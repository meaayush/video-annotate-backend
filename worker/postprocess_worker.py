import os
import tempfile
import uuid

import django

django.setup()

from core.models import Video
from util.redis import (
    ack_video_postprocess,
    dequeue_video_postprocess,
    nack_video_postprocess,
    recover_postprocess_queue,
)
from util.s3 import generate_signed_download_url, upload_file_to_s3
from worker.common import extract_duration, generate_thumbnail


def process_local_upload(video_id, s3_key):
    try:
        video = Video.objects.get(id=video_id)
    except Video.DoesNotExist:
        print(f'Video {video_id} not found, skipping.')
        return

    tmp_dir = tempfile.mkdtemp()
    thumbnail_path = os.path.join(tmp_dir, f'{uuid.uuid4()}.jpg')

    try:
        signed_url = generate_signed_download_url(s3_key)
        print(f'Post-processing video {video_id} via presigned URL...')

        duration = extract_duration(signed_url)
        if duration:
            video.duration = duration

        if generate_thumbnail(signed_url, thumbnail_path):
            s3_thumb_key = f'thumbnails/{video_id}/{uuid.uuid4()}.jpg'
            thumbnail_url = upload_file_to_s3(thumbnail_path, s3_thumb_key, content_type='image/jpeg')
            video.thumbnail_url = thumbnail_url
            print(f'Uploaded thumbnail to S3: {thumbnail_url}')

        video.status = Video.Status.READY
        video.save()
        print(f'Video {video_id} post-processing complete.')

    finally:
        if os.path.exists(thumbnail_path):
            os.remove(thumbnail_path)
        if os.path.exists(tmp_dir):
            os.rmdir(tmp_dir)


def run():
    print('Starting post-process worker...')
    recover_postprocess_queue()

    while True:
        result = dequeue_video_postprocess(timeout=5)
        if not result:
            continue

        raw_job, video_id, s3_key = result
        print(f'Got post-process job: video_id={video_id}, s3_key={s3_key}')

        try:
            process_local_upload(video_id, s3_key)
            ack_video_postprocess(raw_job)
        except Exception as e:
            print(f'Video {video_id} post-processing failed: {e}')
            nack_video_postprocess(raw_job)
            try:
                video = Video.objects.get(id=video_id)
                video.status = Video.Status.FAILED
                video.save()
            except Video.DoesNotExist:
                pass


if __name__ == '__main__':
    run()
