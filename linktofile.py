import asyncio
import logging
from ftplib import FTP
from urllib.parse import urlparse
import requests
import re
import os
import time
from urllib.parse import urlparse

FTP_HOST_IRAN = os.getenv("FTP_HOST", "ir5.incel.space")
FTP_USER_IRAN = os.getenv("FTP_USER", "ir5incel")
FTP_PASS_IRAN = os.getenv("FTP_PASS", "cx4#%ao6Utf#")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

logger = logging.getLogger(__name__)





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

        # دریافت فایل با قابلیت نمایش پیشرفت
        response = requests.get(file_url, stream=True)
        response.raise_for_status()

        # ایجاد wrapper برای نمایش پیشرفت
        wrapper = CallbackWrapper(response, progress_callback)

        # آپلود فایل به FTP
        ftp.storbinary(f'STOR {file_name}', wrapper)

        ftp.quit()
        return f"http://{FTP_HOST_IRAN}/{file_name}"

    except Exception as e:
        logger.error(f"FTP upload error: {e}")
        return None