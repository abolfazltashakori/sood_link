import os
import requests
import re
import time
import asyncio
import logging
from ftplib import FTP
from urllib.parse import urlparse

FTP_HOST_IRAN = os.getenv("FTP_HOST", "ir5.incel.space")
FTP_USER_IRAN = os.getenv("FTP_USER", "ir5incel")
FTP_PASS_IRAN = os.getenv("FTP_PASS", "cx4#%ao6Utf#")


logger = logging.getLogger(__name__)


def get_file_info_from_url(url):
    try:

        response = requests.head(url, allow_redirects=True, timeout=10)


        if response.status_code == 405:
            response = requests.get(url, stream=True, timeout=10)
            response.close()


        content_disposition = response.headers.get('Content-Disposition', '')
        filename_match = re.findall('filename="?(.+)"?', content_disposition)

        if filename_match:
            file_name = filename_match[0]
        else:
            # استخراج نام فایل از URL
            parsed = urlparse(url)
            file_name = os.path.basename(parsed.path) or "unknown_file"

        # دریافت حجم فایل
        file_size = int(response.headers.get('Content-Length', 0))

        return file_name, file_size

    except Exception as e:
        logger.error(f"Error getting file info: {e}")
        return None, 0


class CallbackWrapper:
    def __init__(self, response, progress_callback):
        self.response = response
        self.progress_callback = progress_callback
        self.total_size = int(response.headers.get('content-length', 0))
        self.uploaded = 0
        self.start_time = time.time()
        self.last_update = 0

    def read(self, chunk_size):
        chunk = self.response.raw.read(chunk_size)
        if chunk:
            self.uploaded += len(chunk)
            if self.progress_callback:
                self.progress_callback(self.uploaded, self.total_size)
        return chunk


def upload_to_ftp_with_progress(file_url, file_name, progress_callback=None):
    try:
        ftp = FTP()
        ftp.connect(FTP_HOST_IRAN, 21)
        ftp.login(FTP_USER_IRAN, FTP_PASS_IRAN)
        ftp.cwd('/public_html/')

        # Get file content in memory
        response = requests.get(file_url, stream=True)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        chunks = []

        # Collect all chunks in memory
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                chunks.append(chunk)
                downloaded += len(chunk)
                if progress_callback:
                    progress_callback(downloaded, total_size)

        # Combine all chunks into a single bytes object
        file_content = b''.join(chunks)

        # Create a BytesIO object to simulate a file
        from io import BytesIO
        file_like = BytesIO(file_content)

        # Upload using storbinary
        ftp.storbinary(f'STOR {file_name}', file_like)

        ftp.quit()
        return f"http://{FTP_HOST_IRAN}/{file_name}"

    except Exception as e:
        logger.error(f"FTP upload error: {e}")
        return None