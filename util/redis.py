import json

from redis import Redis

from config.environment import REDIS_DB, REDIS_HOST, REDIS_PORT

VIDEO_UPLOAD_QUEUE = 'video_upload_queue'
VIDEO_UPLOAD_PROCESSING = 'video_upload_processing'

VIDEO_POSTPROCESS_QUEUE = 'video_postprocess_queue'
VIDEO_POSTPROCESS_PROCESSING = 'video_postprocess_processing'

MAX_RETRIES = 3


def get_redis_client():
    return Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)


# --------------- enqueue ---------------

def enqueue_video_upload(video_id, source_url):
    client = get_redis_client()
    job = json.dumps({
        'video_id': str(video_id),
        'source_url': source_url,
        'retries': 0,
    })
    client.lpush(VIDEO_UPLOAD_QUEUE, job)


def enqueue_video_postprocess(video_id, s3_key):
    client = get_redis_client()
    job = json.dumps({
        'video_id': str(video_id),
        's3_key': s3_key,
        'retries': 0,
    })
    client.lpush(VIDEO_POSTPROCESS_QUEUE, job)


# --------------- dequeue (atomic move to processing list) ---------------

def dequeue_video_upload(timeout=5):
    client = get_redis_client()
    raw = client.brpoplpush(VIDEO_UPLOAD_QUEUE, VIDEO_UPLOAD_PROCESSING, timeout=timeout)
    if raw:
        job = json.loads(raw)
        return raw, job['video_id'], job['source_url']
    return None


def dequeue_video_postprocess(timeout=5):
    client = get_redis_client()
    raw = client.brpoplpush(VIDEO_POSTPROCESS_QUEUE, VIDEO_POSTPROCESS_PROCESSING, timeout=timeout)
    if raw:
        job = json.loads(raw)
        return raw, job['video_id'], job['s3_key']
    return None


# --------------- ack / nack ---------------

def ack_video_upload(raw_job):
    """Remove from processing list after successful processing."""
    client = get_redis_client()
    client.lrem(VIDEO_UPLOAD_PROCESSING, 1, raw_job)


def nack_video_upload(raw_job):
    """On failure: re-enqueue if retries remain, otherwise discard."""
    client = get_redis_client()
    client.lrem(VIDEO_UPLOAD_PROCESSING, 1, raw_job)
    job = json.loads(raw_job)
    if job.get('retries', 0) < MAX_RETRIES:
        job['retries'] = job.get('retries', 0) + 1
        print(f"  Re-enqueuing video {job['video_id']} (retry {job['retries']}/{MAX_RETRIES})")
        client.lpush(VIDEO_UPLOAD_QUEUE, json.dumps(job))
    else:
        print(f"  Max retries reached for video {job['video_id']}, giving up.")


def ack_video_postprocess(raw_job):
    """Remove from processing list after successful processing."""
    client = get_redis_client()
    client.lrem(VIDEO_POSTPROCESS_PROCESSING, 1, raw_job)


def nack_video_postprocess(raw_job):
    """On failure: re-enqueue if retries remain, otherwise discard."""
    client = get_redis_client()
    client.lrem(VIDEO_POSTPROCESS_PROCESSING, 1, raw_job)
    job = json.loads(raw_job)
    if job.get('retries', 0) < MAX_RETRIES:
        job['retries'] = job.get('retries', 0) + 1
        print(f"  Re-enqueuing video {job['video_id']} (retry {job['retries']}/{MAX_RETRIES})")
        client.lpush(VIDEO_POSTPROCESS_QUEUE, json.dumps(job))
    else:
        print(f"  Max retries reached for video {job['video_id']}, giving up.")


# --------------- recovery (run on worker startup) ---------------

def recover_upload_queue():
    """Move any orphaned jobs from processing back to the pending queue."""
    client = get_redis_client()
    count = 0
    while True:
        raw = client.rpoplpush(VIDEO_UPLOAD_PROCESSING, VIDEO_UPLOAD_QUEUE)
        if not raw:
            break
        count += 1
    if count:
        print(f'Recovered {count} orphaned upload job(s).')


def recover_postprocess_queue():
    client = get_redis_client()
    count = 0
    while True:
        raw = client.rpoplpush(VIDEO_POSTPROCESS_PROCESSING, VIDEO_POSTPROCESS_QUEUE)
        if not raw:
            break
        count += 1
    if count:
        print(f'Recovered {count} orphaned post-process job(s).')
