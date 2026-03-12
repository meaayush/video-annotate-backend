from flask import request
from flask_restful import Resource

from core.models import Annotation, Video

DEFAULT_PAGE_SIZE = 50

ANNOTATION_FIELDS = (
    'id', 'type', 'source', 'frame_number', 'timestamp', 'content', 'created_at',
)


def serialize_annotation(a):
    return {
        'id': str(a['id']),
        'type': a['type'],
        'source': a['source'],
        'frame_number': a['frame_number'],
        'timestamp': a['timestamp'],
        'content': a['content'],
        'created_at': a['created_at'].isoformat() if a['created_at'] else None,
    }


# ---- Manual annotations (no pagination) ----

class AnnotationList(Resource):
    def get(self, video_id):
        """List all manual annotations for a video."""
        if not Video.objects.filter(id=video_id).exists():
            return {'error': 'Video not found'}, 404

        annotations = Annotation.objects.filter(
            video_id=video_id,
            source=Annotation.Source.MANUAL,
        ).values(*ANNOTATION_FIELDS)

        return {
            'annotations': [serialize_annotation(a) for a in annotations],
        }, 200

    def post(self, video_id):
        """Create a manual annotation."""
        try:
            video = Video.objects.get(id=video_id)
        except Video.DoesNotExist:
            return {'error': 'Video not found'}, 404

        data = request.get_json()
        ann_type = data.get('type')
        content = data.get('content', '')

        if ann_type not in ('frame', 'timestamp'):
            return {'error': "type must be 'frame' or 'timestamp'"}, 400

        if ann_type == 'frame' and data.get('frame_number') is None:
            return {'error': 'frame_number is required for frame annotations'}, 400

        if ann_type == 'timestamp' and data.get('timestamp') is None:
            return {'error': 'timestamp is required for timestamp annotations'}, 400

        annotation = Annotation.objects.create(
            video=video,
            type=ann_type,
            source=Annotation.Source.MANUAL,
            frame_number=data.get('frame_number'),
            timestamp=data.get('timestamp'),
            content=content,
        )

        return {
            'id': str(annotation.id),
            'type': annotation.type,
            'source': annotation.source,
            'frame_number': annotation.frame_number,
            'timestamp': annotation.timestamp,
            'content': annotation.content,
            'created_at': annotation.created_at.isoformat() if annotation.created_at else None,
        }, 201


class AnnotationDetail(Resource):
    """PATCH/DELETE works for both manual and auto annotations."""
    def patch(self, video_id, annotation_id):
        try:
            annotation = Annotation.objects.get(id=annotation_id, video_id=video_id)
        except Annotation.DoesNotExist:
            return {'error': 'Annotation not found'}, 404

        data = request.get_json()

        if 'content' in data:
            annotation.content = data['content']
        if 'frame_number' in data:
            annotation.frame_number = data['frame_number']
        if 'timestamp' in data:
            annotation.timestamp = data['timestamp']

        annotation.save()

        return {
            'id': str(annotation.id),
            'type': annotation.type,
            'source': annotation.source,
            'frame_number': annotation.frame_number,
            'timestamp': annotation.timestamp,
            'content': annotation.content,
            'created_at': annotation.created_at.isoformat() if annotation.created_at else None,
        }, 200

    def delete(self, video_id, annotation_id):
        try:
            annotation = Annotation.objects.get(id=annotation_id, video_id=video_id)
        except Annotation.DoesNotExist:
            return {'error': 'Annotation not found'}, 404

        annotation.delete()
        return {'message': 'Annotation deleted'}, 200


# ---- Auto annotations (paginated, separate API) ----

class AutoAnnotationList(Resource):
    def get(self, video_id):
        """
        Returns ALL auto-annotation slots for the video, paginated.
        Slots are generated from duration + interval.
        Slots that have saved content include id, content, note.
        Empty slots have null id/content/note.
        """
        try:
            video = Video.objects.only(
                'id', 'duration', 'auto_annotation_interval',
            ).get(id=video_id)
        except Video.DoesNotExist:
            return {'error': 'Video not found'}, 404

        interval = video.auto_annotation_interval
        duration = video.duration

        if not interval or not duration:
            return {
                'annotations': [],
                'pagination': {'page': 1, 'page_size': DEFAULT_PAGE_SIZE, 'total': 0, 'total_pages': 0},
                'auto_annotation_interval': interval,
                'duration': duration,
            }, 200

        # Generate all timestamps: 0, interval, 2*interval, ...
        all_timestamps = []
        ts = 0.0
        while ts <= duration:
            all_timestamps.append(round(ts, 2))
            ts += interval
        total = len(all_timestamps)

        # Paginate
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', DEFAULT_PAGE_SIZE, type=int)
        offset = (page - 1) * page_size
        page_timestamps = all_timestamps[offset:offset + page_size]

        # Fetch saved annotations for this page's timestamp range only
        saved = Annotation.objects.filter(
            video_id=video_id,
            source=Annotation.Source.AUTO,
            timestamp__in=page_timestamps,
        ).values(*ANNOTATION_FIELDS)

        saved_map = {a['timestamp']: a for a in saved}

        # Merge: fill in saved content or return empty slot
        annotations = []
        for ts in page_timestamps:
            if ts in saved_map:
                annotations.append(serialize_annotation(saved_map[ts]))
            else:
                annotations.append({
                    'id': None,
                    'type': 'timestamp',
                    'source': 'auto',
                    'frame_number': None,
                    'timestamp': ts,
                    'content': '',
                    'created_at': None,
                })

        return {
            'annotations': annotations,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total': total,
                'total_pages': (total + page_size - 1) // page_size if page_size else 1,
            },
            'auto_annotation_interval': interval,
            'duration': duration,
        }, 200

    def post(self, video_id):
        """Save a note/content on an auto-annotation timestamp (upsert)."""
        try:
            video = Video.objects.get(id=video_id)
        except Video.DoesNotExist:
            return {'error': 'Video not found'}, 404

        data = request.get_json()
        ts = data.get('timestamp')

        if ts is None:
            return {'error': 'timestamp is required for auto annotations'}, 400

        annotation, created = Annotation.objects.update_or_create(
            video=video,
            source=Annotation.Source.AUTO,
            timestamp=ts,
            defaults={
                'type': Annotation.AnnotationType.TIMESTAMP,
                'content': data.get('content', ''),
            },
        )

        return {
            'id': str(annotation.id),
            'type': annotation.type,
            'source': annotation.source,
            'timestamp': annotation.timestamp,
            'content': annotation.content,
            'created_at': annotation.created_at.isoformat() if annotation.created_at else None,
        }, 201 if created else 200


# ---- Auto annotation interval setting ----

class AutoAnnotationInterval(Resource):
    def patch(self, video_id):
        try:
            video = Video.objects.get(id=video_id)
        except Video.DoesNotExist:
            return {'error': 'Video not found'}, 404

        data = request.get_json()
        interval = data.get('auto_annotation_interval')

        if interval is not None and interval not in (1, 5, 10):
            return {'error': 'auto_annotation_interval must be 1, 5, or 10'}, 400

        video.auto_annotation_interval = interval
        video.save()

        return {
            'video_id': str(video.id),
            'auto_annotation_interval': video.auto_annotation_interval,
        }, 200
