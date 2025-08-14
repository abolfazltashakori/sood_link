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


def get_file_info_from_url(url, retries=2):
    for attempt in range(retries):
        try:
            # تلاش با متد HEAD
            with requests.Session() as session:
                session.headers.update(HEADERS)
                response = session.head(url, allow_redirects=True, timeout=15)

                if response.status_code == 200:
                    content_disposition = response.headers.get('Content-Disposition', '')
                    filename_match = re.findall('filename="?(.+)"?', content_disposition)

                    file_name = (
                        filename_match[0]
                        if filename_match
                        else os.path.basename(urlparse(url).path) or "unknown_file"
                    )
                    file_size = int(response.headers.get('Content-Length', 0))
                    return file_name, file_size

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            if attempt < retries - 1:
                time.sleep(1)
                continue
            raise

        except Exception:
            pass

        try:

            with requests.Session() as session:
                session.headers.update(HEADERS)
                response = session.get(url, stream=True, timeout=20)

                if response.status_code == 200:
                    content_disposition = response.headers.get('Content-Disposition', '')
                    filename_match = re.findall('filename="?(.+)"?', content_disposition)

                    file_name = (
                        filename_match[0]
                        if filename_match
                        else os.path.basename(urlparse(url).path) or "unknown_file"
                    )
                    file_size = int(response.headers.get('Content-Length', 0))
                    response.close()  # قطع اتصال
                    return file_name, file_size

        except Exception as e:
            logger.error(f"Final attempt failed: {e}")
            return None, 0

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