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
import logger
from linktofile import FTP_HOST_IRAN, FTP_USER_IRAN, FTP_PASS_IRAN

global_convers = {}
pending_links = {}


bot = Client(
    "Link_service_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

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

@bot.on_message(filters.text & filters.regex("^📊 ترافیک باقیمانده$"))
async def return_terrafic(client, message):
    user_id = message.from_user.id
    traffic = return_traffic(user_id)
    await message.reply_text(f"{traffic}ترافیک باقی مانده شما: ")


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

def readable(size: float) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} GB"


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

    if action == "cancel_link_upload":
        if user_id in pending_links:
            del pending_links[user_id]
        await callback_query.message.edit_text("❌ آپلود لغو شد")
        return

    if user_id not in pending_links:
        return await callback_query.answer("اطلاعات فایل یافت نشد", show_alert=True)

    link_data = pending_links[user_id]
    url = link_data["url"]
    file_name = link_data["file_name"]
    file_size = link_data["file_size"]

    # نمایش وضعیت آپلود
    await callback_query.message.edit_text("⏳ در حال آپلود فایل... لطفا منتظر بمانید")

    # آپلود به سرور
    try:
        download_link = await asyncio.to_thread(
            upload_to_ftp,
            url,
            file_name
        )

        if download_link:
            # به‌روزرسانی ترافیک کاربر (پیاده‌سازی منطق کسر ترافیک)
            # decrase_traffic(user_id, file_size)

            await callback_query.message.edit_text(
                f"✅ آپلود با موفقیت انجام شد!\n"
                f"🔗 لینک مستقیم: [دانلود فایل]({download_link})\n"
                f"📝 نام فایل: `{file_name}`\n"
                f"📦 حجم: {readable(file_size)}",
                disable_web_page_preview=True
            )
        else:
            await callback_query.message.edit_text("❌ خطا در آپلود فایل. لطفا دوباره تلاش کنید.")

    except Exception as e:
        logger.error(f"Upload error: {e}")
        await callback_query.message.edit_text("❌ خطای سیستمی در آپلود فایل رخ داد")


if __name__ == "__main__":
    print("🤖 ربات در حال اجراست...")
    bot.run()