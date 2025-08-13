from pyrogram import Client, filters, enums
from pyrogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, Message
from pyrogram.errors import UserNotParticipant, ChannelPrivate, ChannelInvalid
from config import *
from database_main import *
import requests
import re
import os
from urllib.parse import urlparse
from ftplib import FTP
import asyncio
import logging
from linktofile import *

logger = logging.getLogger(__name__)
global_convers = {}
pending_links = {}


bot = Client(
    "Link_service_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)
def readable(size: float) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} GB"

def format_time(seconds: float) -> str:
    # فرمت‌دهی زمان به صورت خوانا
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


@bot.on_message(filters.command("start"))
async def start(client, message):
    user =message.from_user
    telegram_id = user.id
    first_name = user.first_name
    last_name = user.last_name
    username = user.username
    create_user_if_not_exists(telegram_id, first_name, last_name,username)

    if telegram_id == ADMIN_ID:
        keyboard = ReplyKeyboardMarkup(
            [
                [KeyboardButton("📚 راهنما"), KeyboardButton("📊 ترافیک باقیمانده")],
                [KeyboardButton("💳 تعرفه ها"), KeyboardButton("⚙️ تنظیمات")],
                [KeyboardButton("👑 بخش ادمین"), KeyboardButton("📈 آمار ربات")],
                [KeyboardButton("💰 مدیریت موجودی"), KeyboardButton("🤖 سایر ربات‌ها")]
            ],
            resize_keyboard=True
        )
        menu_text = "🛠️ <b>پنل مدیریتی</b>\nلطفاً یک گزینه را انتخاب کنید:"
    else:
        keyboard = ReplyKeyboardMarkup(
            [
                [KeyboardButton("📚 راهنما"), KeyboardButton("📊 ترافیک باقیمانده")],
                [KeyboardButton("💳 تعرفه ها"), KeyboardButton("📈 آمار ربات")],
                [KeyboardButton("💰 مدیریت موجودی"), KeyboardButton("🤖 سایر ربات‌ها")]
            ],
            resize_keyboard=True
        )
        menu_text = "🏠 <b>منوی اصلی</b>\nلطفاً یک گزینه را انتخاب کنید:"
    await message.reply_text(menu_text, reply_markup=keyboard)

@bot.on_message(filters.text & filters.regex("^📊 ترافیک باقیمانده$"))
async def return_terrafic(client, message):
    user_id = message.from_user.id
    traffic = return_traffic(user_id)
    await message.reply_text(f"ترافیک باقی مانده شما: {readable(traffic)}")


@bot.on_message(filters.text & filters.regex(r'https?://[^\s]+'))
async def handle_link(client: Client, message: Message):
    user_id = message.from_user.id
    url = message.text.strip()

    file_name, file_size = await asyncio.to_thread(get_file_info_from_url, url)

    if not file_name or file_size == 0:
        return await message.reply("❌ دریافت اطلاعات فایل ناموفق بود. لطفا لینک معتبر ارسال کنید.")

    # ذخیره اطلاعات در انتظار تایید
    pending_links[user_id] = {
        "url": url,
        "file_name": file_name,
        "file_size": file_size
    }

    # ایجاد دکمه‌های تایید
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تأیید آپلود", callback_data="confirm_link_upload")],
        [InlineKeyboardButton("❌ لغو", callback_data="cancel_link_upload")]
    ])

    await message.reply_text(
        f"📄 فایل شناسایی شده: {file_name}\n"
        f"📦 حجم: {readable(file_size)}\n"
        "آیا مایل به آپلود این فایل هستید؟",
        reply_markup=keyboard,
        quote=True
    )

def get_file_info_from_url(url):
    try:
        # دریافت هدرهای فایل
        response = requests.head(url, allow_redirects=True, timeout=10)

        # اگر متد HEAD پشتیبانی نشود
        if response.status_code == 405:
            response = requests.get(url, stream=True, timeout=10)
            response.close()

        # استخراج نام فایل
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


# تابع جدید: آپلود به FTP
def upload_to_ftp(file_url, file_name):
    try:
        ftp = FTP()
        ftp.connect(FTP_HOST_IRAN, 21)
        ftp.login(FTP_USER_IRAN, FTP_PASS_IRAN)
        ftp.cwd('/public_html/')  # مسیر پیش‌فرض

        # دانلود و آپلود همزمان
        with requests.get(file_url, stream=True) as r:
            r.raise_for_status()
            ftp.storbinary(f'STOR {file_name}', r.raw)

        ftp.quit()
        return f"http://{FTP_HOST_IRAN}/{file_name}"

    except Exception as e:
        logger.error(f"FTP upload error: {e}")
        return None


@bot.on_callback_query(filters.regex(r'^confirm_link_upload$|^cancel_link_upload$'))
async def handle_link_confirmation(client, callback_query):
    user_id = callback_query.from_user.id
    action = callback_query.data

    # مدیریت لغو آپلود
    if action == "cancel_link_upload":
        if user_id in pending_links:
            del pending_links[user_id]
        await callback_query.message.edit_text("❌ آپلود لغو شد")
        return

    # بررسی وجود اطلاعات فایل
    if user_id not in pending_links:
        return await callback_query.answer("اطلاعات فایل یافت نشد", show_alert=True)

    # بازیابی اطلاعات لینک
    link_data = pending_links[user_id]
    url = link_data["url"]
    file_name = link_data["file_name"]
    file_size = link_data["file_size"]

    # نمایش وضعیت اولیه آپلود
    message = await callback_query.message.edit_text("⏳ در حال آماده‌سازی...")

    # متغیرهای مدیریت پیشرفت
    last_update_time = time.time()
    last_percent = 0

    # تابع نمایش پیشرفت
    async def update_progress(uploaded, total, status="📤 در حال آپلود فایل..."):
        nonlocal last_update_time, last_percent

        # محاسبه درصد پیشرفت
        percent = (uploaded / total) * 100

        # بهینه‌سازی: فقط در صورت تغییر قابل توجه یا گذشت زمان آپدیت شود
        current_time = time.time()
        if (percent - last_percent < 5 and
                current_time - last_update_time < 1.0 and
                percent < 100):
            return

        # به‌روزرسانی زمان و درصد آخرین آپدیت
        last_update_time = current_time
        last_percent = percent

        # ساخت نوار پیشرفت
        progress_bar = "[" + "■" * int(percent / 10) + " " * (10 - int(percent / 10)) + "]"

        # محاسبه سرعت و زمان باقیمانده
        elapsed = current_time - start_time
        speed = uploaded / elapsed if elapsed > 0 else 0
        eta = (total - uploaded) / speed if speed > 0 else 0

        # متن وضعیت
        text = (
            f"{status}\n"
            f"{progress_bar} {percent:.1f}%\n"
            f"📦 {readable(uploaded)} از {readable(total)}\n"
            f"⚡ سرعت: {readable(speed)}/s\n"
            f"⏱ زمان باقیمانده: {format_time(eta)}"
        )

        # آپدیت پیام
        try:
            await message.edit_text(text)
        except Exception as e:
            logger.error(f"Error updating progress: {e}")

    # تابع کمکی برای آپدیت امن پیام
    async def safe_edit(text):
        try:
            await message.edit_text(text)
        except Exception as e:
            logger.error(f"Error editing message: {e}")

    # آپلود به سرور با نمایش پیشرفت
    try:
        # شروع تایمر
        start_time = time.time()

        # نمایش وضعیت شروع دانلود
        await safe_edit("⏳ در حال دریافت فایل از لینک...")

        # آپلود به سرور
        download_link = await asyncio.to_thread(
            upload_to_ftp_with_progress,
            url,
            file_name,
            lambda u, t: asyncio.run_coroutine_threadsafe(
                update_progress(u, t, "📥 در حال دریافت فایل از لینک..."),
                client.loop
            )
        )

        # بررسی موفقیت آمیز بودن آپلود
        if not download_link:
            await safe_edit("❌ خطا در آپلود فایل. لطفاً دوباره تلاش کنید.")
            return

        # نمایش پیام موفقیت
        success_text = (
            f"✅ آپلود با موفقیت انجام شد!\n\n"
            f"📝 نام فایل: `{file_name}`\n"
            f"📦 حجم: {readable(file_size)}\n"
            f"🔗 لینک مستقیم: [دانلود فایل]({download_link})"
        )

        await safe_edit(success_text)

    except Exception as e:
        logger.error(f"Upload error: {e}")
        await safe_edit("❌ خطای سیستمی در آپلود فایل رخ داد")

    finally:
        # حذف لینک از لیست انتظار
        if user_id in pending_links:
            del pending_links[user_id]

if __name__ == "__main__":
    print("🤖 ربات در حال اجراست...")
    bot.run()