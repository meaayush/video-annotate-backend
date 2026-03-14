from flask import request
from flask_restful import Resource

from core.models import Annotation, Video
from util.summary import summarize_annotations, postprocess_highlights_time

DEFAULT_PAGE_SIZE = 50

ANNOTATION_FIELDS = (
    'id', 'type', 'source', 'timestamp', 'timestamp_start', 'timestamp_end', 'content', 'created_at',
)


def serialize_annotation(a):
    return {
        'id': str(a['id']),
        'type': a['type'],
        'source': a['source'],
        'timestamp': a['timestamp'],
        'timestamp_start': a['timestamp_start'],
        'timestamp_end': a['timestamp_end'],
        'content': a['content'],
        'created_at': a['created_at'].isoformat() if a['created_at'] else None,
    }

class AnnotationList(Resource):
    def get(self, video_id):
        """List all manual annotations for a video."""
        if not Video.objects.filter(id=video_id).exists():
            return {'error': 'Video not found'}, 404

        qs = Annotation.objects.filter(
            video_id=video_id,
            source=Annotation.Source.MANUAL,
        )

        search = request.args.get('search', '').strip()
        if search:
            qs = qs.filter(content__icontains=search)

        return {
            'annotations': [serialize_annotation(a) for a in qs.values(*ANNOTATION_FIELDS)],
            'search': search or None,
        }, 200

    def post(self, video_id):
        try:
            video = Video.objects.get(id=video_id)
        except Video.DoesNotExist:
            return {'error': 'Video not found'}, 404

        data = request.get_json()
        ann_type = data.get('type')
        content = data.get('content', '')

        if ann_type not in ('frame', 'timestamp'):
            return {'error': "type must be 'frame' or 'timestamp'"}, 400

        if ann_type == 'frame' and (data.get('timestamp_start') is None or data.get('timestamp_end') is None):
            return {'error': 'timestamp_start and timestamp_end are required for frame annotations'}, 400

        if ann_type == 'frame' and data['timestamp_start'] >= data['timestamp_end']:
            return {'error': 'timestamp_start must be less than timestamp_end'}, 400

        if ann_type == 'timestamp' and data.get('timestamp') is None:
            return {'error': 'timestamp is required for timestamp annotations'}, 400

        lookup = {'video': video, 'source': Annotation.Source.MANUAL, 'type': ann_type}
        if ann_type == 'timestamp':
            lookup['timestamp'] = data.get('timestamp')
        else:
            lookup['timestamp_start'] = data.get('timestamp_start')
            lookup['timestamp_end'] = data.get('timestamp_end')

        annotation, created = Annotation.objects.update_or_create(
            **lookup,
            defaults={
                'timestamp': data.get('timestamp'),
                'timestamp_start': data.get('timestamp_start'),
                'timestamp_end': data.get('timestamp_end'),
                'content': content,
            },
        )

        return {
            'id': str(annotation.id),
            'type': annotation.type,
            'source': annotation.source,
            'timestamp': annotation.timestamp,
            'timestamp_start': annotation.timestamp_start,
            'timestamp_end': annotation.timestamp_end,
            'content': annotation.content,
            'created_at': annotation.created_at.isoformat() if annotation.created_at else None,
        }, 200 if not created else 201


class AnnotationDetail(Resource):
    def patch(self, video_id, annotation_id):
        try:
            annotation = Annotation.objects.get(id=annotation_id, video_id=video_id)
        except Annotation.DoesNotExist:
            return {'error': 'Annotation not found'}, 404

        data = request.get_json()

        if 'content' in data:
            annotation.content = data['content']
        if 'timestamp' in data:
            annotation.timestamp = data['timestamp']
        if 'timestamp_start' in data:
            annotation.timestamp_start = data['timestamp_start']
        if 'timestamp_end' in data:
            annotation.timestamp_end = data['timestamp_end']

        annotation.save()

        return {
            'id': str(annotation.id),
            'type': annotation.type,
            'source': annotation.source,
            'timestamp': annotation.timestamp,
            'timestamp_start': annotation.timestamp_start,
            'timestamp_end': annotation.timestamp_end,
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


class VideoSummary(Resource):
    def get(self, video_id):
        if not Video.objects.filter(id=video_id).exists():
            return {'error': 'Video not found'}, 404

        ts_annotations = (
            Annotation.objects
            .filter(video_id=video_id, type=Annotation.AnnotationType.TIMESTAMP, timestamp__isnull=False)
            .exclude(content='')
            .values('timestamp', 'content')
        )
        frame_annotations = (
            Annotation.objects
            .filter(video_id=video_id, type=Annotation.AnnotationType.FRAME, timestamp_start__isnull=False)
            .exclude(content='')
            .values('timestamp_start', 'content')
        )

        items = [
            {'timestamp': float(a['timestamp']), 'content': a['content']}
            for a in ts_annotations
        ] + [
            {'timestamp': float(a['timestamp_start']), 'content': a['content']}
            for a in frame_annotations
        ]
        items.sort(key=lambda x: x['timestamp'])

        if not items:
            return {'error': 'No annotations with timestamps found for this video'}, 422

        summary = summarize_annotations(items)
        summary = postprocess_highlights_time(summary)
        
        return summary, 200


class AutoAnnotationList(Resource):
    def get(self, video_id):
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

        all_timestamps = []
        ts = 0.0
        while ts <= duration:
            all_timestamps.append(round(ts, 2))
            ts += interval
        total = len(all_timestamps)

        search = request.args.get('search', '').strip()

        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', DEFAULT_PAGE_SIZE, type=int)

        # When searching, skip slot generation — paginate over saved annotations matching content
        if search:
            saved_qs = Annotation.objects.filter(
                video_id=video_id,
                source=Annotation.Source.AUTO,
                content__icontains=search,
            ).order_by('timestamp')

            total_search = saved_qs.count()
            offset = (page - 1) * page_size
            paged = saved_qs.values(*ANNOTATION_FIELDS)[offset:offset + page_size]

            return {
                'annotations': [serialize_annotation(a) for a in paged],
                'search': search,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total': total_search,
                    'total_pages': (total_search + page_size - 1) // page_size if page_size else 1,
                },
                'auto_annotation_interval': interval,
                'duration': duration,
            }, 200
        offset = (page - 1) * page_size
        page_timestamps = all_timestamps[offset:offset + page_size]

        saved = Annotation.objects.filter(
            video_id=video_id,
            source=Annotation.Source.AUTO,
            timestamp__in=page_timestamps,
        ).values(*ANNOTATION_FIELDS)

        saved_map = {a['timestamp']: a for a in saved}

        annotations = []
        for ts in page_timestamps:
            if ts in saved_map:
                annotations.append(serialize_annotation(saved_map[ts]))
            else:
                annotations.append({
                    'id': None,
                    'type': 'timestamp',
                    'source': 'auto',
                    'timestamp': ts,
                    'timestamp_start': None,
                    'timestamp_end': None,
                    'content': '',
                    'created_at': None,
                })

        return {
            'annotations': annotations,
            'search': None,
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
