from flask import request
from flask_restful import Resource

from core.models import Video
from util.s3 import build_video_url, generate_signed_upload_url
from util.redis import enqueue_video_upload, enqueue_video_postprocess


class UploadSignedUrl(Resource):
    def post(self):
        data = request.get_json()
        title = data.get('title', 'Untitled')
        content_type = data.get('content_type', 'video/mp4')
        auto_annotation_interval = data.get('auto_annotation_interval')

        video = Video.objects.create(
            title=title,
            source_type=Video.SourceType.LOCAL_UPLOAD,
            status=Video.Status.PENDING,
            auto_annotation_interval=auto_annotation_interval,
        )

        try:
            signed_url, s3_key = generate_signed_upload_url(video.id, content_type)
        except Exception as e:
            video.status = Video.Status.FAILED
            video.save()
            return {'error': f'Failed to generate signed URL: {str(e)}'}, 500

        return {
            'video_id': str(video.id),
            'signed_url': signed_url,
            's3_key': s3_key,
        }, 200


class UploadConfirm(Resource):
    def post(self):
        data = request.get_json()
        video_id = data.get('video_id')
        s3_key = data.get('s3_key')

        if not video_id or not s3_key:
            return {'error': 'video_id and s3_key are required'}, 400

        try:
            video = Video.objects.get(id=video_id)
        except Video.DoesNotExist:
            return {'error': 'Video not found'}, 404

        video.video_url = build_video_url(s3_key)
        video.status = Video.Status.PROCESSING
        video.save()

        # Enqueue post-processing (thumbnail + duration extraction)
        try:
            enqueue_video_postprocess(video.id, s3_key)
        except Exception as e:
            video.status = Video.Status.FAILED
            video.save()
            return {'error': f'Failed to enqueue post-processing: {str(e)}'}, 500

        return {
            'video_id': str(video.id),
            'status': video.status,
            'video_url': video.video_url,
        }, 200


class UploadUrl(Resource):
    def post(self):
        data = request.get_json()
        url = data.get('url')
        title = data.get('title', 'Untitled')
        auto_annotation_interval = data.get('auto_annotation_interval')

        if not url:
            return {'error': 'url is required'}, 400

        video = Video.objects.create(
            title=title,
            source_type=Video.SourceType.URL_UPLOAD,
            status=Video.Status.PENDING,
            auto_annotation_interval=auto_annotation_interval,
        )

        try:
            enqueue_video_upload(video.id, url)
        except Exception as e:
            video.status = Video.Status.FAILED
            video.save()
            return {'error': f'Failed to enqueue job: {str(e)}'}, 500

        return {
            'video_id': str(video.id),
            'status': video.status,
            'message': 'Video upload queued',
        }, 202
