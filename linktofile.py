import random
import re
import os
import time
import requests
import shutil
from urllib.parse import urlparse
from ftplib import FTP
import logging
import urllib3

# غیرفعال کردن هشدارهای SSL (بدون استفاده از requests.packages)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

FTP_HOST_IRAN = os.getenv("FTP_HOST", "ir5.incel.space")
FTP_USER_IRAN = os.getenv("FTP_USER", "ir5incel")
FTP_PASS_IRAN = os.getenv("FTP_PASS", "cx4#%ao6Utf#")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"
]

logger = logging.getLogger(__name__)


def get_file_info_from_url(url, retries=3):
    for attempt in range(retries):
        try:
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            session = requests.Session()
            session.verify = False
            session.max_redirects = 5

            # تلاش اول با HEAD
            try:
                response = session.head(url, headers=headers, allow_redirects=True, timeout=15)
                if response.status_code == 200:
                    file_name = extract_filename(url, response.headers.get('Content-Disposition', ''))
                    file_size = int(response.headers.get('Content-Length', 0))
                    return file_name, file_size
            except Exception:
                pass

            # تلاش با GET
            response = session.get(url, headers=headers, stream=True, timeout=25)
            if response.status_code == 200:
                file_name = extract_filename(url, response.headers.get('Content-Disposition', ''))
                file_size = int(response.headers.get('Content-Length', 0))
                if file_size == 0:
                    file_size = get_size_via_content(url)
                return file_name, file_size

        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
            time.sleep(1)

    return None, 0

def get_size_via_content(url):
    try:
        with requests.get(url, stream=True, timeout=15) as r:
            r.raise_for_status()
            return int(r.headers.get('content-length', 0))
    except Exception:
        return 0


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
def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Referer": "https://www.google.com/",
        "DNT": "1",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache"
    }

def upload_to_ftp_with_progress(file_url, file_name, progress_callback=None):
    temp_path = f"/tmp/{file_name}"
    session = requests.Session()
    # ایمن‌سازی: اگر می‌خواهید گواهی SSL را نادیده بگیرید
    session.verify = False
    # جلوگیری از استفاده از پراکسی env (اگر می‌خواهید)
    session.trust_env = False
    session.max_redirects = 10
    session.headers.update(get_headers())

    try:
        # ابتدا یک HEAD بزنیم تا ببینیم سرور چه می‌گوید
        try:
            head = session.head(file_url, allow_redirects=True, timeout=15)
        except Exception:
            head = None

        # تلاش برای دانلود (اولین تلاش با هدرهای اولیه)
        r = session.get(file_url, stream=True, timeout=60, allow_redirects=True)

        if r.status_code == 403:
            try:
                import cloudscraper
                scraper = cloudscraper.create_scraper()
                # کپی هدرها به scraper
                scraper.headers.update(session.headers)
                r = scraper.get(file_url, stream=True, timeout=60, allow_redirects=True)
            except Exception:
                # cloudscraper نصب نشده یا خطا، ادامه می‌دهیم و لاگ می‌زنیم
                logger.warning("cloudscraper fallback failed or not installed")

        # در اینجا بررسی نهایی وضعیت
        if r.status_code not in (200, 206):
            # لاگِ هدرها/کد برای دیباگ
            logger.error(f"Download failed: {r.status_code} for url: {file_url}")
            logger.debug(f"Response headers: {r.headers}")
            # تلاش نهایی: لاگِ مقداری از متن پاسخ (کم) برای فهم دلیل
            try:
                snippet = r.content[:512]
                logger.debug(f"Response snippet: {snippet!r}")
            except Exception:
                pass
            return None

        # نوشتن فایل موقت و گزارش پیشرفت (اگر callback داده شده)
        total = int(r.headers.get('content-length') or 0)
        downloaded = 0
        with open(temp_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback and total:
                    try:
                        progress_callback(downloaded, total)
                    except Exception:
                        pass

        # آپلود به FTP
        ftp = FTP()
        ftp.connect(FTP_HOST_IRAN, 21, timeout=30)
        ftp.login(FTP_USER_IRAN, FTP_PASS_IRAN)
        ftp.cwd('/public_html/')
        with open(temp_path, 'rb') as f:
            ftp.storbinary(f'STOR {file_name}', f)
        ftp.quit()

        # حذف فایل موقت
        try:
            os.remove(temp_path)
        except Exception:
            pass

        return f"http://{FTP_HOST_IRAN}/{file_name}"

    except Exception as e:
        # بهتر است لاگ دقیق‌تری داشته باشیم تا متوجه شویم خطا از دانلود است یا FTP
        logger.error(f"Upload/download error for {file_url}: {e}")
        # تلاش برای حذف فایل موقت در صورت وجود
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass
        return None


def extract_info(response, url):
    content_disposition = response.headers.get('Content-Disposition', '')
    file_name = extract_filename(url, content_disposition)

    # محاسبه حجم از طریق محتوای دریافتی اگر Content-Length وجود نداشت
    file_size = int(response.headers.get('Content-Length', 0))
    if file_size == 0 and 'content-length' not in response.headers:
        response.close()
        file_size = get_size_via_content(url)

    return file_name, file_size


def get_size_via_content(url):
    try:
        with requests.get(url, stream=True, timeout=15) as r:
            r.raise_for_status()
            return int(r.headers.get('content-length', 0))
    except Exception:
        return 0


def extract_filename(url, content_disposition=""):
    """
    استخراج نام فایل از Content-Disposition یا URL
    """
    # 1. اول از Content-Disposition استخراج می‌کنیم
    if content_disposition:
        filename_match = re.findall('filename="?(.+)"?', content_disposition)
        if filename_match:
            return filename_match[0].strip()

    # 2. اگر پیدا نشد، از URL استخراج می‌کنیم
    parsed = urlparse(url)
    path = parsed.path
    if path:
        base = os.path.basename(path)
        if base:
            # حذف پارامترهای اضافی
            return base.split('?')[0].split('#')[0].strip()

    # 3. اگر هیچکدام کار نکرد، نام پیش‌فرض
    return f"file_{int(time.time())}"