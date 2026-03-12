import os
import subprocess

import requests


DOWNLOAD_CHUNK_SIZE = 1024 * 1024


def download_file(url, dest_path):
    print(f'Downloading {url}...')
    response = requests.get(url, stream=True, timeout=(10, None))
    response.raise_for_status()

    total_size = int(response.headers.get('content-length', 0))
    downloaded = 0

    with open(dest_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
            f.write(chunk)
            downloaded += len(chunk)
            if total_size:
                pct = (downloaded / total_size) * 100
                print(f'  Download progress: {downloaded}/{total_size} bytes ({pct:.1f}%)', end='\r')

    print(f'\nDownloaded to {dest_path} ({os.path.getsize(dest_path)} bytes)')


def extract_duration(video_source):
    try:
        result = subprocess.run(
            [
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_source,
            ],
            capture_output=True, text=True, timeout=60,
        )
        duration = float(result.stdout.strip())
        print(f'Duration: {duration}s')
        return duration
    except Exception as e:
        print(f'Failed to extract duration: {e}')
        return None


def generate_thumbnail(video_source, thumbnail_path):
    try:
        subprocess.run(
            [
                'ffmpeg', '-y',
                '-ss', '00:00:01',
                '-i', video_source,
                '-vframes', '1',
                '-q:v', '2',
                thumbnail_path,
            ],
            capture_output=True, text=True, timeout=60,
        )
        if os.path.exists(thumbnail_path):
            print(f'Thumbnail generated: {thumbnail_path}')
            return True
    except Exception as e:
        print(f'Failed to generate thumbnail: {e}')
    return False
