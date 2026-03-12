from flask_restful import Resource
from core.models import Video


class VideoList(Resource):
    def get(self):
        videos = Video.objects.all().values(
            'id', 'title', 'duration', 'thumbnail_url', 'status', 'created_at',
        )
        return {
            'videos': [
                {
                    'id': str(v['id']),
                    'title': v['title'],
                    'duration': v['duration'],
                    'thumbnail_url': v['thumbnail_url'],
                    'status': v['status'],
                    'created_at': v['created_at'].isoformat() if v['created_at'] else None,
                }
                for v in videos
            ]
        }, 200


class VideoDetail(Resource):
    def get(self, video_id):
        try:
            video = Video.objects.get(id=video_id)
        except Video.DoesNotExist:
            return {'error': 'Video not found'}, 404

        return {
            'id': str(video.id),
            'title': video.title,
            'duration': video.duration,
            'thumbnail_url': video.thumbnail_url,
            'video_url': video.video_url,
            'source_type': video.source_type,
            'status': video.status,
            'auto_annotation_interval': video.auto_annotation_interval,
            'created_at': video.created_at.isoformat() if video.created_at else None,
            'updated_at': video.updated_at.isoformat() if video.updated_at else None,
        }, 200

    def delete(self, video_id):
        try:
            video = Video.objects.get(id=video_id)
        except Video.DoesNotExist:
            return {'error': 'Video not found'}, 404

        video.delete()
        return {'message': 'Video deleted'}, 200
