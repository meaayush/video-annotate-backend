import uuid

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.config import Config

from config.environment import (
    AWS_ACCESS_KEY_ID,
    AWS_S3_BUCKET,
    AWS_S3_REGION,
    AWS_SECRET_ACCESS_KEY,
)

MULTIPART_THRESHOLD = 50 * 1024 * 1024
MULTIPART_CHUNKSIZE = 50 * 1024 * 1024 
MAX_CONCURRENCY = 10          


def get_s3_client():
    return boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_S3_REGION,
        endpoint_url=f'https://s3.{AWS_S3_REGION}.amazonaws.com',
        config=Config(signature_version='s3v4'),
    )


def generate_signed_upload_url(video_id, content_type='video/mp4', expires_in=3600):
    s3 = get_s3_client()
    s3_key = f'videos/{video_id}/{uuid.uuid4()}.mp4'
    signed_url = s3.generate_presigned_url(
        'put_object',
        Params={
            'Bucket': AWS_S3_BUCKET,
            'Key': s3_key,
            'ContentType': content_type,
        },
        ExpiresIn=expires_in,
    )
    return signed_url, s3_key


def upload_file_to_s3(file_path, s3_key, content_type='video/mp4'):
    s3 = get_s3_client()
    transfer_config = TransferConfig(
        multipart_threshold=MULTIPART_THRESHOLD,
        multipart_chunksize=MULTIPART_CHUNKSIZE,
        max_concurrency=MAX_CONCURRENCY,
    )
    s3.upload_file(
        file_path,
        AWS_S3_BUCKET,
        s3_key,
        ExtraArgs={'ContentType': content_type},
        Config=transfer_config,
    )
    return build_video_url(s3_key)


def download_from_s3(s3_key, dest_path):
    s3 = get_s3_client()
    s3.download_file(AWS_S3_BUCKET, s3_key, dest_path)


def generate_signed_download_url(s3_key, expires_in=3600):
    s3 = get_s3_client()
    return s3.generate_presigned_url(
        'get_object',
        Params={'Bucket': AWS_S3_BUCKET, 'Key': s3_key},
        ExpiresIn=expires_in,
    )


def build_video_url(s3_key):
    return f'https://{AWS_S3_BUCKET}.s3.{AWS_S3_REGION}.amazonaws.com/{s3_key}'
