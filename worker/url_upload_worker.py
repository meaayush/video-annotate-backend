import os
import tempfile
import uuid

import django
django.setup()

from core.models import Video
from util.redis import (
    ack_video_upload,
    dequeue_video_upload,
    nack_video_upload,
    recover_upload_queue,
)
from util.s3 import upload_file_to_s3
from worker.common import download_file, extract_duration, generate_thumbnail


def process_url_upload(video_id, source_url):
    try:
        video = Video.objects.get(id=video_id)
    except Video.DoesNotExist:
        print(f'Video {video_id} not found, skipping.')
        return

    video.status = Video.Status.PROCESSING
    video.save()

    tmp_dir = tempfile.mkdtemp()
    video_path = os.path.join(tmp_dir, f'{uuid.uuid4()}.mp4')
    thumbnail_path = os.path.join(tmp_dir, f'{uuid.uuid4()}.jpg')

    try:
        download_file(source_url, video_path)

        s3_video_key = f'videos/{video_id}/{uuid.uuid4()}.mp4'
        video_url = upload_file_to_s3(video_path, s3_video_key, content_type='video/mp4')
        video.video_url = video_url
        print(f'Uploaded video to S3: {video_url}')

        duration = extract_duration(video_path)
        if duration:
            video.duration = duration

        if generate_thumbnail(video_path, thumbnail_path):
            s3_thumb_key = f'thumbnails/{video_id}/{uuid.uuid4()}.jpg'
            thumbnail_url = upload_file_to_s3(thumbnail_path, s3_thumb_key, content_type='image/jpeg')
            video.thumbnail_url = thumbnail_url
            print(f'Uploaded thumbnail to S3: {thumbnail_url}')

        video.status = Video.Status.READY
        video.save()
        print(f'Video {video_id} processed successfully.')

    finally:
        for path in [video_path, thumbnail_path]:
            if os.path.exists(path):
                os.remove(path)
        if os.path.exists(tmp_dir):
            os.rmdir(tmp_dir)


def run():
    print('Starting URL upload worker...')
    recover_upload_queue()

    while True:
        result = dequeue_video_upload(timeout=5)
        if not result:
            continue

        raw_job, video_id, source_url = result
        print(f'Got upload job: video_id={video_id}, url={source_url}')

        try:
            process_url_upload(video_id, source_url)
            ack_video_upload(raw_job)
        except Exception as e:
            print(f'Video {video_id} failed: {e}')
            nack_video_upload(raw_job)
            # Mark video as failed only if max retries exhausted
            try:
                video = Video.objects.get(id=video_id)
                video.status = Video.Status.FAILED
                video.save()
            except Video.DoesNotExist:
                pass


if __name__ == '__main__':
    run()
