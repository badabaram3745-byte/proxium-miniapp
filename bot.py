# -*- coding: utf-8 -*-
"""
ربات فروش VPN (پروکسیوم)
نیازمند: python-telegram-bot >= 22.7  (پشتیبانی از دکمه رنگی style و icon_custom_emoji_id)
"""
import os, re, io, json, time, uuid, html, secrets, sqlite3, logging, datetime as dt
import httpx
import asyncio, hmac, hashlib, base64, urllib.parse  # ➕
from telegram import (Update, InlineKeyboardButton as IKB, InlineKeyboardMarkup as IKM,
                      ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove)
from telegram.constants import ParseMode
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler, MessageHandler,
                          ContextTypes, filters)
try:
    import jdatetime
except ImportError:
    jdatetime = None
try:
    import qrcode
except ImportError:
    qrcode = None

# ───────────────────────── تنظیمات اصلی ─────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "PUT_YOUR_TOKEN_HERE")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "123456789").replace(" ", "").split(",") if x}
# ➕ ادمین اصلی (فقط او می‌تواند ادمین اضافه/حذف کند)
MAIN_ADMIN_ID = 7363962357
ENV_ADMIN_IDS = set(ADMIN_IDS)  # ادمین‌های داخل تنظیمات هم ادمین اصلی حساب می‌شوند
ADMIN_IDS.add(MAIN_ADMIN_ID)
BOT_NAME = os.getenv("BOT_NAME", "پروکسیوم")
DB_PATH = os.getenv("DB_PATH", "bot.db")
RTL = os.getenv("RTL_BUTTONS", "1") == "1"      # دکمه اول هر ردیف سمت راست باشد
USER_PREFIX = os.getenv("USER_PREFIX", "px")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bot")

GREEN, RED, BLUE = "success", "danger", "primary"
# ➕ رنگ جداگانه برای هر دکمه (از پنل مدیریت > رنگ دکمه‌ها)
BTN_COLOR_MODES = {"orig": ("رنگ اورجینال", None), "green": ("سبز", GREEN), "red": ("قرمز", RED),
                   "blue": ("آبی", BLUE), "none": ("بی‌رنگ", None)}
BTN_GROUPS = {"pl": "دکمه‌های مدت (ماهه)", "bp": "دکمه‌های ردیف پلن (حجم/روز/قیمت)", "ta": "دکمه‌های مبلغ شارژ",
              "sv": "لیست اشتراک‌های کاربر", "inv": "دکمه‌های لوکیشن", "pv": "لیست پنل‌ها (ادمین)",
              "plv": "لیست پلن‌ها (ادمین)", "set": "دکمه‌های تنظیمات (ادمین)", "tg": "دکمه‌های روشن/خاموش (ادمین)",
              "pn": "نوع پنل (ادمین)", "soon": "پنل‌های به‌زودی", "tx": "لیست متن‌ها (ادمین)",
              "em": "لیست ایموجی‌ها (ادمین)", "noop": "عنوان‌ها و برچسب‌های صفحه", "url": "دکمه‌های لینک"}
# ➕ گروه رنگ دکمه‌های جدید (تمدید / کد تخفیف)
BTN_GROUPS.update({"rnp": "لیست پلن‌های تمدید", "dcv": "لیست کدهای تخفیف (ادمین)", "dcp": "دکمه‌های درصد تخفیف (ادمین)"})
try:
    _SRC = open(os.path.abspath(__file__), encoding="utf-8").read()
except Exception:
    _SRC = ""
BTN_NAMES = sorted(set(re.findall(r'btn\("([^"{]+)"', _SRC))) + list(dict.fromkeys(BTN_GROUPS.values()))

def color_key(text, data=None, url=None):
    if text in BTN_NAMES[:len(BTN_NAMES) - len(BTN_GROUPS)]: return text
    if url: return BTN_GROUPS["url"]
    pre = (data or "noop").split(":")[0]
    return BTN_GROUPS.get(pre, BTN_GROUPS["noop"])

# ───────────────────────── ایموجی‌ها (پریمیوم + جایگزین) ─────────────────────────
# آیدی ایموجی پریمیوم هر کلید از داخل پنل ادمین > ایموجی‌های پریمیوم ست می‌شود
EMOJI = {
    "bot": "⚡️", "fire": "♨️", "hello": "👋", "buy": "🛍", "subs": "✅", "wallet": "🤑",
    "test": "🆓", "support": "💬", "channel": "📣", "account": "👤", "more": "😎",
    "admin": "🛠", "back": "🔙", "m1": "1️⃣", "m3": "3️⃣", "m6": "6️⃣", "m12": "🔟",
    "tariff1": "1️⃣", "tariff3": "3️⃣", "tariff6": "6️⃣",
    "all": "🔥", "suggest": "🤔", "gift": "🎁", "price": "💲", "volume": "🟢", "time": "⏳",
    "shop": "🏪", "card": "💳", "ok": "✅", "no": "❌", "panel": "🔌", "plan": "📦",
    "ban": "🚫", "unban": "♻️", "text": "✏️", "stats": "📊", "search": "🔎", "bridge": "🌉",
    "bc": "📢", "pin": "📍", "point": "👇", "link": "🔗", "qr": "🔳", "addbal": "➕",
    "subbal": "➖", "emoji": "😀", "settings": "⚙️", "help": "📖", "rules": "📜",
    "ref": "🤝", "phone": "📱", "chest": "🧰", "bag": "🛍",
    "layout": "🧩", "searchsvc": "🔎", "cleanup": "🧹", "layout1": "1️⃣", "layout2": "2️⃣", "layout3": "3️⃣", "original": "♻️",
    "startlayout": "🏠", "morelayout": "😎", "trx": "🧾", "today": "📅", "yesterday": "⏪", "last7": "7️⃣", "last30": "📆", "alltrx": "📚",
    "ip": "📍", "usage": "📊", "mysettings": "⚙️", "remind": "🔔", "transfer": "🔁", "ipbox": "🛡",  # ➕
}
# ➕ ایموجی دکمه‌های جدید (تمدید، حذف، تغییر نام، کد تخفیف، تراکنش‌ها)
EMOJI.update({"renew": "🔄", "delsrv": "🗑", "rename": "📝", "discount": "🎟", "trx": "🧾", "ticket": "🎫", "direct": "👤"})

# ───────────────────────── متن‌های قابل ویرایش ─────────────────────────
# متغیرها: {BOT} {USER} {ID} {BALANCE} {PRICE} {GB} {DAYS} {LINK} {SERVICES} {DATE} ...
# ایموجی پریمیوم داخل متن: {E:کلید}  مثل {E:bot}
TEXTS = {
    "start": ("استارت",
        "{E:fire} <b>{BOT}</b> {E:bot}\n"
        "سلام <b>{USER}</b> عزیز {E:hello}\n"
        "به پنل مدیریت سرویس‌های VPN خوش آمدید.\n\n"
        "<blockquote>{E:card} موجودی کیف پول: <b>{BALANCE}</b> تومان\n"
        "{E:plan} سرویس‌های فعال: <b>{SERVICES}</b> سرویس\n"
        "🆔 شناسه کاربری: <code>{ID}</code>\n"
        "🕒 آخرین ورود: {DATE}</blockquote>\n\n"
        "<b>یکی از گزینه‌های منو را انتخاب کنید</b> {E:point}"),
    "buy_intro": ("انتخاب مدت",
        "{E:pin} <b>مدت سرویس را انتخاب کن</b>\n\n"
        "بسته‌ها را مقایسه کنید و از کلیدهای زیر، مدت دلخواه را انتخاب کنید. "
        "قیمت دقیق هر بسته پس از انتخاب مدت نمایش داده می‌شود."),
    "plans": ("لیست پلن‌ها",
        "{E:bag} لطفاً سرویس خود را انتخاب کنید.\n\n{E:chest} موجودی فعلی شما: <b>{BALANCE}</b> تومان"),
    "invoice": ("فاکتور",
        "🧾 <b>فاکتور خرید</b>\n<blockquote>{E:volume} حجم: <b>{GB} گیگ</b>\n{E:time} مدت: <b>{DAYS} روز</b>\n"
        "📍 لوکیشن: <b>{LOCATION}</b>\n{E:price} مبلغ: <b>{PRICE}</b> تومان\n"
        "{E:card} موجودی شما: <b>{BALANCE}</b> تومان</blockquote>\n\nبرای پرداخت روی دکمه زیر بزنید."),
    "delivery": ("تحویل سرویس",
        "{E:ok} <b>سرویس شما با موفقیت ساخته شد</b>\n<blockquote>👤 نام سرویس: <code>{NAME}</code>\n"
        "{E:volume} حجم: {GB} گیگ\n{E:time} مدت: {DAYS} روز\n{E:price} مبلغ: {PRICE} تومان</blockquote>\n\n"
        "{E:link} لینک اتصال:\n<code>{LINK}</code>"),
    "account": ("حساب کاربری / کیف پول",
        "{E:account} <b>حساب کاربری</b>\n<blockquote>🆔 شناسه کاربری: <code>{ID}</code>\n"
        "👤 نام: <b>{USER}</b>\n{E:phone} شماره تماس: {PHONE}\n👥 گروه کاربری: <b>{GROUP}</b>\n"
        "🕒 زمان ثبت‌نام: {JOINED}\n🎟 کد معرف: <code>{REF}</code></blockquote>\n\n"
        "<b>خلاصه فعالیت حساب</b>\n<blockquote>{E:wallet} موجودی کیف پول: <b>{BALANCE}</b> تومان\n"
        "🛒 سرویس‌های خریداری‌شده: <b>{SERVICES}</b> عدد\n🧾 فاکتورهای پرداخت‌شده: <b>{INVOICES}</b> عدد\n"
        "{E:ref} زیرمجموعه‌ها: <b>{REFS}</b> نفر</blockquote>\n\n🕒 آخرین مشاهده: {DATE}"),
    "topup": ("افزایش موجودی", "{E:wallet} <b>افزایش موجودی</b>\n\nمبلغ مورد نظر را انتخاب کنید یا مبلغ دلخواه وارد کنید."),
    "topup_card": ("کارت به کارت",
        "{E:card} <b>پرداخت کارت به کارت</b>\n<blockquote>مبلغ: <b>{PRICE}</b> تومان\n"
        "شماره کارت: <code>{CARD}</code>\nبه نام: <b>{OWNER}</b></blockquote>\n\n"
        "بعد از واریز، <b>عکس رسید</b> را همین‌جا ارسال کنید."),
    "receipt_wait": ("رسید دریافت شد", "{E:ok} رسید شما دریافت شد و پس از بررسی ادمین، موجودی شارژ می‌شود."),
    "gift": ("شارژ ویژه با هدیه",
        "{E:gift} <b>شارژ ویژه با هدیه</b>\n\nبا شارژ <b>{MIN}</b> تومان یا بیشتر، <b>{PERCENT}%</b> "
        "هدیه روی موجودی‌تان دریافت کنید!"),
    "help": ("راهنما", "{E:help} <b>راهنما</b>\n\n۱. از «خرید اشتراک» مدت و حجم را انتخاب کنید.\n"
        "۲. لینک را در اپ v2rayNG / Streisand / Hiddify وارد کنید.\n۳. در صورت مشکل به پشتیبانی پیام دهید."),
    "rules": ("قوانین", "{E:rules} <b>قوانین</b>\n\n• استفاده هم‌زمان بیش از حد مجاز ممنوع است.\n"
        "• هزینه پس از تحویل سرویس قابل بازگشت نیست."),
    "test_delivery": ("تحویل اکانت تست",
        "{E:test} <b>اکانت تست رایگان شما آماده است</b>\n<blockquote>{E:volume} حجم: {GB} گیگ\n"
        "{E:time} مدت: {DAYS} روز</blockquote>\n\n{E:link} لینک:\n<code>{LINK}</code>"),
    "test_mid": ("یادآوری میان‌دوره تست",
        "سلام {USER} {E:hello}\nاز اکانت تست راضی بودی؟ نصف زمان تستت گذشته؛ برای ادامه همین الان سرویس بخر {E:fire}"),
    "test_end": ("پایان تست", "⌛️ اکانت تست شما تمام شد. با خرید اشتراک، بدون قطعی ادامه بده {E:bot}"),
    "expire_soon": ("یادآوری انقضا", "⏰ سرویس <code>{NAME}</code> کمتر از ۲۴ ساعت دیگر منقضی می‌شود."),
    "banned": ("کاربر مسدود", "🚫 حساب شما مسدود شده است."),
    "no_balance": ("موجودی ناکافی", "{E:no} موجودی کافی نیست. مبلغ: {PRICE} | موجودی: {BALANCE} تومان"),
    "subs_empty": ("بدون اشتراک", "شما هنوز اشتراکی ندارید. از «خرید اشتراک» شروع کنید {E:buy}"),
    "more": ("سایر امکانات", "{E:more} <b>سایر امکانات</b>"),
    "ref": ("زیرمجموعه‌گیری", "{E:ref} <b>زیرمجموعه‌گیری</b>\n\nبا لینک زیر دوستانت را دعوت کن و از هر شارژشان "
        "<b>{PERCENT}%</b> هدیه بگیر:\n<code>{LINK}</code>"),
    # ➕ اطلاعات IP
    "ip_intro": ("اطلاعات IP من",
        "{E:ip} <b>اطلاعات IP من</b>\n\n📍 با بازکردن دکمه زیر، IP عمومی اتصال فعلی شما بررسی می‌شود و نتیجه "
        "داخل همین ربات ارسال خواهد شد.\n\n<blockquote>⚠️ توجه! اطلاعات IP در دیتابیس ربات ذخیره نمی‌شود. "
        "برای تشخیص موقعیت تقریبی و اپراتور، IP به سرویس ipwho.is ارسال می‌شود!</blockquote>"),
    "ip_result": ("نتیجه اطلاعات IP",
        "{E:ipbox} <b>اطلاعات IP فعلی شما</b>\n\n<blockquote>✅ آدرس IP: <code>{IP}</code>\n⚠️ نسخه: <b>{VER}</b>\n"
        "{FLAG} کشور: <b>{COUNTRY}</b>\n🌙 استان/منطقه: <b>{REGION}</b>\n⚪️ شهر: <b>{CITY}</b>\n"
        "📡 اپراتور/سازمان: <b>{ISP}</b>\n🔢 شماره ASN: <code>{ASN}</code>\n🕒 منطقه زمانی: <b>{TZ}</b></blockquote>\n\n"
        "<blockquote>🟩 موقعیت نمایش‌داده‌شده تقریبی است و براساس IP محاسبه می‌شود.</blockquote>"),
}

# ➕ متن‌های بخش‌های جدید (قابل ویرایش از پنل مدیریت > ویرایش متن‌ها)
TEXTS.update({
    "discount_ask": ("درخواست کد تخفیف",
        "{E:discount} <b>کد تخفیف</b>\n\nلطفاً کد تخفیف خود را وارد کنید {E:point}"),
    "discount_ok": ("کد تخفیف اعمال شد",
        "<blockquote>{E:discount} کد تخفیف <code>{CODE}</code> اعمال شد\n{E:price} قیمت اصلی: <s>{ORIG}</s> تومان\n"
        "🔻 تخفیف: <b>{PERCENT}%</b> ({DISCOUNT} تومان)\n{E:ok} مبلغ نهایی: <b>{PRICE}</b> تومان</blockquote>"),
    "discount_bad": ("کد تخفیف نامعتبر", "{E:no} {REASON}\nدوباره کد را بفرستید یا برگردید."),
    "renew_plans": ("انتخاب پلن تمدید",
        "{E:renew} <b>تمدید سرویس</b> <code>{NAME}</code>\n\nپلن تمدید را انتخاب کنید.\n"
        "<blockquote>با تمدید، حجم سرویس به حجم پلن جدید ریست می‌شود و روزهای پلن به زمان باقی‌مانده اضافه می‌شود.</blockquote>\n"
        "{E:chest} موجودی فعلی شما: <b>{BALANCE}</b> تومان"),
    "renew_invoice": ("فاکتور تمدید",
        "🧾 <b>فاکتور تمدید</b>\n<blockquote>👤 سرویس: <code>{NAME}</code>\n{E:volume} حجم جدید: <b>{GB} گیگ</b>\n"
        "{E:time} مدت: <b>{DAYS} روز</b>\n📅 انقضای جدید: <b>{EXPIRE}</b>\n{E:price} مبلغ: <b>{PRICE}</b> تومان\n"
        "{E:card} موجودی شما: <b>{BALANCE}</b> تومان</blockquote>\n\nبرای تمدید روی دکمه زیر بزنید."),
    "renew_done": ("تمدید موفق",
        "{E:ok} <b>سرویس با موفقیت تمدید شد</b>\n<blockquote>👤 سرویس: <code>{NAME}</code>\n{E:volume} حجم: {GB} گیگ\n"
        "{E:time} انقضای جدید: {EXPIRE}\n{E:price} مبلغ: {PRICE} تومان</blockquote>"),
    "delete_confirm": ("تأیید حذف سرویس",
        "{E:delsrv} <b>حذف سرویس</b>\n\nآیا مطمئنی سرویس <code>{NAME}</code> حذف شود؟\n"
        "<blockquote>⚠️ سرویس هم از ربات و هم از پنل پاک می‌شود و قابل برگشت نیست.</blockquote>"),
    "delete_done": ("سرویس حذف شد", "{E:ok} سرویس <code>{NAME}</code> از ربات و پنل حذف شد."),
    "rename_ask": ("درخواست نام جدید سرویس",
        "{E:rename} <b>تغییر نام سرویس</b>\n\nنام فعلی: <code>{NAME}</code>\nنام جدید را بفرستید (حداکثر ۳۲ کاراکتر):"),
    "rename_done": ("تغییر نام موفق", "{E:ok} نام سرویس به <b>{NAME}</b> تغییر کرد."),
    "trx_head": ("عنوان تراکنش‌ها (ادمین)", "{E:trx} <b>تراکنش‌ها | {PERIOD}</b>"),
    "dc_admin": ("عنوان کدهای تخفیف (ادمین)",
        "{E:discount} <b>کدهای تخفیف</b>\nروی هر کد بزن برای مدیریت، یا کد جدید بساز."),
})

DEFAULT_SETTINGS = {
    "card_number": "6037-0000-0000-0000", "card_owner": "نام صاحب کارت",
    "test_enabled": "1", "test_gb": "1", "test_days": "1", "test_panel": "",
    "gift_min": "500000", "gift_percent": "10", "ref_percent": "5",
    "support_url": "https://t.me/telegram", "channel_url": "https://t.me/telegram",
    "premium_on": "1", "bridge_url": "", "start_sticker": "", "suggest_plan": "",
    "extra_admins": "",
    "button_layout": "1",
}
SETTING_TITLES = {
    "card_number": "شماره کارت", "card_owner": "نام صاحب کارت", "test_gb": "حجم تست (گیگ)",
    "test_days": "مدت تست (روز)", "test_panel": "آیدی پنل تست", "gift_min": "حداقل شارژ هدیه",
    "gift_percent": "درصد هدیه", "ref_percent": "درصد زیرمجموعه", "support_url": "لینک پشتیبانی",
    "channel_url": "لینک کانال", "bridge_url": "آدرس پل (پروکسی هسته واسط)",
    "start_sticker": "استیکر استارت (استیکر بفرست)", "suggest_plan": "آیدی پلن پیشنهادی",
}
# ➕ آدرس عمومی سرور اطلاعات IP
DEFAULT_SETTINGS["ip_web_url"] = ""
SETTING_TITLES["ip_web_url"] = "آدرس سرور اطلاعات IP (مثل https://ip.domain.com یا http://IP:8088)"
IP_WEB_HOST = os.getenv("IP_WEB_HOST", "0.0.0.0")
IP_WEB_PORT = int(os.getenv("IP_WEB_PORT", "8088"))
IP_TRUST_PROXY = os.getenv("IP_TRUST_PROXY", "0") == "1"   # اگر پشت nginx/Cloudflare هستی 1 بگذار
BOT_REF = {"bot": None, "username": "", "srv": None, "last": {}}

PANEL_TYPES = [("marzban", "مرزبان"), ("marzneshin", "مرزنشین"), ("pasarguard", "پاسارگارد"),
               ("sanaei", "ثنایی / 3x-UI"), ("alireza", "علیرضا"), ("xui", "X-UI عمومی"),
               ("manual", "فروش دستی")]
SOON_PANELS = ["هیدیفای", "Guard", "WGDashboard", "s-ui", "IBSNG", "میکروتیک"]
XUI_PREFIX = {"sanaei": "/panel/api/inbounds", "alireza": "/xui/API/inbounds", "xui": "/xui/API/inbounds"}
EXTRA_HINT = {
    "marzban": "پروکسی‌ها به صورت JSON مثل {\"vless\":{}} (یا - برای پیش‌فرض)",
    "pasarguard": "آیدی گروه‌ها با کاما مثل 1,2",
    "marzneshin": "آیدی سرویس‌ها با کاما مثل 1,2",
    "sanaei": "آیدی اینباند|آدرس ساب|آدرس سرور  مثل  1|https://sub.domain.com:2096/sub  (فقط آیدی اینباند هم کافی است، بقیه خودکار)",
    "alireza": "آیدی اینباند|آدرس ساب", "xui": "آیدی اینباند|آدرس ساب",
}

# ───────────────────────── دیتابیس ─────────────────────────
CON = sqlite3.connect(DB_PATH, check_same_thread=False)
CON.row_factory = sqlite3.Row

def q(sql, args=(), one=False):
    rows = CON.execute(sql, args).fetchall()
    return (rows[0] if rows else None) if one else rows

def ex(sql, args=()):
    cur = CON.execute(sql, args); CON.commit(); return cur.lastrowid

def init_db():
    CON.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT, username TEXT, phone TEXT,
        balance INTEGER DEFAULT 0, banned INTEGER DEFAULT 0, grp TEXT DEFAULT 'عادی', created INTEGER,
        last_seen INTEGER, ref_by INTEGER, test_used INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS plans(id INTEGER PRIMARY KEY AUTOINCREMENT, months INTEGER, gb INTEGER,
        days INTEGER, price INTEGER, active INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS panels(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, ptype TEXT, url TEXT,
        user TEXT, password TEXT, extra TEXT, active INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS services(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, plan_id INTEGER,
        panel_id INTEGER, username TEXT, link TEXT, sub TEXT, gb INTEGER, days INTEGER, price INTEGER,
        created INTEGER, expire INTEGER, is_test INTEGER DEFAULT 0, mid_sent INTEGER DEFAULT 0,
        end_sent INTEGER DEFAULT 0, status TEXT DEFAULT 'active');
    CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER,
        bonus INTEGER DEFAULT 0, photo TEXT, status TEXT DEFAULT 'pending', created INTEGER);
    CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY, v TEXT);
    """)
    for k, v in DEFAULT_SETTINGS.items():
        ex("INSERT OR IGNORE INTO settings(k,v) VALUES(?,?)", (k, v))
    if not q("SELECT 1 FROM plans LIMIT 1"):
        for m, gb, d, p in [(1, 30, 30, 55000), (1, 50, 30, 82500), (1, 100, 30, 165000), (1, 150, 30, 247500),
                            (3, 100, 90, 222750), (3, 150, 90, 334125), (3, 200, 90, 445500),
                            (6, 25, 180, 74250), (6, 50, 180, 148500), (6, 100, 180, 297000)]:
            ex("INSERT INTO plans(months,gb,days,price) VALUES(?,?,?,?)", (m, gb, d, p))

def S(k):
    r = q("SELECT v FROM settings WHERE k=?", (k,), True)
    return r["v"] if r else DEFAULT_SETTINGS.get(k, "")

def set_S(k, v):
    ex("INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, str(v)))

def get_user(uid):
    return q("SELECT * FROM users WHERE id=?", (uid,), True)

# ───────────────────────── ابزارها ─────────────────────────
def money(n): return f"{int(n):,}"

def jdate(ts=None):
    ts = ts or time.time()
    if jdatetime:
        return jdatetime.datetime.fromtimestamp(ts).strftime("%Y/%m/%d - %H:%M")
    return dt.datetime.fromtimestamp(ts).strftime("%Y/%m/%d - %H:%M")

def emoji_id(key):
    if S("premium_on") != "1": return None
    return S("emoji:" + key) or None

def E(key):
    fb = EMOJI.get(key, "")
    eid = emoji_id(key)
    if eid: fb = S("emoji_fb:" + key) or fb  # ➕ ایموجی اصلی همان ایموجی پریمیوم
    return f'<tg-emoji emoji-id="{eid}">{fb or "⭐️"}</tg-emoji>' if eid else fb

def render(key, **kw):
    t = S("text:" + key) or TEXTS[key][1]
    kw.setdefault("BOT", html.escape(BOT_NAME))
    for k, v in kw.items():
        t = t.replace("{" + k + "}", str(v))
    return re.sub(r"\{E:(\w+)\}", lambda m: E(m.group(1)), t)

def btn(text, data=None, style=None, ek=None, url=None):
    """دکمه رنگی + ایموجی پریمیوم. اگر آیدی ایموجی ست نشده باشد، ایموجی معمولی کنار متن می‌آید."""
    kw = {}
    if style: kw["style"] = style
    _c = S("color:" + color_key(text, data, url))  # ➕ رنگ اختصاصی همین دکمه
    if _c == "none": kw.pop("style", None)
    elif BTN_COLOR_MODES.get(_c, (0, None))[1]: kw["style"] = BTN_COLOR_MODES[_c][1]
    eid = emoji_id(ek) if ek else None
    if eid: kw["icon_custom_emoji_id"] = eid
    label = text if (eid or not ek) else f"{text} {EMOJI.get(ek, '')}".strip()
    try:
        if url: return IKB(label, url=url, **kw)
        return IKB(label, callback_data=data or "noop", **kw)
    except TypeError:  # ➕ نسخه قدیمی‌تر کتابخانه: ارسال مستقیم فیلدها به API
        if url: return IKB(label, url=url, api_kwargs=kw)
        return IKB(label, callback_data=data or "noop", api_kwargs=kw)

def row(*b):
    """چیدمان قابل تنظیم دکمه‌ها؛ حالت ۱ همان رفتار قبلی است."""
    b = [x for x in b if x is not None]
    layout = S("button_layout") or "1"
    if layout == "1":
        return list(reversed(b)) if RTL else b
    if layout == "2":
        return b if RTL else list(reversed(b))
    if layout == "3":
        # چیدمان سوم: دکمه اول به انتهای ردیف می‌رود.
        return (b[1:] + b[:1]) if len(b) > 1 else b
    # حالت ۴: اورجینال، مستقل از تنظیمات RTL.
    return list(reversed(b)) if RTL else b

def section_row(section, *b):
    """چیدمان مستقل برای منوی استارت و سایر امکانات."""
    b = [x for x in b if x is not None]
    layout = S("layout:" + section) or "4"
    if layout == "1":
        return list(reversed(b)) if RTL else b
    if layout == "2":
        return b if RTL else list(reversed(b))
    if layout == "3":
        return (b[1:] + b[:1]) if len(b) > 1 else b
    return list(reversed(b)) if RTL else b

def is_admin(uid): return uid in ADMIN_IDS

# ➕ مدیریت ادمین‌ها
def is_main_admin(uid): return uid == MAIN_ADMIN_ID or uid in ENV_ADMIN_IDS

def extra_admins():
    return [int(x) for x in S("extra_admins").replace(" ", "").split(",") if x.strip().isdigit()]

def load_admins():
    ADMIN_IDS.add(MAIN_ADMIN_ID)
    for a in extra_admins(): ADMIN_IDS.add(a)

def save_admins(ids):
    set_S("extra_admins", ",".join(str(i) for i in sorted(set(ids)) if i != MAIN_ADMIN_ID))

async def admin_admins(update):
    ids = extra_admins()
    lines = [f"👑 ادمین اصلی: <code>{MAIN_ADMIN_ID}</code>"]
    lines += [f"• <code>{i}</code> ({html.escape((get_user(i) or {'name': None})['name'] or '-')})" for i in ids] or ["(ادمین دیگری اضافه نشده)"]
    kb = [row(btn("افزودن ادمین", "adm:add", GREEN, "addbal"))]
    kb += [row(btn(f"حذف {i}", f"adm:del:{i}", RED, "no")) for i in ids]
    await show(update, "👥 <b>مدیریت ادمین‌ها</b>\n<blockquote>" + "\n".join(lines) + "</blockquote>", kb + admin_back())

# ➕ ایموجی پریمیوم با کد عددی
def parse_emoji_ids(txt):
    """کد عددی custom emoji را از متن درمی‌آورد؛ کد فارسی/لاتین و جداکننده‌ها را قبول می‌کند."""
    txt = (txt or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    # custom_emoji_id تلگرام یک شناسه عددی است، نه file_id یا message_id.
    return re.findall(r"(?<!\d)[0-9]{15,20}(?!\d)", txt)

async def check_emoji(bot, eid):
    """اعتبارسنجی واقعی custom_emoji_id با Telegram Bot API.
    خطای شبکه/دسترسی نباید به‌اشتباه کد را معتبر اعلام کند.
    """
    eid = str(eid or "").strip()
    if not re.fullmatch(r"[0-9]{15,20}", eid):
        return False, None
    try:
        st = await bot.get_custom_emoji_stickers([eid])
        if st and getattr(st[0], "type", None) == "custom_emoji":
            return True, (st[0].emoji or "⭐️")
        return False, None
    except Exception as e:
        log.warning("custom emoji validation failed for %s: %s", eid, e)
        return False, None

def strip_premium(text, markup):
    """اگر تلگرام ایموجی پریمیوم را قبول نکرد، نسخه ساده (بدون پریمیوم) ساخته می‌شود."""
    text = re.sub(r'<tg-emoji emoji-id="[^"]*">(.*?)</tg-emoji>', r"\1", text or "", flags=re.S)
    if markup:
        try:
            d = markup.to_dict()
            for r_ in d.get("inline_keyboard", []):
                for b_ in r_: b_.pop("icon_custom_emoji_id", None)
            markup = IKM.de_json(d, None)
        except Exception:
            pass
    return text, markup

COLOR_ICON = {"orig": "⚪️", "green": "🟢", "red": "🔴", "blue": "🔵", "none": "⚫️"}
CLR_PAGE = 16

def color_list_kb(page=0):
    names = BTN_NAMES; pages = max(1, (len(names) + CLR_PAGE - 1) // CLR_PAGE); page = max(0, min(page, pages - 1))
    items = [IKB(f"{COLOR_ICON.get(S('color:' + n) or 'orig', '⚪️')} {n}", callback_data=f"cb:{i}:{page}")
             for i, n in enumerate(names)][page * CLR_PAGE:(page + 1) * CLR_PAGE]
    kb = [row(*items[i:i + 2]) for i in range(0, len(items), 2)]
    nav = [IKB("◀️ قبلی", callback_data=f"cp:{page - 1}") if page > 0 else None,
           IKB(f"{page + 1}/{pages}", callback_data="noop"),
           IKB("بعدی ▶️", callback_data=f"cp:{page + 1}") if page + 1 < pages else None]
    kb.append(row(*nav))
    kb.append([IKB("♻️ ریست رنگ همه دکمه‌ها", callback_data="cr")])
    return kb + admin_back()

def color_pick_kb(i, page):
    cur = S("color:" + BTN_NAMES[i]) or "orig"
    kb = [[IKB(("✅ " if k == cur else "") + COLOR_ICON[k] + " " + v[0], callback_data=f"cs:{i}:{k}:{page}",
               **({"api_kwargs": {"style": v[1]}} if v[1] else {}))] for k, v in BTN_COLOR_MODES.items()]
    return kb + [[IKB("🔙 بازگشت", callback_data=f"cp:{page}")]]

# ➕ ایموجی پریمیوم: خواندن خود ایموجی از پیام
def premium_ids(m):
    ents = list(m.entities or []) + list(m.caption_entities or [])
    return [e.custom_emoji_id for e in ents if e.type == "custom_emoji"]

def entity_fb(m, eid):
    for e in list(m.entities or []):
        if e.type == "custom_emoji" and e.custom_emoji_id == eid:
            try: return m.parse_entity(e) or "⭐️"
            except Exception: break
    for e in list(m.caption_entities or []):
        if e.type == "custom_emoji" and e.custom_emoji_id == eid:
            try: return m.parse_caption_entity(e) or "⭐️"
            except Exception: break
    return "⭐️"

def premium_by_line(m):
    """{شماره خط: (آیدی, ایموجی)} برای ثبت گروهی"""
    text = m.text or m.caption or ""; ents = m.entities if m.text else m.caption_entities
    raw = text.encode("utf-16-le"); out = {}
    for e in ents or []:
        if e.type != "custom_emoji": continue
        line = raw[:e.offset * 2].decode("utf-16-le", "ignore").count("\n")
        fb = raw[e.offset * 2:(e.offset + e.length) * 2].decode("utf-16-le", "ignore") or "⭐️"
        out.setdefault(line, (e.custom_emoji_id, fb))
    return out

def emoji_pick_kb():
    keys = list(EMOJI)
    kb = [[IKB(f"{EMOJI[k]} {k}", callback_data=f"eq:{k}") for k in keys[i:i + 3]] for i in range(0, len(keys), 3)]
    return kb + admin_back("a:emoji")

# ➕ اطلاعات IP (وب‌سرور داخلی ربات)
def ip_sig(uid, exp):
    return hmac.new(BOT_TOKEN.encode(), f"{uid}:{exp}".encode(), hashlib.sha256).hexdigest()[:40]

def ip_link(uid):
    base = (S("ip_web_url") or "").strip().rstrip("/")
    if not base: return None
    if not base.startswith("http"): base = "https://" + base
    exp = int(time.time()) + 3600
    return f"{base}/ip-info?uid={uid}&exp={exp}&sig={ip_sig(uid, exp)}"

def _ip_page(ok):
    u = BOT_REF.get("username") or ""
    back = f"https://t.me/{u}" if u else "tg://"
    title = "اطلاعات ارسال شد" if ok else "لینک نامعتبر یا منقضی شده"
    sub = "نتیجه بررسی داخل ربات برای شما فرستاده شد." if ok else "دوباره از داخل ربات روی «اطلاعات IP من» بزنید."
    icon, col = ("✓", "#22c55e") if ok else ("✕", "#ef4444")
    return f"""<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#0b1120;
font-family:Tahoma,Vazirmatn,sans-serif;color:#fff}}.c{{width:84%;max-width:420px;background:#111a2e;border:1px solid #1f2a44;
border-radius:28px;padding:44px 26px;text-align:center}}.i{{width:84px;height:84px;margin:0 auto 22px;border-radius:22px;
background:#13302c;color:{col};font-size:52px;line-height:84px}}h1{{font-size:22px;margin:0 0 16px}}p{{color:#9aa4b8;margin:0 0 30px}}
a{{display:block;background:{col};color:#06150c;text-decoration:none;font-weight:bold;padding:16px;border-radius:18px;font-size:18px}}</style>
</head><body><div class="c"><div class="i">{icon}</div><h1>{title}</h1><p>{sub}</p><a href="{back}">بازگشت به ربات</a></div></body></html>"""

async def ip_send_result(uid, ip):
    bot = BOT_REF.get("bot")
    if not bot: return
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            j = (await c.get(f"https://ipwho.is/{ip}", params={"lang": "en"})).json()
    except Exception as e:
        log.warning("ipwho %s", e); j = {"success": False}
    kb = IKM([row(btn("بازگشت به سایر امکانات", "more", RED, "back"))])
    if not j.get("success"):
        return await bot.send_message(uid, f"❌ دریافت اطلاعات IP <code>{html.escape(ip)}</code> ممکن نشد.",
                                      parse_mode=ParseMode.HTML, reply_markup=kb)
    con, tz, fl = j.get("connection") or {}, j.get("timezone") or {}, j.get("flag") or {}
    e_ = lambda v: html.escape(str(v or "-"))
    text = render("ip_result", IP=e_(j.get("ip") or ip), VER=e_(j.get("type")), COUNTRY=e_(j.get("country")),
                  FLAG=fl.get("emoji") or "🏳", REGION=e_(j.get("region")), CITY=e_(j.get("city")),
                  ISP=e_(con.get("org") or con.get("isp")), ASN=e_(f"AS{con['asn']}" if con.get("asn") else "-"),
                  TZ=e_(tz.get("id")))
    try:
        await bot.send_message(uid, text, parse_mode=ParseMode.HTML, reply_markup=kb)
    except Exception:
        t2, k2 = strip_premium(text, kb)
        await bot.send_message(uid, t2, parse_mode=ParseMode.HTML, reply_markup=k2)

async def _ip_http(reader, writer):
    try:
        head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 10)
        lines = head.decode("latin-1").split("\r\n")
        parts = lines[0].split(" ")
        hdr = {}
        for l in lines[1:]:
            if ":" in l:
                k, v = l.split(":", 1); hdr[k.strip().lower()] = v.strip()
        peer = (writer.get_extra_info("peername") or ("",))[0]
        ip = peer
        if IP_TRUST_PROXY or peer in ("127.0.0.1", "::1"):
            ip = (hdr.get("cf-connecting-ip") or hdr.get("x-real-ip") or
                  hdr.get("x-forwarded-for", "").split(",")[0].strip() or peer)
        if ip.startswith("::ffff:"): ip = ip[7:]
        u = urllib.parse.urlsplit(parts[1] if len(parts) > 1 else "/")
        qs = dict(urllib.parse.parse_qsl(u.query))
        status, ok = "200 OK", False
        if u.path.rstrip("/").endswith("ip-info"):
            try:
                uid, exp = int(qs.get("uid", "0")), int(qs.get("exp", "0"))
                ok = exp > time.time() and hmac.compare_digest(qs.get("sig", ""), ip_sig(uid, exp))
            except Exception:
                ok = False
            if ok and time.time() - BOT_REF["last"].get(uid, 0) > 10:
                BOT_REF["last"][uid] = time.time()
                try: await ip_send_result(uid, ip)
                except Exception as e: log.warning("ip send %s", e)
            body = _ip_page(ok)
        else:
            status, body = "404 Not Found", "<h1>404</h1>"
        data = body.encode("utf-8")
        writer.write(f"HTTP/1.1 {status}\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {len(data)}\r\n"
                     "Cache-Control: no-store\r\nConnection: close\r\n\r\n".encode() + data)
        await writer.drain()
    except Exception as e:
        log.debug("ip http %s", e)
    finally:
        try: writer.close()
        except Exception: pass

async def ip_server_start(app):
    BOT_REF["bot"] = app.bot
    try: BOT_REF["username"] = (await app.bot.get_me()).username or ""
    except Exception: pass
    try:
        BOT_REF["srv"] = await asyncio.start_server(_ip_http, IP_WEB_HOST, IP_WEB_PORT)
        log.info("ip-info server on %s:%s", IP_WEB_HOST, IP_WEB_PORT)
    except Exception as e:
        log.warning("ip-info server failed: %s", e)

# ➕ پنل‌ها: ساخت لینک کانفیگ و ساب
async def _sub_links(sub):
    """کانفیگ‌ها را از خود لینک ساب می‌خواند (برای پاسارگارد/ثنایی وقتی لینک مستقیم برنگردد)."""
    try:
        async with httpx.AsyncClient(timeout=20, verify=False, follow_redirects=True, proxy=S("bridge_url") or None) as c:
            r = await c.get(sub, headers={"User-Agent": "v2rayNG/1.8.19"})
        t = r.text.strip()
        if "://" not in t:
            t = base64.b64decode(t + "=" * (-len(t) % 4)).decode("utf-8", "ignore")
        return [l.strip() for l in t.splitlines()
                if re.match(r"^(vless|vmess|trojan|ss|hysteria2|hy2|tuic|wireguard)://", l.strip())]
    except Exception as e:
        log.warning("sub links %s: %s", sub, e); return []

async def _mz_create(c, t, body, h):
    r = await c.post("/api/user", json=body, headers=h)
    if t == "pasarguard" and r.status_code == 422:   # بعضی نسخه‌ها expire را به صورت تاریخ می‌خواهند
        b2 = dict(body); b2["expire"] = dt.datetime.fromtimestamp(body["expire"], dt.timezone.utc).isoformat()
        r = await c.post("/api/user", json=b2, headers=h)
    if r.status_code >= 400: raise Exception(f"HTTP {r.status_code}: {r.text[:300]}")
    return r.json()

def _pg_group_list(payload):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("groups", "data", "items", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            found = _pg_group_list(value)
            if found:
                return found
    return []

async def _pg_active_group_ids(c, h):
    # Pasarguard versions differ: some paginate /groups and newer versions
    # expose /groups/simple. Read-only lookup, no project data is changed.
    for path in ("/api/groups?all=true", "/api/groups/simple?all=true",
                 "/api/groups", "/api/groups/simple", "/api/group"):
        try:
            r = await c.get(path, headers=h)
            if r.status_code >= 400:
                continue
            groups = _pg_group_list(r.json())
            ids = [int(g["id"]) for g in groups
                   if isinstance(g, dict) and str(g.get("id", "")).isdigit()
                   and not g.get("is_disabled", g.get("disabled", False))]
            if ids:
                return ids
        except Exception as e:
            log.warning("pasarguard groups %s: %s", path, e)
    return []

def _xui_root(t): return XUI_PREFIX[t].split("/api")[0].split("/API")[0]   # /panel یا /xui

async def _xui_inbound(c, t, inb):
    try:
        j = (await c.get(f"{XUI_PREFIX[t]}/get/{inb}")).json()
        return j.get("obj") if j.get("success") else None
    except Exception as e:
        log.warning("xui inbound %s", e); return None

def _xui_prepare(client, inbound):
    if not inbound: return client
    proto = inbound.get("protocol")
    try: st = json.loads(inbound.get("settings") or "{}")
    except Exception: st = {}
    old = (st.get("clients") or [{}])[0]
    if proto == "vless": client["flow"] = old.get("flow", "")
    elif proto == "vmess": client["security"] = old.get("security", "auto")
    elif proto == "trojan": client["password"] = secrets.token_urlsafe(12)
    elif proto == "shadowsocks":
        m = st.get("method", "")
        n = 16 if "128" in m else 32
        client["password"] = base64.b64encode(os.urandom(n)).decode() if m.startswith("2022") else secrets.token_urlsafe(12)
        client["method"] = "" if m.startswith("2022") else m
    return client

def _xui_link(inbound, client, host):
    try:
        proto, port = inbound.get("protocol"), inbound.get("port")
        ss = json.loads(inbound.get("streamSettings") or "{}")
        st = json.loads(inbound.get("settings") or "{}")
    except Exception:
        return None
    ext = ss.get("externalProxy") or []
    if ext: host, port = ext[0].get("dest") or host, ext[0].get("port") or port
    net, sec = ss.get("network", "tcp"), ss.get("security", "none")
    ps = f"{inbound.get('remark') or 'srv'}-{client['email']}"
    prm = {"type": net, "security": sec}
    hpath, hhost, htype = "", "", "none"
    if net == "ws":
        w = ss.get("wsSettings") or {}; hpath = w.get("path", "/"); hhost = w.get("host") or (w.get("headers") or {}).get("Host", "")
    elif net == "grpc":
        g = ss.get("grpcSettings") or {}; prm["serviceName"] = g.get("serviceName", ""); hpath = prm["serviceName"]
        if g.get("multiMode"): prm["mode"] = "multi"
    elif net == "httpupgrade":
        w = ss.get("httpupgradeSettings") or {}; hpath = w.get("path", "/"); hhost = w.get("host", "")
    elif net in ("xhttp", "splithttp"):
        w = ss.get("xhttpSettings") or ss.get("splithttpSettings") or {}; hpath = w.get("path", "/"); hhost = w.get("host", "")
        if w.get("mode"): prm["mode"] = w["mode"]
    elif net == "tcp":
        hd = (ss.get("tcpSettings") or {}).get("header") or {}
        if hd.get("type") == "http":
            htype = "http"; prm["headerType"] = "http"
            rq = hd.get("request") or {}; hpath = ",".join(rq.get("path") or ["/"])
            hhost = ",".join((rq.get("headers") or {}).get("Host") or [])
    elif net == "kcp":
        k = ss.get("kcpSettings") or {}; htype = (k.get("header") or {}).get("type", "none"); prm["headerType"] = htype
        if k.get("seed"): prm["seed"] = k["seed"]
    if hpath and net != "grpc": prm["path"] = hpath
    if hhost: prm["host"] = hhost
    sni = ""
    if sec == "tls":
        tl = ss.get("tlsSettings") or {}; sni = tl.get("serverName", "")
        fp = (tl.get("settings") or {}).get("fingerprint"); alpn = tl.get("alpn") or []
        if sni: prm["sni"] = sni
        if fp: prm["fp"] = fp
        if alpn: prm["alpn"] = ",".join(alpn)
    elif sec == "reality":
        r = ss.get("realitySettings") or {}; rs = r.get("settings") or {}
        prm["pbk"] = rs.get("publicKey", ""); prm["fp"] = rs.get("fingerprint") or "chrome"
        sni = (r.get("serverNames") or [""])[0]; prm["sni"] = sni; prm["sid"] = (r.get("shortIds") or [""])[0]
        if rs.get("spiderX"): prm["spx"] = rs["spiderX"]
    tag = "#" + urllib.parse.quote(ps)
    if proto == "vless":
        prm["encryption"] = "none"
        if client.get("flow"): prm["flow"] = client["flow"]
        return f"vless://{client['id']}@{host}:{port}?{urllib.parse.urlencode(prm)}{tag}"
    if proto == "trojan":
        return f"trojan://{client.get('password') or client['id']}@{host}:{port}?{urllib.parse.urlencode(prm)}{tag}"
    if proto == "vmess":
        v = {"v": "2", "ps": ps, "add": host, "port": port, "id": client["id"], "aid": 0, "scy": client.get("security", "auto"),
             "net": net, "type": htype, "host": hhost, "path": hpath, "tls": sec if sec in ("tls", "reality") else "",
             "sni": sni, "fp": prm.get("fp", ""), "alpn": prm.get("alpn", "")}
        return "vmess://" + base64.b64encode(json.dumps(v, ensure_ascii=False).encode()).decode()
    if proto == "shadowsocks":
        m = st.get("method", ""); pw = client.get("password", "")
        if m.startswith("2022"): pw = f"{st.get('password', '')}:{pw}"
        ui = base64.urlsafe_b64encode(f"{m}:{pw}".encode()).decode().rstrip("=")
        return f"ss://{ui}@{host}:{port}{tag}"
    return None

async def _xui_sub(c, t, p, sid):
    try:
        j = (await c.post(_xui_root(t) + "/setting/all")).json()
        o = j.get("obj") or {}
    except Exception as e:
        log.warning("xui settings %s", e); return ""
    if not o.get("subEnable"): return ""
    if o.get("subURI"): return o["subURI"].rstrip("/") + "/" + sid
    host = o.get("subDomain") or urllib.parse.urlsplit(p["url"]).hostname
    scheme = "https" if o.get("subCertFile") else "http"
    path = "/" + (o.get("subPath") or "/sub/").strip("/") + "/"
    return f"{scheme}://{host}:{o.get('subPort') or 2096}{path}{sid}"

def make_qr(data):
    if not qrcode or not data: return None
    bio = io.BytesIO(); qrcode.make(data).save(bio, "PNG"); bio.seek(0); return bio

async def show(update: Update, text, kb=None):
    """اگر از دکمه آمده، پیام ویرایش شود؛ وگرنه پیام جدید."""
    markup = IKM(kb) if kb else None
    cq = update.callback_query
    if cq:
        try:
            return await cq.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=markup,
                                              disable_web_page_preview=True)
        except Exception:
            pass
    try:
        return await update.effective_chat.send_message(text, parse_mode=ParseMode.HTML, reply_markup=markup,
                                                        disable_web_page_preview=True)
    except Exception as e:  # ➕ اگر ایموجی پریمیوم رد شد، بدون پریمیوم بفرست تا ربات از کار نیفتد
        log.warning("show premium fallback: %s", e)
        t2, m2 = strip_premium(text, markup)
        if cq:
            try: return await cq.edit_message_text(t2, parse_mode=ParseMode.HTML, reply_markup=m2, disable_web_page_preview=True)
            except Exception: pass
        return await update.effective_chat.send_message(t2, parse_mode=ParseMode.HTML, reply_markup=m2,
                                                        disable_web_page_preview=True)

def set_state(ctx, *s): ctx.user_data["state"] = s
def clear_state(ctx): ctx.user_data.pop("state", None)

# ───────────────────────── اتصال به پنل‌ها ─────────────────────────
def _http(p):
    return httpx.AsyncClient(base_url=p["url"].rstrip("/"), timeout=25, verify=False,
                             proxy=S("bridge_url") or None, follow_redirects=True)

async def _token(c, p):
    path = "/api/admins/token" if p["ptype"] == "marzneshin" else "/api/admin/token"
    r = await c.post(path, data={"username": p["user"], "password": p["password"]})
    r.raise_for_status()
    return {"Authorization": "Bearer " + r.json()["access_token"]}

async def _xlogin(c, p):
    r = await c.post("/login", data={"username": p["user"], "password": p["password"]})
    r.raise_for_status()
    j = r.json()
    if not j.get("success"): raise Exception(j.get("msg") or "login failed")

def _ids(extra): return [int(x) for x in (extra or "").replace(" ", "").split(",") if x.isdigit()]

async def panel_test(p):
    if p["ptype"] == "manual": return True, "حالت فروش دستی (بدون اتصال)"
    try:
        async with _http(p) as c:
            await (_xlogin(c, p) if p["ptype"] in XUI_PREFIX else _token(c, p))
        return True, "اتصال موفق ✅"
    except Exception as e:
        return False, f"خطا در اتصال: {html.escape(str(e))[:300]}"

async def panel_create(p, username, gb, days):
    t, extra = p["ptype"], (p["extra"] or "").strip()
    exp = int(time.time() + days * 86400); limit = int(gb * 1024 ** 3); links = []
    async with _http(p) as c:
        if t in ("marzban", "pasarguard"):
            h = await _token(c, p)
            body = {"username": username, "expire": exp, "data_limit": limit,
                    "data_limit_reset_strategy": "no_reset", "status": "active"}
            if t == "marzban":
                body["proxies"] = json.loads(extra) if extra.startswith("{") else {"vless": {}}
                body["inbounds"] = {}
            else:
                body["group_ids"] = _ids(extra); body["proxy_settings"] = {}
                if not body["group_ids"]:
                    body["group_ids"] = await _pg_active_group_ids(c, h)
                if not body["group_ids"]:
                    raise Exception("هیچ گروه فعالی در پاسارگارد پیدا نشد؛ یک گروه فعال بسازید یا شناسه گروه را در تنظیمات پنل وارد کنید.")
            j = await _mz_create(c, t, body, h)  # ➕ با پیام خطای دقیق + سازگاری پاسارگارد
            sub, links = j.get("subscription_url") or "", j.get("links") or []
        elif t == "marzneshin":
            h = await _token(c, p)
            body = {"username": username, "service_ids": _ids(extra), "expire_strategy": "fixed_date",
                    "expire_date": dt.datetime.fromtimestamp(exp, dt.timezone.utc).isoformat(),
                    "data_limit": limit, "data_limit_reset_strategy": "no_reset"}
            r = await c.post("/api/users", json=body, headers=h); r.raise_for_status(); j = r.json()
            sub = j.get("subscription_url") or ""
        elif t in XUI_PREFIX:
            await _xlogin(c, p)
            parts = extra.split("|")
            inb = int(parts[0]) if parts and parts[0].strip().isdigit() else 1
            sub_base = parts[1].strip() if len(parts) > 1 else ""
            sid = secrets.token_hex(8)
            client = {"id": str(uuid.uuid4()), "email": username, "limitIp": 0, "totalGB": limit,
                      "expiryTime": exp * 1000, "enable": True, "tgId": "", "subId": sid, "flow": ""}
            inbound = await _xui_inbound(c, t, inb)  # ➕ تنظیم کلاینت بر اساس پروتکل اینباند
            client = _xui_prepare(client, inbound)
            r = await c.post(XUI_PREFIX[t] + "/addClient",
                             data={"id": inb, "settings": json.dumps({"clients": [client]})})
            j = r.json()
            if not j.get("success"): raise Exception(j.get("msg") or "addClient failed")
            sub = f"{sub_base.rstrip('/')}/{sid}" if sub_base else ""
            if not sub: sub = await _xui_sub(c, t, p, sid)  # ➕ لینک ساب از تنظیمات خود پنل
            host = parts[2].strip() if len(parts) > 2 and parts[2].strip() else urllib.parse.urlsplit(p["url"]).hostname
            if inbound and inbound.get("listen") not in (None, "", "0.0.0.0", "::") and not (len(parts) > 2 and parts[2].strip()):
                host = inbound["listen"]
            lk = _xui_link(inbound, client, host) if inbound else None  # ➕ لینک مستقیم کانفیگ
            if lk: links = [lk]
        else:
            raise Exception("نوع پنل پشتیبانی نمی‌شود")
    if sub.startswith("/"): sub = p["url"].rstrip("/") + sub
    if not links and sub.startswith("http"):  # ➕ گرفتن کانفیگ‌ها از خود لینک ساب
        links = await _sub_links(sub)
    return {"sub": sub, "link": links[0] if links else sub}

async def panel_info(p, username):
    t = p["ptype"]
    async with _http(p) as c:
        if t in ("marzban", "pasarguard"):
            h = await _token(c, p)
            j = (await c.get(f"/api/user/{username}", headers=h)).json()
            used, total, exp, st = j.get("used_traffic", 0), j.get("data_limit") or 0, j.get("expire"), j.get("status")
        elif t == "marzneshin":
            h = await _token(c, p)
            j = (await c.get(f"/api/users/{username}", headers=h)).json()
            used, total, exp = j.get("used_traffic", 0), j.get("data_limit") or 0, j.get("expire_date")
            st = "active" if j.get("is_active", j.get("enabled")) else "disabled"
        elif t in XUI_PREFIX:
            await _xlogin(c, p)
            j = (await c.get(f"{XUI_PREFIX[t]}/getClientTraffics/{username}")).json().get("obj") or {}
            used, total = (j.get("up", 0) + j.get("down", 0)), j.get("total", 0)
            exp = (j.get("expiryTime") or 0) / 1000; st = "active" if j.get("enable") else "disabled"
        else:
            return None
    if isinstance(exp, str):
        try: exp = dt.datetime.fromisoformat(exp.replace("Z", "+00:00")).timestamp()
        except Exception: exp = None
    return {"status": st, "used": used / 1024 ** 3, "total": total / 1024 ** 3 if total else 0,
            "expire": jdate(exp) if exp else "نامحدود"}

def _gb(value):
    try:
        return float(value or 0) / 1024 ** 3
    except Exception:
        return 0

def _pick(obj, *keys, default=None):
    if not isinstance(obj, dict):
        return default
    for key in keys:
        value = obj.get(key)
        if value is not None and value != "":
            return value
    return default

async def panel_status(p):
    """وضعیت کلی پنل، با سازگاری نسبی بین نسخه‌های مختلف."""
    t = p["ptype"]
    out = {"cpu": "-", "ram": "-", "swap": "-", "disk": "-", "panel_status": "نامشخص",
           "version": "-", "down": 0, "up": 0, "down_speed": 0, "up_speed": 0,
           "clients": 0, "main_accounts": 0, "user_down": 0, "user_up": 0,
           "user_total": 0, "active_volume": 0}
    if t == "manual":
        out["panel_status"] = "فروش دستی، بدون اتصال به پنل"
        return out
    async with _http(p) as c:
        if t in ("marzban", "pasarguard", "marzneshin"):
            h = await _token(c, p)
            data = {}
            for path in ("/api/system", "/api/system/status", "/api/admin/system"):
                try:
                    r = await c.get(path, headers=h)
                    if r.status_code < 400 and isinstance(r.json(), dict):
                        data = r.json(); break
                except Exception:
                    pass
            info = data.get("data", data) if isinstance(data, dict) else {}
            cpu = _pick(info, "cpu", "cpu_percent", "cpu_usage")
            ru = _pick(info, "ram_used", "memory_used", "used_memory")
            rt = _pick(info, "ram_total", "memory_total", "total_memory")
            if cpu is not None: out["cpu"] = f"{float(cpu):.1f}%"
            if ru is not None or rt is not None:
                out["ram"] = f"{_gb(ru):.2f} GB / {_gb(rt):.2f} GB"
            out["swap"] = _pick(info, "swap", "swap_usage", default="-")
            out["disk"] = _pick(info, "disk", "disk_usage", default="-")
            out["version"] = _pick(info, "version", "app_version", default="-")
            out["panel_status"] = "فعال ✅"
        elif t in XUI_PREFIX:
            await _xlogin(c, p)
            root = XUI_PREFIX[t].split("/api")[0].split("/API")[0]
            for path in (root + "/api/server/status", root + "/api/server/status/"):
                try:
                    r = await c.get(path)
                    if r.status_code < 400:
                        j = r.json()
                        info = j.get("obj", j.get("data", j)) if isinstance(j, dict) else {}
                        out["cpu"] = f"{float(_pick(info, 'cpu', 'cpu_percent', default=0)):.1f}%"
                        out["ram"] = f"{_gb(_pick(info, 'mem', 'mem_used', default=0)):.2f} GB / {_gb(_pick(info, 'mem_total', 'memTotal', default=0)):.2f} GB"
                        out["swap"] = f"{_gb(_pick(info, 'swap', 'swap_used', default=0)):.2f} GB / {_gb(_pick(info, 'swap_total', 'swapTotal', default=0)):.2f} GB"
                        out["disk"] = f"{_gb(_pick(info, 'disk', 'disk_used', default=0)):.2f} GB / {_gb(_pick(info, 'disk_total', 'diskTotal', default=0)):.2f} GB"
                        out["version"] = _pick(info, "version", "xray_version", default="-")
                        out["panel_status"] = "فعال ✅"
                        break
                except Exception:
                    pass
    return out

def panel_status_text(p, s):
    return (
        f"🛍 <b>وضعیت سرور {html.escape(p['name'])} 🚩</b>\n"
        f"╔══════════════════════╗\n<b>📊 وضعیت صفحه اصلی سرور</b>\n"
        f"╠ CPU: <b>{s['cpu']}</b>\n╠ وضعیت رم: <b>{s['ram']}</b>\n"
        f"╠ لینک پنل: <code>{html.escape(p['url'] or '-')}</code>\n"
        f"╠ SWAP: <b>{s['swap']}</b>\n╠ هارد: <b>{s['disk']}</b>\n"
        f"╠ وضعیت پنل: <b>{s['panel_status']}</b>\n╠ نسخه پنل: <b>{html.escape(str(s['version']))}</b>\n"
        f"╠ دانلود مصرفی: <b>{_gb(s['down']):.2f} GB</b>\n╠ آپلود مصرفی: <b>{_gb(s['up']):.2f} GB</b>\n"
        f"╠ دانلود بر ثانیه: <b>{s['down_speed']} MB</b>\n╚ آپلود بر ثانیه: <b>{s['up_speed']} MB</b>\n\n"
        f"╔══════════════════════╗\n<b>👥 وضعیت لیست اکانت‌ها</b>\n"
        f"╠ تعداد کل کلاینت‌ها: <b>{s['clients']}</b>\n╠ تعداد اکانت‌های اصلی: <b>{s['main_accounts']}</b>\n"
        f"╠ دانلود کاربران: <b>{_gb(s['user_down']):.2f} GB</b>\n╠ آپلود کاربران: <b>{_gb(s['user_up']):.2f} GB</b>\n"
        f"╠ مجموع مصرف: <b>{_gb(s['user_total']):.2f} GB</b>\n"
        f"╚ حجم فعال خریداری‌شده: <b>{s['active_volume']:.2f} GB</b>"
    )

# ───────────────────────── کیبوردها ─────────────────────────
def main_kb(uid):
    kb = [
        section_row("start", btn("خرید اشتراک", "buy", GREEN, "buy")),
        section_row("start", btn("اشتراک ها", "subs", None, "subs"), btn("افزایش موجودی", "account", None, "wallet")),
        section_row("start", btn("تست قبل از خرید", "test", RED, "test")),
        section_row("start", btn("پشتیبانی", "supportmenu", None, "support"), btn("کانال", url=S("channel_url"), ek="channel"), btn("حساب", "account", None, "account")),
        section_row("start", btn("سایر امکانات", "more", None, "more")),
    ]
    if is_admin(uid):
        kb.append(section_row("start", btn("پنل مدیریت", "admin", BLUE, "admin")))
    return kb

def back_home(): return [row(btn("بازگشت به منوی اصلی", "home", RED, "back"))]

def layout_choices(section, title, back="a:layout"):
    current = S("layout:" + section) or "4"
    return [
        row(btn("چیدمان اول" + (" ✅" if current == "1" else ""), f"lay:{section}:1", BLUE, "layout1")),
        row(btn("چیدمان دوم" + (" ✅" if current == "2" else ""), f"lay:{section}:2", BLUE, "layout2")),
        row(btn("چیدمان سوم" + (" ✅" if current == "3" else ""), f"lay:{section}:3", BLUE, "layout3")),
        row(btn("حالت اورجینال" + (" ✅" if current == "4" else ""), f"lay:{section}:4", GREEN, "original")),
    ] + admin_back(back)

def layout_kb():
    return [row(btn("چیدمان بخش استارت", "laymenu:start", BLUE, "startlayout")),
            row(btn("چیدمان سایر امکانات", "laymenu:more", BLUE, "morelayout"))] + admin_back("admin")

def admin_kb():
    return [
        row(btn("آمار", "a:stats", BLUE, "stats"), btn("پیام همگانی", "a:bc", BLUE, "bc")),
        row(btn("مدیریت پنل‌ها", "a:panels", BLUE, "panel"), btn("مدیریت پلن‌ها", "a:plans", BLUE, "plan")),
        row(btn("افزایش موجودی با آیدی", "a:addbal", GREEN, "addbal"), btn("کسر موجودی", "a:subbal", RED, "subbal")),
        row(btn("بن کاربر", "a:ban", RED, "ban"), btn("آن‌بن کاربر", "a:unban", GREEN, "unban")),
        row(btn("ویرایش متن‌ها", "a:texts", None, "text"), btn("ایموجی‌های پریمیوم", "a:emoji", None, "emoji")),
        row(btn("تنظیمات تست", "a:test", None, "test"), btn("تنظیمات پرداخت", "a:pay", None, "card")),
        row(btn("جستجوی کاربر در پنل", "a:search", None, "search"), btn("آدرس پل", "set:bridge_url", None, "bridge")),
        row(btn("تنظیمات عمومی", "a:gen", None, "settings")),
        row(btn("رنگ دکمه‌ها", "a:color", None, "settings"), btn("چیدمان دکمه‌ها", "a:layout", None, "layout")),
        row(btn("مدیریت ادمین‌ها", "a:admins", None, "admin")),
        row(btn("آدرس سرور اطلاعات IP", "set:ip_web_url", None, "ip")),
        row(btn("تراکنش‌ها", "a:trx", BLUE, "trx"), btn("کدهای تخفیف", "a:dc", GREEN, "discount")),  # ➕
        row(btn("بازگشت", "home", RED, "back")),
    ]

def admin_back(to="admin"): return [row(btn("بازگشت", to, RED, "back"))]

# ───────────────────────── صفحات کاربر ─────────────────────────
def active_services(uid):
    return q("SELECT COUNT(*) c FROM services WHERE user_id=? AND status='active' AND expire>?",
             (uid, int(time.time())), True)["c"]

async def send_home(update: Update, ctx, uid):
    u = get_user(uid)
    text = render("start", USER=html.escape(u["name"] or "کاربر"), ID=uid, BALANCE=money(u["balance"]),
                  SERVICES=active_services(uid), DATE=jdate())
    await show(update, text, main_kb(uid))

def months_label(m):
    return {1: "یک‌ماهه"}.get(m, f"{m} ماهه")

async def page_buy(update, ctx):
    plans = q("SELECT * FROM plans WHERE active=1 ORDER BY months, price")
    months = sorted({p["months"] for p in plans})
    lines = ["<b>مدت | حجم‌ها | شروع قیمت</b>"]
    for m in months:
        ps = [p for p in plans if p["months"] == m]
        lines.append(f"<b>{m} ماهه</b> | {min(p['gb'] for p in ps)} تا {max(p['gb'] for p in ps)} گیگ | "
                     f"{money(min(p['price'] for p in ps))} تومان")
    text = render("buy_intro") + "\n\n<blockquote>" + "\n".join(lines) + "</blockquote>"
    mb = [btn(months_label(m), f"pl:{m}", BLUE, f"m{m}" if f"m{m}" in EMOJI else None) for m in months]
    kb = [row(*mb[i:i + 2]) for i in range(0, len(mb), 2)]
    kb += [row(btn("مشاهده همه پلن‌ها", "pl:0", BLUE, "all")),
           row(btn("پیشنهاد سرویس", "suggest", GREEN, "suggest")),
           row(btn("بازگشت", "home", RED, "back"))]
    await show(update, text, kb)

def plan_rows(ps, bk):
    return [row(btn("خرید", f"bp:{p['id']}", GREEN, bk), btn(f"{p['gb']}گیگ", f"bp:{p['id']}"),
                btn(f"{p['days']}روز", f"bp:{p['id']}"), btn(money(p["price"]), f"bp:{p['id']}")) for p in ps]

async def page_plans(update, ctx, uid, m):
    plans = q("SELECT * FROM plans WHERE active=1 ORDER BY months, gb")
    months = sorted({p["months"] for p in plans})
    if not months: return await show(update, "فعلاً پلنی تعریف نشده.", back_home())
    u = get_user(uid)
    kb = [row(btn("خرید", "noop", RED, "shop"), btn("حجم", "noop", RED, "volume"),
              btn("زمان", "noop", RED, "time"), btn("قیمت", "noop", RED, "price"))]
    if m == 0:
        for mm in months:
            kb.append(row(btn(f"{mm} ماهه", f"pl:{mm}", BLUE, f"m{mm}" if f"m{mm}" in EMOJI else None)))
            kb += plan_rows([p for p in plans if p["months"] == mm], f"m{mm}" if f"m{mm}" in EMOJI else None)
    else:
        if m not in months: m = months[0]
        i = months.index(m); ek = f"m{m}" if f"m{m}" in EMOJI else None
        kb.append(row(btn(f"{m} ماهه", "noop", BLUE, ek)))
        kb += plan_rows([p for p in plans if p["months"] == m], ek)
        kb.append(row(btn("صفحه بعد", f"pl:{months[i + 1]}", BLUE) if i + 1 < len(months) else None,
                      btn(months_label(m), "noop"),
                      btn("صفحه قبل", f"pl:{months[i - 1]}", BLUE) if i > 0 else None))
    kb += [row(btn("پیشنهاد سرویس", "suggest", GREEN, "suggest")), row(btn("بازگشت", "buy", RED, "back"))]
    await show(update, render("plans", BALANCE=money(u["balance"])), kb)

async def page_invoice(update, uid, plan_id, panel_id):
    p = q("SELECT * FROM plans WHERE id=?", (plan_id,), True)
    pn = q("SELECT * FROM panels WHERE id=?", (panel_id,), True)
    u = get_user(uid)
    price, dcline, _ = dc_price(uid, p["price"])  # ➕ کد تخفیف
    text = render("invoice", GB=p["gb"], DAYS=p["days"], PRICE=money(price), BALANCE=money(u["balance"]),
                  LOCATION=html.escape(pn["name"])) + dcline
    kb = [row(btn("پرداخت از کیف پول", f"pay:{plan_id}:{panel_id}", GREEN, "ok")),
          row(btn("افزایش موجودی", "topup", None, "wallet")),
          row(btn("استفاده از کد تخفیف", f"dc:b:{plan_id}:{panel_id}", BLUE, "discount")),  # ➕
          row(btn("بازگشت", "buy", RED, "back"))]
    await show(update, text, kb)

async def deliver(ctx, uid, sid, key="delivery"):
    s = q("SELECT * FROM services WHERE id=?", (sid,), True)
    u = get_user(uid)
    link = s["sub"] or s["link"] or "-"
    text = render(key, USER=html.escape(u["name"] or ""), NAME=s["username"], GB=s["gb"], DAYS=s["days"],
                  PRICE=money(s["price"]), LINK=html.escape(link))
    kb = IKM([row(btn("اشتراک‌های من", "subs", BLUE, "subs")), row(btn("منوی اصلی", "home", RED, "back"))])
    qr = make_qr(link if link != "-" else None)
    if qr and len(text) < 1000:
        await ctx.bot.send_photo(uid, qr, caption=text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await ctx.bot.send_message(uid, text, parse_mode=ParseMode.HTML, reply_markup=kb)
    # ➕ ارسال جداگانه بارکد (QR) کانفیگ و لینک ساب
    for title, val in (("کانفیگ", s["link"]), ("لینک ساب", s["sub"])):
        if not val or val == "-": continue
        img = make_qr(val)
        if not img: continue
        try:
            await ctx.bot.send_photo(uid, img, caption=f"🔳 <b>QR {title}</b>\n<code>{html.escape(val[:900])}</code>",
                                     parse_mode=ParseMode.HTML)
        except Exception as e:
            log.warning("qr %s: %s", title, e)

async def build_service(ctx, uid, panel, gb, days, price, plan_id=None, is_test=0):
    uname = f"{USER_PREFIX}{uid}_{secrets.token_hex(2)}"
    now = int(time.time())
    if panel["ptype"] == "manual":
        sid = ex("INSERT INTO services(user_id,plan_id,panel_id,username,gb,days,price,created,expire,is_test,status)"
                 " VALUES(?,?,?,?,?,?,?,?,?,?,'pending')",
                 (uid, plan_id, panel["id"], uname, gb, days, price, now, now + days * 86400, is_test))
        for a in ADMIN_IDS:
            await ctx.bot.send_message(a, f"🛎 سفارش دستی #{sid}\nکاربر: <code>{uid}</code>\n{gb} گیگ / {days} روز",
                                       parse_mode=ParseMode.HTML,
                                       reply_markup=IKM([[btn("ارسال کانفیگ", f"dl:{sid}", GREEN, "link")]]))
        return sid, True
    res = await panel_create(panel, uname, gb, days)
    sid = ex("INSERT INTO services(user_id,plan_id,panel_id,username,link,sub,gb,days,price,created,expire,is_test)"
             " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
             (uid, plan_id, panel["id"], uname, res["link"], res["sub"], gb, days, price, now,
              now + days * 86400, is_test))
    return sid, False

async def do_pay(update, ctx, uid, plan_id, panel_id):
    p = q("SELECT * FROM plans WHERE id=?", (plan_id,), True)
    pn = q("SELECT * FROM panels WHERE id=? AND active=1", (panel_id,), True)
    u = get_user(uid)
    if not p or not pn: return await show(update, "این پلن/لوکیشن در دسترس نیست.", back_home())
    price, _, dcode = dc_price(uid, p["price"])  # ➕ قیمت بعد از کد تخفیف
    if u["balance"] < price:
        return await show(update, render("no_balance", PRICE=money(price), BALANCE=money(u["balance"])),
                          [row(btn("افزایش موجودی", "topup", GREEN, "wallet")), row(btn("بازگشت", "buy", RED, "back"))])
    ex("UPDATE users SET balance=balance-? WHERE id=?", (price, uid))
    try:
        sid, manual = await build_service(ctx, uid, pn, p["gb"], p["days"], price, plan_id)
    except Exception as e:
        ex("UPDATE users SET balance=balance+? WHERE id=?", (price, uid))
        log.exception("create failed")
        for a in ADMIN_IDS:
            await ctx.bot.send_message(a, f"⚠️ خطای ساخت سرویس روی پنل {pn['name']}:\n{html.escape(str(e))[:500]}")
        return await show(update, "❌ ساخت سرویس با خطا مواجه شد و مبلغ به کیف پول برگشت. به پشتیبانی پیام دهید.",
                          back_home())
    dc_use(uid, dcode); trx_log(uid, "buy", sid, plan_id, panel_id, p["gb"], p["days"], price, p["price"] - price, dcode)  # ➕
    if manual:
        return await show(update, "✅ سفارش ثبت شد. کانفیگ به‌زودی توسط پشتیبانی ارسال می‌شود.", back_home())
    if update.callback_query:
        try: await update.callback_query.message.delete()
        except Exception: pass
    await deliver(ctx, uid, sid)

async def page_account(update, uid):
    u = get_user(uid)
    services = q("SELECT COUNT(*) c FROM services WHERE user_id=? AND is_test=0", (uid,), True)["c"]
    inv = q("SELECT COUNT(*) c FROM payments WHERE user_id=? AND status='ok'", (uid,), True)["c"]
    refs = q("SELECT COUNT(*) c FROM users WHERE ref_by=?", (uid,), True)["c"]
    text = render("account", ID=uid, USER=html.escape(u["name"] or ""), PHONE=u["phone"] or "ثبت نشده",
                  GROUP=u["grp"], JOINED=jdate(u["created"]), REF=uid, BALANCE=money(u["balance"]),
                  SERVICES=services, INVOICES=inv, REFS=refs, DATE=jdate())
    kb = [row(btn("افزایش موجودی", "topup", GREEN, "bag"), btn("شارژ ویژه با هدیه", "gift", GREEN, "gift")),
          row(btn("کل تراکنش‌های من", "utrx:today", BLUE, "trx"))]
    if not u["phone"]: kb.append(row(btn("ثبت شماره تماس", "phone", None, "phone")))
    kb += back_home()
    await show(update, text, kb)

async def page_topup(update, gift=False):
    base = int(S("gift_min")) if gift else 50000
    amounts = [base, base * 2, base * 4, base * 10] if gift else [50000, 100000, 200000, 500000]
    g = 1 if gift else 0
    kb = [row(btn(f"{money(a)} تومان", f"ta:{a}:{g}", GREEN)) for a in amounts]
    kb += [row(btn("مبلغ دلخواه", f"tc:{g}", BLUE, "card")), row(btn("بازگشت", "account", RED, "back"))]
    text = render("gift", MIN=money(S("gift_min")), PERCENT=S("gift_percent")) if gift else render("topup")
    await show(update, text, kb)

async def ask_receipt(update, ctx, amount, gift):
    set_state(ctx, "receipt", amount, gift)
    await show(update, render("topup_card", PRICE=money(amount), CARD=html.escape(S("card_number")),
                              OWNER=html.escape(S("card_owner"))),
               [row(btn("انصراف", "account", RED, "no"))])

async def page_subs(update, uid):
    rows = q("SELECT * FROM services WHERE user_id=? AND status!='deleted' ORDER BY id DESC LIMIT 30", (uid,))  # ➕
    if not rows: return await show(update, render("subs_empty"), [row(btn("خرید اشتراک", "buy", GREEN, "buy"))] + back_home())
    kb = []
    for s in rows:
        st = "🟢" if s["status"] == "active" and s["expire"] > time.time() else ("⏳" if s["status"] == "pending" else "🔴")
        kb.append(row(btn(f"{st} {s['title'] or s['username']} | {s['gb']}GB{' (تست)' if s['is_test'] else ''}", f"sv:{s['id']}")))
    controls = [row(btn("جستجوی سرویس", "subsearch", BLUE, "searchsvc"),
                     btn("پاک‌سازی منقضی‌ها", "subclean", RED, "cleanup"))]
    await show(update, f"{E('subs')} <b>اشتراک‌های شما</b>", kb + controls + back_home())

async def page_sub_search(update, uid, term):
    term = (term or "").strip()
    if not term:
        return await page_subs(update, uid)
    rows = q("SELECT * FROM services WHERE user_id=? AND status!='deleted' AND (username LIKE ? OR title LIKE ?) ORDER BY id DESC LIMIT 30",
             (uid, f"%{term}%", f"%{term}%"))
    if not rows:
        return await show(update, "سرویسی با این مشخصات پیدا نشد.",
                          [row(btn("جستجوی دوباره", "subsearch", BLUE, "searchsvc"))] + back_home())
    kb = [row(btn(f"{'🟢' if s['status']=='active' else '🔴'} {s['title'] or s['username']} | {s['gb']}GB",
                  f"sv:{s['id']}")) for s in rows]
    await show(update, f"🔎 <b>نتیجه جستجو برای:</b> <code>{html.escape(term)}</code>",
               kb + [row(btn("جستجوی دوباره", "subsearch", BLUE, "searchsvc"))] + back_home())

async def cleanup_expired_services(update, ctx, uid):
    rows = q("SELECT * FROM services WHERE user_id=? AND status!='deleted' AND expire<=?",
             (uid, int(time.time())))
    if not rows:
        return await show(update, "✅ سرویس منقضی‌شده‌ای برای پاک‌سازی نیست.", back_home())
    removed = 0
    for s in rows:
        pn = q("SELECT * FROM panels WHERE id=?", (s["panel_id"],), True)
        if pn and pn["ptype"] != "manual" and s["status"] != "pending":
            try:
                await panel_delete(pn, s["username"])
            except Exception as e:
                log.warning("cleanup expired %s: %s", s["id"], e)
        ex("UPDATE services SET status='deleted' WHERE id=?", (s["id"],))
        removed += 1
    return await show(update, f"✅ {removed} سرویس منقضی پاک‌سازی شد.", back_home())

async def page_service(update, uid, sid):
    s = q("SELECT * FROM services WHERE id=? AND user_id=? AND status!='deleted'", (sid, uid), True)  # ➕
    if not s: return await show(update, "سرویس پیدا نشد.", back_home())
    pn = q("SELECT * FROM panels WHERE id=?", (s["panel_id"],), True)
    extra = ""
    if pn and pn["ptype"] != "manual" and s["status"] == "active":
        try:
            i = await panel_info(pn, s["username"])
            if i: extra = (f"\nوضعیت: <b>{i['status']}</b>\nمصرف: <b>{i['used']:.2f}</b> از "
                           f"<b>{i['total']:.0f}</b> گیگ\nانقضا: {i['expire']}")
        except Exception:
            extra = "\n(دریافت وضعیت از پنل ممکن نشد)"
    link = s["sub"] or s["link"] or "هنوز ارسال نشده"
    text = (f"{E('plan')} <b>{svc_name(s)}</b>\n<blockquote>📍 لوکیشن: {html.escape(pn['name'] if pn else '-')}\n"
            f"{E('volume')} حجم: {s['gb']} گیگ\n{E('time')} انقضا: {jdate(s['expire'])}{extra}</blockquote>\n\n"
            f"{E('link')} لینک:\n<code>{html.escape(link)}</code>")
    kb = [row(btn("دریافت QR", f"qr:{sid}", BLUE, "qr"), btn("بروزرسانی وضعیت", f"sv:{sid}", None, "search")),
          row(btn("QR کانفیگ", f"qrc:{sid}", BLUE, "qr")) if s["link"] and s["sub"] and s["link"] != s["sub"] else [],
          row(btn("تمدید پلن", f"rn:{sid}", GREEN, "renew")) if s["status"] != "pending" else [],  # ➕
          row(btn("تغییر نام سرویس", f"sren:{sid}", BLUE, "rename"), btn("حذف سرویس", f"sdel:{sid}", RED, "delsrv")),  # ➕
          row(btn("بازگشت", "subs", RED, "back"))]
    kb = [r for r in kb if r]  # ➕
    await show(update, text, kb)

async def page_user_trx(update, uid, per="today"):
    if per not in TRX_PERIODS: per = "today"
    a, b = trx_range(per)
    buys = q("SELECT * FROM services WHERE user_id=? AND is_test=0 AND created>=? AND created<?", (uid, a, b))
    rens = q("SELECT * FROM txlog WHERE user_id=? AND kind='renew' AND created>=? AND created<?", (uid, a, b))
    pays = q("SELECT * FROM payments WHERE user_id=? AND status='ok' AND created>=? AND created<?", (uid, a, b))
    lines = [f"{E('trx')} <b>تراکنش‌های من | {TRX_PERIODS[per]}</b>", "<blockquote>"]
    lines += [f"🛒 خرید سرویس: {money(sum(x['price'] or 0 for x in buys))} تومان" if buys else "🛒 خرید سرویس: ۰"]
    lines += [f"🔄 تمدید: {money(sum(x['amount'] or 0 for x in rens))} تومان" if rens else "🔄 تمدید: ۰"]
    lines += [f"💳 شارژ کیف پول: {money(sum(x['amount'] or 0 for x in pays))} تومان" if pays else "💳 شارژ کیف پول: ۰"]
    lines += [f"🧾 تعداد عملیات: {len(buys)+len(rens)+len(pays)}", "</blockquote>"]
    kb = [row(btn("امروز", "utrx:today", BLUE, "today"), btn("دیروز", "utrx:yday", BLUE, "yesterday")),
          row(btn("۷ روز اخیر", "utrx:7", BLUE, "last7"), btn("۳۰ روز اخیر", "utrx:30", BLUE, "last30")),
          row(btn("کل تراکنش‌ها", "utrx:all", GREEN, "alltrx"))]
    await show(update, "\n".join(lines), kb + back_home())

async def do_test(update, ctx, uid):
    u = get_user(uid)
    if S("test_enabled") != "1": return await show(update, "اکانت تست فعلاً غیرفعال است.", back_home())
    if u["test_used"]: return await show(update, "شما قبلاً اکانت تست دریافت کرده‌اید.", back_home())
    pid = S("test_panel")
    pn = (q("SELECT * FROM panels WHERE id=? AND active=1", (pid,), True) if pid.isdigit() else None) or \
         q("SELECT * FROM panels WHERE active=1 AND ptype!='manual' ORDER BY id LIMIT 1", one=True)
    if not pn: return await show(update, "هنوز سروری برای تست تنظیم نشده.", back_home())
    try:
        sid, manual = await build_service(ctx, uid, pn, float(S("test_gb")), float(S("test_days")), 0, None, 1)
    except Exception as e:
        log.exception("test failed")
        return await show(update, "❌ ساخت اکانت تست ممکن نشد، بعداً تلاش کنید.", back_home())
    ex("UPDATE users SET test_used=1 WHERE id=?", (uid,))
    if manual: return await show(update, "✅ درخواست تست ثبت شد.", back_home())
    await deliver(ctx, uid, sid, "test_delivery")

async def page_more(update, uid):
    kb = [section_row("more", btn("راهنما", "help", None, "help"), btn("قوانین", "rules", None, "rules")),
          section_row("more", btn("زیرمجموعه‌گیری", "ref", GREEN, "ref"), btn("تعرفه ها", "tariffs", None, "price"))]
    kb = [section_row("more", btn("اطلاعات IP من", "ip", GREEN, "ip")),
          section_row("more", btn("گزارش مصرف", "usage", None, "usage"), btn("پیشنهاد سرویس", "suggest", None, "suggest")),
          section_row("more", btn("تنظیمات من", "myset", None, "mysettings"), btn("تنظیم یادآورها", "remind", None, "remind")),
          section_row("more", btn("انتقال سرویس", "transfer", None, "transfer"))] + kb
    await show(update, render("more"), kb + back_home())

# ➕ صفحات جدید سایر امکانات
def back_more(): return [row(btn("بازگشت به سایر امکانات", "more", RED, "back"))]

async def page_tariffs(update, ctx, uid):
    """منوی تعرفه‌ها؛ قیمت و پلن‌ها از همان داده‌های فعلی بخش خرید خوانده می‌شوند."""
    text = "💲 <b>تعرفه ها</b>\n\nمدت اشتراک را انتخاب کنید:"
    kb = [
        row(btn("یک ماهه", "pl:1", BLUE, "tariff1")),
        row(btn("سه ماهه", "pl:3", BLUE, "tariff3")),
        row(btn("شش ماهه", "pl:6", BLUE, "tariff6")),
    ] + back_more()
    await show(update, text, kb)

async def page_ip(update, uid):
    link = ip_link(uid)
    if not link:
        t = "⚠️ این بخش هنوز توسط مدیریت فعال نشده."
        if is_admin(uid): t += "\n\nادمین: از پنل مدیریت > «آدرس سرور اطلاعات IP» آدرس عمومی سرور را وارد کن."
        return await show(update, t, back_more())
    await show(update, render("ip_intro"), [row(btn("بررسی و ارسال اطلاعات IP", url=link, style=GREEN, ek="ip"))] + back_more())

async def page_usage(update, uid):
    rows_ = q("SELECT * FROM services WHERE user_id=? AND status='active' ORDER BY id DESC LIMIT 10", (uid,))
    if not rows_: return await show(update, render("subs_empty"), back_more())
    out = []
    for s in rows_:
        pn = q("SELECT * FROM panels WHERE id=?", (s["panel_id"],), True)
        line = f"{E('plan')} <b>{html.escape(s['username'])}</b>"
        try:
            i = await panel_info(pn, s["username"]) if pn and pn["ptype"] != "manual" else None
        except Exception:
            i = None
        if i:
            left = max(i["total"] - i["used"], 0) if i["total"] else 0
            line += (f"\nمصرف: <b>{i['used']:.2f}</b> از <b>{i['total']:.0f}</b> گیگ"
                     + (f" | باقی‌مانده: <b>{left:.2f}</b>" if i["total"] else "") + f"\nانقضا: {i['expire']}")
        else:
            line += f"\nحجم: {s['gb']} گیگ | انقضا: {jdate(s['expire'])}"
        out.append(line)
    await show(update, f"{E('usage')} <b>گزارش مصرف</b>\n\n<blockquote>" + "\n\n".join(out) + "</blockquote>", back_more())

def remind_on(uid): return S(f"remind:{uid}") != "0"

async def page_myset(update, uid):
    u = get_user(uid)
    t = (f"{E('mysettings')} <b>تنظیمات من</b>\n<blockquote>👤 نام: <b>{html.escape(u['name'] or '-')}</b>\n"
         f"🆔 شناسه: <code>{uid}</code>\n📱 شماره: {html.escape(u['phone'] or 'ثبت نشده')}\n"
         f"🔔 یادآور انقضا: <b>{'روشن' if remind_on(uid) else 'خاموش'}</b></blockquote>")
    kb = [row(btn("تنظیم یادآورها", "remind", None, "remind"), btn("حساب کاربری", "account", None, "account"))]
    if not u["phone"]: kb.append(row(btn("ثبت شماره تماس", "phone", None, "phone")))
    await show(update, t, kb + back_more())

async def page_remind(update, uid):
    on = remind_on(uid)
    t = (f"{E('remind')} <b>تنظیم یادآورها</b>\n\nیادآور قبل از اتمام سرویس (۲۴ ساعت مانده): "
         f"<b>{'روشن' if on else 'خاموش'}</b>")
    await show(update, t, [row(btn("خاموش کردن یادآور" if on else "روشن کردن یادآور", "rmt", RED if on else GREEN, "remind"))] + back_more())

async def page_transfer(update, uid):
    rows_ = q("SELECT * FROM services WHERE user_id=? AND status='active' AND is_test=0 AND expire>? ORDER BY id DESC LIMIT 30",
              (uid, int(time.time())))
    if not rows_: return await show(update, "سرویس فعالی برای انتقال ندارید.", back_more())
    kb = [row(btn(f"{s['username']} | {s['gb']}GB", f"tr:{s['id']}", None, "transfer")) for s in rows_]
    await show(update, f"{E('transfer')} <b>انتقال سرویس</b>\nکدام سرویس را به کاربر دیگری منتقل کنیم؟", kb + back_more())

async def page_suggest(update):
    sp = S("suggest_plan")
    p = (q("SELECT * FROM plans WHERE id=? AND active=1", (sp,), True) if sp.isdigit() else None) or \
        q("SELECT p.* , COUNT(s.id) c FROM plans p LEFT JOIN services s ON s.plan_id=p.id WHERE p.active=1 "
          "GROUP BY p.id ORDER BY c DESC, p.price ASC LIMIT 1", one=True)
    if not p: return await show(update, "پلنی موجود نیست.", back_home())
    text = (f"{E('suggest')} <b>پیشنهاد ما برای شما</b>\n<blockquote>{E('volume')} {p['gb']} گیگ\n"
            f"{E('time')} {p['days']} روز\n{E('price')} {money(p['price'])} تومان</blockquote>")
    await show(update, text, [row(btn("خرید همین سرویس", f"bp:{p['id']}", GREEN, "buy")), row(btn("بازگشت", "buy", RED, "back"))])

# ───────────────────────── صفحات ادمین ─────────────────────────
async def admin_panels(update):
    kb = [row(btn(f"{'🟢' if p['active'] else '🔴'} {p['name']} ({p['ptype']})", f"pv:{p['id']}"))
          for p in q("SELECT * FROM panels")]
    kb += [row(btn("افزودن پنل", "pn", GREEN, "addbal"))] + admin_back()
    await show(update, f"{E('panel')} <b>مدیریت پنل‌ها (پل اتصال)</b>\nچند پنل = چند لوکیشن هنگام خرید.", kb)

async def admin_plans(update):
    kb = [row(btn(f"{'🟢' if p['active'] else '🔴'} {p['months']}ماهه | {p['gb']}گیگ | {p['days']}روز | {money(p['price'])}",
                  f"plv:{p['id']}")) for p in q("SELECT * FROM plans ORDER BY months, gb")]
    kb += [row(btn("افزودن پلن", "pla", GREEN, "addbal"))] + admin_back()
    await show(update, f"{E('plan')} <b>مدیریت پلن‌ها</b>\nقیمت، حجم و روز را خودت تعیین کن.", kb)

def settings_kb(keys, toggles=()):
    kb = [row(btn(f"{SETTING_TITLES[k]}: {S(k)[:20] or '-'}", f"set:{k}")) for k in keys]
    for k, title in toggles:
        on = S(k) == "1"
        kb.append(row(btn(f"{title}: {'روشن' if on else 'خاموش'}", f"tg:{k}", GREEN if on else RED)))
    return kb + admin_back()

# ───────────────────────── ➕ کد تخفیف / تمدید / حذف / تغییر نام / تراکنش‌ها ─────────────────────────
DC_PENDING = {}      # کد تخفیف اعمال‌شده هر کاربر (تا پرداخت بعدی)
RENEW_BUSY = set()   # جلوگیری از دوبار کلیک روی تمدید

def init_db_extra():
    CON.executescript("""
    CREATE TABLE IF NOT EXISTS discounts(code TEXT PRIMARY KEY, percent INTEGER, max_uses INTEGER DEFAULT 0,
        used INTEGER DEFAULT 0, active INTEGER DEFAULT 1, created INTEGER);
    CREATE TABLE IF NOT EXISTS discount_uses(id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT, user_id INTEGER, created INTEGER);
    CREATE TABLE IF NOT EXISTS txlog(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, kind TEXT, service_id INTEGER,
        plan_id INTEGER, panel_id INTEGER, gb REAL, days REAL, amount INTEGER, discount INTEGER DEFAULT 0, code TEXT,
        created INTEGER);
    """)
    cols = [r["name"] for r in q("PRAGMA table_info(services)")]
    if "title" not in cols: ex("ALTER TABLE services ADD COLUMN title TEXT")

def svc_name(s):
    t = s["title"] if "title" in s.keys() else None
    return f"{html.escape(t)} | {html.escape(s['username'])}" if t else html.escape(s["username"])

def dc_check(uid, code):
    """خروجی: (ردیف کد, دلیل خطا)"""
    r = q("SELECT * FROM discounts WHERE code=?", (code or "",), True)
    if not r or not r["active"]: return None, "کد تخفیف نامعتبر است."
    if r["max_uses"] and r["used"] >= r["max_uses"]: return None, "ظرفیت استفاده از این کد تمام شده."
    if q("SELECT 1 FROM discount_uses WHERE code=? AND user_id=?", (code, uid), True):
        return None, "شما قبلاً از این کد استفاده کرده‌اید."
    return r, ""

def dc_price(uid, price):
    """قیمت نهایی بعد از کد تخفیف اعمال‌شده → (قیمت, متن نمایش, کد)"""
    code = DC_PENDING.get(uid)
    if not code: return int(price), "", None
    r, _ = dc_check(uid, code)
    if not r: DC_PENDING.pop(uid, None); return int(price), "", None
    off = int(price) * int(r["percent"]) // 100
    final = max(int(price) - off, 0)
    line = "\n\n" + render("discount_ok", CODE=html.escape(code), PERCENT=r["percent"], ORIG=money(price),
                           DISCOUNT=money(off), PRICE=money(final))
    return final, line, code

def dc_use(uid, code):
    if not code: return
    ex("UPDATE discounts SET used=used+1 WHERE code=?", (code,))
    ex("INSERT INTO discount_uses(code,user_id,created) VALUES(?,?,?)", (code, uid, int(time.time())))
    DC_PENDING.pop(uid, None)

def dc_save(code, percent):
    percent = max(1, min(100, int(percent)))
    if q("SELECT 1 FROM discounts WHERE code=?", (code,), True):
        ex("UPDATE discounts SET percent=? WHERE code=?", (percent, code))
    else:
        ex("INSERT INTO discounts(code,percent,created) VALUES(?,?,?)", (code, percent, int(time.time())))

def dc_percent_kb(code):
    pcs = [5, 10, 15, 20, 25, 30, 40, 50, 70, 100]
    b = [btn(f"{p}%", f"dcp:{code}:{p}", BLUE) for p in pcs]
    return [row(*b[i:i + 5]) for i in range(0, len(b), 5)] + admin_back("a:dc")

def trx_log(uid, kind, sid, plan_id, panel_id, gb, days, amount, discount=0, code=None):
    try:
        ex("INSERT INTO txlog(user_id,kind,service_id,plan_id,panel_id,gb,days,amount,discount,code,created)"
           " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
           (uid, kind, sid, plan_id, panel_id, gb, days, int(amount), int(discount or 0), code, int(time.time())))
    except Exception as e:
        log.warning("txlog %s", e)

async def admin_discounts(update):
    kb = [row(btn(f"{'🟢' if r['active'] else '🔴'} {r['code']} | {r['percent']}% | {r['used']}/{r['max_uses'] or '∞'}",
                  f"dcv:{r['code']}")) for r in q("SELECT * FROM discounts ORDER BY created DESC LIMIT 40")]
    kb += [row(btn("ساخت کد تخفیف", "dca", GREEN, "addbal"))] + admin_back()
    await show(update, render("dc_admin"), kb)

async def admin_discount_view(update, code):
    r = q("SELECT * FROM discounts WHERE code=?", (code,), True)
    if not r: return await admin_discounts(update)
    t = (f"{E('discount')} <b>کد تخفیف</b> <code>{r['code']}</code>\n<blockquote>درصد تخفیف: <b>{r['percent']}%</b>\n"
         f"تعداد استفاده: <b>{r['used']}</b> از <b>{r['max_uses'] or 'نامحدود'}</b>\n"
         f"وضعیت: <b>{'فعال' if r['active'] else 'غیرفعال'}</b>\nساخته‌شده: {jdate(r['created'])}</blockquote>\n"
         "هر کاربر فقط یک‌بار می‌تواند از هر کد استفاده کند.")
    kb = [row(btn("تغییر درصد", f"dce:{code}", BLUE, "price"), btn("سقف استفاده", f"dcl:{code}", BLUE, "stats")),
          row(btn("غیرفعال کردن کد" if r["active"] else "فعال کردن کد", f"dcg:{code}", RED if r["active"] else GREEN),
              btn("حذف کد", f"dcd:{code}", RED, "no"))] + admin_back("a:dc")
    await show(update, t, kb)

TRX_PERIODS = {"today": "امروز", "yday": "دیروز", "7": "۷ روز اخیر", "30": "۳۰ روز اخیر", "all": "کل"}

def trx_range(per):
    day0 = dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    now = time.time() + 1
    return {"today": (day0, now), "yday": (day0 - 86400, day0), "7": (now - 7 * 86400, now),
            "30": (now - 30 * 86400, now)}.get(per, (0, now))

async def admin_trx(update, per):
    if per not in TRX_PERIODS: per = "today"
    a, b = trx_range(per)
    buys = q("SELECT * FROM services WHERE is_test=0 AND created>=? AND created<?", (a, b))
    rens = q("SELECT * FROM txlog WHERE kind='renew' AND created>=? AND created<?", (a, b))
    pays = q("SELECT * FROM payments WHERE status='ok' AND created>=? AND created<?", (a, b))
    tests = q("SELECT COUNT(*) c FROM services WHERE is_test=1 AND created>=? AND created<?", (a, b), True)["c"]
    newu = q("SELECT COUNT(*) c FROM users WHERE created>=? AND created<?", (a, b), True)["c"]
    disc = q("SELECT COALESCE(SUM(discount),0) s, COUNT(code) c FROM txlog WHERE created>=? AND created<? AND discount>0",
             (a, b), True)
    sb, sr = sum(s["price"] or 0 for s in buys), sum(r["amount"] or 0 for r in rens)
    pnames = {p["id"]: p["name"] for p in q("SELECT id,name FROM panels")}
    orig = {r["service_id"]: r for r in q("SELECT * FROM txlog WHERE kind='buy' AND created>=?", (a - 86400,))}  # مشخصات زمان خرید
    by_plan, by_panel = {}, {}
    for gb, days, pid, amt in ([(orig[s["id"]]["gb"] if s["id"] in orig else s["gb"],
                                 orig[s["id"]]["days"] if s["id"] in orig else s["days"],
                                 s["panel_id"], s["price"] or 0) for s in buys] +
                               [(r["gb"], r["days"], r["panel_id"], r["amount"] or 0) for r in rens]):
        k = f"{gb:g}گیگ | {days:g}روز"; c = by_plan.setdefault(k, [0, 0]); c[0] += 1; c[1] += amt
        k = pnames.get(pid, f"پنل حذف‌شده #{pid}"); c = by_panel.setdefault(k, [0, 0]); c[0] += 1; c[1] += amt
    fmt = lambda d: "\n".join(f"• {html.escape(k)}: <b>{v[0]}</b> عدد = <b>{money(v[1])}</b>"
                              for k, v in sorted(d.items(), key=lambda x: -x[1][1])[:15]) or "—"
    t = (render("trx_head", PERIOD=TRX_PERIODS[per]) +
         f"\n<blockquote>🛒 فروش سرویس: <b>{len(buys)}</b> عدد = <b>{money(sb)}</b> تومان\n"
         f"🔄 تمدید: <b>{len(rens)}</b> عدد = <b>{money(sr)}</b> تومان\n"
         f"💰 جمع درآمد: <b>{money(sb + sr)}</b> تومان\n"
         f"💳 شارژ کیف پول تأییدشده: <b>{len(pays)}</b> عدد = <b>{money(sum(p['amount'] for p in pays))}</b> تومان"
         f" (+ هدیه {money(sum(p['bonus'] or 0 for p in pays))})\n"
         f"🎟 تخفیف داده‌شده: <b>{disc['c']}</b> بار = <b>{money(disc['s'])}</b> تومان\n"
         f"🆓 اکانت تست: <b>{tests}</b> | 👥 کاربر جدید: <b>{newu}</b></blockquote>\n"
         f"📦 <b>به تفکیک پلن (حجم/مدت)</b>\n<blockquote>{fmt(by_plan)}</blockquote>\n"
         f"🔌 <b>به تفکیک پنل/لوکیشن</b>\n<blockquote>{fmt(by_panel)}</blockquote>")
    last = sorted([("🛒", s["created"], s["user_id"], s["price"] or 0, s["panel_id"]) for s in buys] +
                  [("🔄", r["created"], r["user_id"], r["amount"] or 0, r["panel_id"]) for r in rens],
                  key=lambda x: -x[1])[:10]
    if last and len(t) < 3000:
        t += "\n🧾 <b>آخرین تراکنش‌ها</b>\n<blockquote>" + "\n".join(
            f"{k} {jdate(c)} | <code>{u_}</code> | {money(am)} | {html.escape(pnames.get(pid, '-'))}"
            for k, c, u_, am, pid in last) + "</blockquote>"
    kb = [row(btn("امروز", "trx:today", BLUE), btn("دیروز", "trx:yday", BLUE)),
          row(btn("۷ روز اخیر", "trx:7", BLUE), btn("۳۰ روز اخیر", "trx:30", BLUE), btn("کل تراکنش‌ها", "trx:all", BLUE))]
    await show(update, t, kb + admin_back())

# ---------- پنل: تمدید و حذف ----------
async def _xui_find(c, t, p, username):
    """پیدا کردن اینباند و کلاینت روی X-UI با ایمیل (یوزرنیم سرویس)"""
    inb = None
    try:
        j = (await c.get(f"{XUI_PREFIX[t]}/getClientTraffics/{username}")).json().get("obj") or {}
        inb = j.get("inboundId") or j.get("inbound_id")
    except Exception as e:
        log.warning("xui find %s", e)
    if not inb:
        parts = (p["extra"] or "").split("|")
        inb = int(parts[0]) if parts and parts[0].strip().isdigit() else 1
    inbound = await _xui_inbound(c, t, inb)
    client = None
    if inbound:
        try: cl = json.loads(inbound.get("settings") or "{}").get("clients") or []
        except Exception: cl = []
        client = next((x for x in cl if x.get("email") == username), None)
    return inb, inbound, client

def _xui_cid(inbound, client):
    proto = (inbound or {}).get("protocol")
    if proto == "trojan": return client.get("password") or client.get("id")
    if proto == "shadowsocks": return client.get("email")
    return client.get("id")

async def panel_renew(p, username, gb, exp):
    """تمدید روی پنل: انقضای جدید + حجم جدید + ریست مصرف"""
    t = p["ptype"]; limit = int(gb * 1024 ** 3); exp = int(exp)
    async with _http(p) as c:
        if t in ("marzban", "pasarguard"):
            h = await _token(c, p)
            try: await c.post(f"/api/user/{username}/reset", headers=h)
            except Exception as e: log.warning("reset %s", e)
            body = {"expire": exp, "data_limit": limit, "status": "active"}
            r = await c.put(f"/api/user/{username}", json=body, headers=h)
            if t == "pasarguard" and r.status_code == 422:
                body["expire"] = dt.datetime.fromtimestamp(exp, dt.timezone.utc).isoformat()
                r = await c.put(f"/api/user/{username}", json=body, headers=h)
            if r.status_code >= 400: raise Exception(f"HTTP {r.status_code}: {r.text[:300]}")
        elif t == "marzneshin":
            h = await _token(c, p)
            try: await c.post(f"/api/users/{username}/reset", headers=h)
            except Exception as e: log.warning("reset %s", e)
            body = {"username": username, "expire_strategy": "fixed_date", "data_limit": limit,
                    "expire_date": dt.datetime.fromtimestamp(exp, dt.timezone.utc).isoformat()}
            r = await c.put(f"/api/users/{username}", json=body, headers=h)
            if r.status_code >= 400: raise Exception(f"HTTP {r.status_code}: {r.text[:300]}")
            try: await c.post(f"/api/users/{username}/enable", headers=h)
            except Exception: pass
        elif t in XUI_PREFIX:
            await _xlogin(c, p)
            inb, inbound, client = await _xui_find(c, t, p, username)
            if not client: raise Exception("کلاینت روی پنل پیدا نشد")
            client.update({"totalGB": limit, "expiryTime": exp * 1000, "enable": True})
            r = await c.post(f"{XUI_PREFIX[t]}/updateClient/{_xui_cid(inbound, client)}",
                             data={"id": inb, "settings": json.dumps({"clients": [client]})})
            j = r.json()
            if not j.get("success"): raise Exception(j.get("msg") or "updateClient failed")
            try: await c.post(f"{XUI_PREFIX[t]}/{inb}/resetClientTraffic/{username}")
            except Exception as e: log.warning("xui reset %s", e)
        else:
            raise Exception("نوع پنل پشتیبانی نمی‌شود")

async def panel_delete(p, username):
    t = p["ptype"]
    async with _http(p) as c:
        if t in ("marzban", "pasarguard", "marzneshin"):
            h = await _token(c, p)
            r = await c.delete(f"/api/{'users' if t == 'marzneshin' else 'user'}/{username}", headers=h)
            if r.status_code >= 400 and r.status_code != 404: raise Exception(f"HTTP {r.status_code}: {r.text[:300]}")
        elif t in XUI_PREFIX:
            await _xlogin(c, p)
            inb, inbound, client = await _xui_find(c, t, p, username)
            if not client: return  # روی پنل وجود ندارد
            j = (await c.post(f"{XUI_PREFIX[t]}/{inb}/delClient/{_xui_cid(inbound, client)}")).json()
            if not j.get("success"):
                j2 = (await c.post(f"{XUI_PREFIX[t]}/{inb}/delClientByEmail/{username}")).json()
                if not j2.get("success"): raise Exception(j.get("msg") or "delClient failed")
        else:
            raise Exception("نوع پنل پشتیبانی نمی‌شود")

# ---------- صفحات تمدید ----------
def _my_service(uid, sid):
    return q("SELECT * FROM services WHERE id=? AND user_id=? AND status!='deleted'", (sid, uid), True)

def renew_exp(s, days):
    return int(max(time.time(), s["expire"] or 0) + float(days) * 86400)

async def page_renew(update, uid, sid):
    s = _my_service(uid, sid)
    if not s: return await show(update, "سرویس پیدا نشد.", back_home())
    plans = q("SELECT * FROM plans WHERE active=1 ORDER BY months, gb")
    if not plans: return await show(update, "فعلاً پلنی برای تمدید وجود ندارد.", [row(btn("بازگشت", f"sv:{sid}", RED, "back"))])
    plans = sorted(plans, key=lambda p: p["id"] != s["plan_id"])  # پلن فعلی بالای لیست
    kb = [row(btn(f"{'⭐️ ' if p['id'] == s['plan_id'] else ''}{p['gb']}گیگ | {p['days']}روز | {money(p['price'])} تومان",
                  f"rnp:{sid}:{p['id']}")) for p in plans[:40]]
    kb.append(row(btn("بازگشت", f"sv:{sid}", RED, "back")))
    await show(update, render("renew_plans", NAME=svc_name(s), BALANCE=money(get_user(uid)["balance"])), kb)

async def page_renew_invoice(update, uid, sid, plan_id):
    s = _my_service(uid, sid); p = q("SELECT * FROM plans WHERE id=? AND active=1", (plan_id,), True)
    if not s or not p: return await show(update, "این سرویس/پلن در دسترس نیست.", back_home())
    u = get_user(uid)
    price, dcline, _ = dc_price(uid, p["price"])
    text = render("renew_invoice", NAME=svc_name(s), GB=p["gb"], DAYS=p["days"], EXPIRE=jdate(renew_exp(s, p["days"])),
                  PRICE=money(price), BALANCE=money(u["balance"])) + dcline
    kb = [row(btn("پرداخت و تمدید", f"rnpay:{sid}:{plan_id}", GREEN, "ok")),
          row(btn("افزایش موجودی", "topup", None, "wallet")),
          row(btn("استفاده از کد تخفیف", f"dc:r:{sid}:{plan_id}", BLUE, "discount")),
          row(btn("بازگشت", f"rn:{sid}", RED, "back"))]
    await show(update, text, kb)

async def do_renew(update, ctx, uid, sid, plan_id):
    s = _my_service(uid, sid); p = q("SELECT * FROM plans WHERE id=? AND active=1", (plan_id,), True)
    pn = q("SELECT * FROM panels WHERE id=?", (s["panel_id"],), True) if s else None
    if not s or not p: return await show(update, "این سرویس/پلن در دسترس نیست.", back_home())
    if not pn: return await show(update, "پنل این سرویس حذف شده؛ تمدید ممکن نیست. به پشتیبانی پیام دهید.", back_home())
    if s["status"] == "pending": return await show(update, "این سرویس هنوز تحویل نشده.", back_home())
    if sid in RENEW_BUSY: return
    price, _, dcode = dc_price(uid, p["price"])
    u = get_user(uid)
    if u["balance"] < price:
        return await show(update, render("no_balance", PRICE=money(price), BALANCE=money(u["balance"])),
                          [row(btn("افزایش موجودی", "topup", GREEN, "wallet")), row(btn("بازگشت", f"rnp:{sid}:{plan_id}", RED, "back"))])
    RENEW_BUSY.add(sid)
    new_exp = renew_exp(s, p["days"])
    ex("UPDATE users SET balance=balance-? WHERE id=?", (price, uid))
    try:
        if pn["ptype"] == "manual":
            for a in ADMIN_IDS:
                try: await ctx.bot.send_message(a, f"🔄 تمدید دستی سرویس <code>{html.escape(s['username'])}</code>\nکاربر: <code>{uid}</code>\n"
                                                   f"{p['gb']} گیگ / {p['days']} روز | انقضای جدید: {jdate(new_exp)}", parse_mode=ParseMode.HTML)
                except Exception: pass
        else:
            await panel_renew(pn, s["username"], p["gb"], new_exp)
    except Exception as e:
        ex("UPDATE users SET balance=balance+? WHERE id=?", (price, uid))
        log.exception("renew failed")
        for a in ADMIN_IDS:
            try: await ctx.bot.send_message(a, f"⚠️ خطای تمدید سرویس {s['username']} روی پنل {pn['name']}:\n{html.escape(str(e))[:500]}")
            except Exception: pass
        return await show(update, "❌ تمدید با خطا مواجه شد و مبلغ به کیف پول برگشت. به پشتیبانی پیام دهید.", back_home())
    finally:
        RENEW_BUSY.discard(sid)
    ex("UPDATE services SET gb=?, days=?, expire=?, plan_id=?, status='active', mid_sent=0, end_sent=0, is_test=0 WHERE id=?",
       (p["gb"], p["days"], new_exp, plan_id, sid))
    dc_use(uid, dcode); trx_log(uid, "renew", sid, plan_id, pn["id"], p["gb"], p["days"], price, p["price"] - price, dcode)
    await show(update, render("renew_done", NAME=svc_name(s), GB=p["gb"], EXPIRE=jdate(new_exp), PRICE=money(price)),
               [row(btn("بازگشت به سرویس", f"sv:{sid}", BLUE, "back"))] + back_home())

async def do_delete_service(update, ctx, uid, sid, force=False):
    s = _my_service(uid, sid)
    if not s: return await show(update, "سرویس پیدا نشد.", back_home())
    pn = q("SELECT * FROM panels WHERE id=?", (s["panel_id"],), True)
    if not force and pn and pn["ptype"] != "manual" and s["status"] != "pending":
        try:
            await panel_delete(pn, s["username"])
        except Exception as e:
            log.warning("delete %s: %s", s["username"], e)
            return await show(update, f"⚠️ حذف از پنل ممکن نشد:\n<code>{html.escape(str(e))[:300]}</code>\n\nدوباره تلاش کن یا فقط از ربات حذف شود؟",
                              [row(btn("تلاش دوباره", f"sdy:{sid}", BLUE, "renew"), btn("حذف فقط از ربات", f"sdf:{sid}", RED, "delsrv")),
                               row(btn("انصراف", f"sv:{sid}", GREEN, "back"))])
    elif pn and pn["ptype"] == "manual":
        for a in ADMIN_IDS:
            try: await ctx.bot.send_message(a, f"🗑 کاربر <code>{uid}</code> سرویس دستی <code>{html.escape(s['username'])}</code> را حذف کرد.",
                                            parse_mode=ParseMode.HTML)
            except Exception: pass
    ex("UPDATE services SET status='deleted' WHERE id=?", (sid,))
    await show(update, render("delete_done", NAME=svc_name(s)), [row(btn("اشتراک‌های من", "subs", BLUE, "subs"))] + back_home())

# ───────────────────────── هندلرها ─────────────────────────
def touch(tg_user, ref=None):
    u = get_user(tg_user.id); now = int(time.time())
    if not u:
        ref_by = ref if ref and ref != tg_user.id and get_user(ref) else None
        ex("INSERT INTO users(id,name,username,created,last_seen,ref_by) VALUES(?,?,?,?,?,?)",
           (tg_user.id, tg_user.first_name, tg_user.username, now, now, ref_by))
    else:
        ex("UPDATE users SET name=?, username=?, last_seen=? WHERE id=?",
           (tg_user.first_name, tg_user.username, now, tg_user.id))
    return get_user(tg_user.id)

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ref = None
    if ctx.args and ctx.args[0].startswith("ref_") and ctx.args[0][4:].isdigit():
        ref = int(ctx.args[0][4:])
    u = touch(update.effective_user, ref)
    clear_state(ctx)
    if u["banned"]: return await update.message.reply_text(render("banned"), parse_mode=ParseMode.HTML)
    if S("start_sticker"):
        try: await update.message.reply_sticker(S("start_sticker"))
        except Exception: pass
    await send_home(update, ctx, u["id"])

async def cmd_emoji(update: Update, ctx):
    if not is_admin(update.effective_user.id): return
    set_state(ctx, "emojiinfo")
    await update.message.reply_text("یک پیام حاوی ایموجی پریمیوم بفرست تا آیدی‌اش را بدهم.")

async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cq = update.callback_query; uid = cq.from_user.id; d = cq.data
    u = touch(cq.from_user)
    if u["banned"]: return await cq.answer("حساب شما مسدود است", show_alert=True)
    if d == "noop": return await cq.answer()
    await cq.answer()
    adm = is_admin(uid)

    # ---------- کاربر ----------
    if d == "home": clear_state(ctx); return await send_home(update, ctx, uid)
    if d == "buy": return await page_buy(update, ctx)
    if d.startswith("pl:"): return await page_plans(update, ctx, uid, int(d[3:]))
    if d == "suggest": return await page_suggest(update)
    if d.startswith("bp:"):
        pid = int(d[3:]); panels = q("SELECT * FROM panels WHERE active=1")
        if not panels: return await show(update, "فعلاً سروری فعال نیست.", back_home())
        if len(panels) == 1: return await page_invoice(update, uid, pid, panels[0]["id"])
        kb = [row(btn(f"📍 {p['name']}", f"inv:{pid}:{p['id']}", BLUE)) for p in panels]
        return await show(update, "📍 <b>لوکیشن مورد نظر را انتخاب کنید</b>", kb + [row(btn("بازگشت", "buy", RED, "back"))])
    if d.startswith(("inv:", "rnp:")) and (ctx.user_data.get("state") or [None])[0] == "dcode": clear_state(ctx)  # ➕
    if d.startswith("inv:"):
        _, a, b = d.split(":"); return await page_invoice(update, uid, int(a), int(b))
    if d.startswith("pay:"):
        _, a, b = d.split(":"); return await do_pay(update, ctx, uid, int(a), int(b))
    if d == "account": clear_state(ctx); return await page_account(update, uid)
    if d.startswith("utrx:"): return await page_user_trx(update, uid, d[5:])
    if d == "topup": return await page_topup(update)
    if d == "gift": return await page_topup(update, True)
    if d.startswith("ta:"):
        _, a, g = d.split(":"); return await ask_receipt(update, ctx, int(a), g == "1")
    if d.startswith("tc:"):
        set_state(ctx, "amount", d[3:] == "1")
        return await show(update, "💳 مبلغ دلخواه را به تومان بفرستید (فقط عدد):", [row(btn("انصراف", "account", RED, "no"))])
    if d == "subs": clear_state(ctx); return await page_subs(update, uid)
    if d == "subsearch":
        set_state(ctx, "subsearch")
        return await show(update, "🔎 نام یا شناسه سرویس را بفرست:",
                          [row(btn("انصراف", "subs", RED, "no"))])
    if d == "subclean":
        return await show(update, "⚠️ سرویس‌های منقضی از فهرست ربات حذف می‌شوند و حذف آن‌ها از پنل هم تلاش می‌شود. ادامه می‌دهی؟",
                          [row(btn("بله، پاک‌سازی کن", "subclean:yes", RED, "cleanup"),
                               btn("انصراف", "subs", GREEN, "back"))])
    if d == "subclean:yes": return await cleanup_expired_services(update, ctx, uid)
    if d.startswith("sv:"): return await page_service(update, uid, int(d[3:]))
    if d.startswith("qr:"):
        s = q("SELECT * FROM services WHERE id=? AND user_id=?", (int(d[3:]), uid), True)
        img = make_qr(s and (s["sub"] or s["link"]))
        if img: await ctx.bot.send_photo(uid, img, caption=f"<code>{html.escape(s['sub'] or s['link'])}</code>", parse_mode=ParseMode.HTML)
        return
    if d.startswith("qrc:"):  # ➕ QR فقط کانفیگ
        s = q("SELECT * FROM services WHERE id=? AND user_id=?", (int(d[4:]), uid), True)
        img = make_qr(s and s["link"])
        if img: await ctx.bot.send_photo(uid, img, caption=f"🔳 <b>QR کانفیگ</b>\n<code>{html.escape(s['link'][:900])}</code>", parse_mode=ParseMode.HTML)
        return
    # ➕ تمدید / حذف / تغییر نام سرویس + کد تخفیف
    if d.startswith("rn:"): clear_state(ctx); return await page_renew(update, uid, int(d[3:]))
    if d.startswith("rnp:"):
        _, a, b = d.split(":"); clear_state(ctx); return await page_renew_invoice(update, uid, int(a), int(b))
    if d.startswith("rnpay:"):
        _, a, b = d.split(":"); return await do_renew(update, ctx, uid, int(a), int(b))
    if d.startswith("sren:"):
        s = q("SELECT * FROM services WHERE id=? AND user_id=? AND status!='deleted'", (int(d[5:]), uid), True)
        if not s: return await show(update, "سرویس پیدا نشد.", back_home())
        set_state(ctx, "srename", s["id"])
        return await show(update, render("rename_ask", NAME=svc_name(s)), [row(btn("بازگشت", f"sv:{s['id']}", RED, "back"))])
    if d.startswith("sdel:"):
        s = q("SELECT * FROM services WHERE id=? AND user_id=? AND status!='deleted'", (int(d[5:]), uid), True)
        if not s: return await show(update, "سرویس پیدا نشد.", back_home())
        return await show(update, render("delete_confirm", NAME=svc_name(s)),
                          [row(btn("بله، حذف شود", f"sdy:{s['id']}", RED, "delsrv"), btn("انصراف", f"sv:{s['id']}", GREEN, "back"))])
    if d.startswith("sdy:") or d.startswith("sdf:"):
        return await do_delete_service(update, ctx, uid, int(d[4:]), force=d.startswith("sdf:"))
    if d.startswith("dc:"):
        parts = d.split(":"); back = f"inv:{parts[2]}:{parts[3]}" if parts[1] == "b" else f"rnp:{parts[2]}:{parts[3]}"
        set_state(ctx, "dcode", back)
        return await show(update, render("discount_ask"), [row(btn("بازگشت", back, RED, "back"))])
    # ➕ سایر امکانات جدید
    if d == "ip": return await page_ip(update, uid)
    if d == "usage": return await page_usage(update, uid)
    if d == "myset": return await page_myset(update, uid)
    if d == "remind": return await page_remind(update, uid)
    if d == "rmt": set_S(f"remind:{uid}", "0" if remind_on(uid) else "1"); return await page_remind(update, uid)
    if d == "transfer": clear_state(ctx); return await page_transfer(update, uid)
    if d.startswith("tr:"):
        s = q("SELECT * FROM services WHERE id=? AND user_id=?", (int(d[3:]), uid), True)
        if not s: return await show(update, "سرویس پیدا نشد.", back_more())
        set_state(ctx, "transfer", s["id"])
        return await show(update, f"آیدی عددی کاربری که می‌خواهی سرویس <code>{html.escape(s['username'])}</code> به او منتقل شود را بفرست:\n"
                                  "(کاربر مقصد باید یک‌بار ربات را استارت کرده باشد)", [row(btn("انصراف", "transfer", RED, "no"))])
    if d.startswith("trc:"):
        _, a, b = d.split(":"); s = q("SELECT * FROM services WHERE id=? AND user_id=?", (int(a), uid), True)
        if not s or not get_user(int(b)): return await show(update, "انتقال ممکن نیست.", back_more())
        ex("UPDATE services SET user_id=? WHERE id=?", (int(b), s["id"])); clear_state(ctx)
        try: await ctx.bot.send_message(int(b), f"🔁 سرویس <code>{html.escape(s['username'])}</code> به حساب شما منتقل شد.", parse_mode=ParseMode.HTML)
        except Exception: pass
        return await show(update, f"✅ سرویس <code>{html.escape(s['username'])}</code> به کاربر <code>{b}</code> منتقل شد.", back_more())
    if d == "test": return await do_test(update, ctx, uid)
    if d == "supportmenu": return await added_support_menu(update, ctx)
    if d == "more": return await page_more(update, uid)
    if d == "tariffs": return await page_tariffs(update, ctx, uid)
    if d in ("help", "rules"): return await show(update, render(d), [row(btn("بازگشت", "more", RED, "back"))])
    if d == "ref":
        me = await ctx.bot.get_me()
        return await show(update, render("ref", PERCENT=S("ref_percent"), LINK=f"https://t.me/{me.username}?start=ref_{uid}"),
                          [row(btn("بازگشت", "more", RED, "back"))])
    if d == "phone":
        kb = ReplyKeyboardMarkup([[KeyboardButton("📱 ارسال شماره", request_contact=True)]], resize_keyboard=True, one_time_keyboard=True)
        return await ctx.bot.send_message(uid, "با دکمه زیر شماره‌ات را بفرست:", reply_markup=kb)

    if not adm: return
    # ---------- ادمین ----------
    if d == "a:layout": return await show(update, f"{E('layout')} <b>چیدمان دکمه‌ها</b>\nبخش موردنظر را انتخاب کن:", layout_kb())
    if d.startswith("laymenu:"):
        section = d.split(":", 1)[1]
        if section not in {"start", "more"}: return await show(update, "بخش نامعتبر است.", layout_kb())
        title = "استارت" if section == "start" else "سایر امکانات"
        return await show(update, f"{E('layout')} <b>چیدمان {title}</b>", layout_choices(section, title))
    if d.startswith("lay:"):
        _, section, value = d.split(":")
        if section in {"start", "more"} and value in {"1", "2", "3", "4"}:
            set_S("layout:" + section, value)
        return await show(update, f"✅ چیدمان ذخیره شد.", layout_choices(section, ""))
    if d == "admin": clear_state(ctx); return await show(update, f"{E('admin')} <b>پنل مدیریت</b>", admin_kb())
    if d == "a:stats":
        now = int(time.time())
        t = (f"{E('stats')} <b>آمار</b>\n<blockquote>کاربران: {q('SELECT COUNT(*) c FROM users', one=True)['c']}\n"
             f"مسدود: {q('SELECT COUNT(*) c FROM users WHERE banned=1', one=True)['c']}\n"
             f"سرویس فعال: {q('SELECT COUNT(*) c FROM services WHERE status=? AND expire>?', ('active', now), True)['c']}\n"
             f"فروش کل: {money(q('SELECT COALESCE(SUM(price),0) s FROM services', one=True)['s'])} تومان\n"
             f"شارژ تأییدشده: {money(q('SELECT COALESCE(SUM(amount),0) s FROM payments WHERE status=?', ('ok',), True)['s'])} تومان\n"
             f"رسید در انتظار: {q('SELECT COUNT(*) c FROM payments WHERE status=?', ('pending',), True)['c']}</blockquote>")
        return await show(update, t, admin_back())
    prompts = {"a:addbal": ("addbal", "آیدی و مبلغ را بفرست:\n<code>123456789 50000</code>"),
               "a:subbal": ("subbal", "آیدی و مبلغ کسر:\n<code>123456789 50000</code>"),
               "a:ban": ("ban", "آیدی عددی کاربر برای بن:"), "a:unban": ("unban", "آیدی عددی کاربر برای آن‌بن:"),
               "a:bc": ("bc", "پیام همگانی را بفرست (متن/عکس/هرچی):"),
               "a:search": ("search", "یوزرنیم سرویس روی پنل را بفرست:"),
               "pla": ("pladd", "پلن جدید را این شکلی بفرست:\n<code>ماه حجم روز قیمت</code>\nمثال: <code>1 50 30 82500</code>")}
    if d in prompts:
        set_state(ctx, prompts[d][0]); return await show(update, prompts[d][1], admin_back())
    if d == "a:panels": return await admin_panels(update)
    if d == "a:plans": return await admin_plans(update)
    if d == "pn":
        kb = [row(btn(n, f"pn:{t}", BLUE)) for t, n in PANEL_TYPES]
        kb += [row(btn(f"{n} (به‌زودی)", "soon")) for n in SOON_PANELS]
        return await show(update, "نوع پنل را انتخاب کن:", kb + admin_back("a:panels"))
    if d == "soon": return await cq.answer("به‌زودی اضافه می‌شود", show_alert=True)
    if d.startswith("pn:"):
        ctx.user_data["np"] = {"ptype": d[3:]}; set_state(ctx, "padd", "name")
        return await show(update, "اسم پنل/لوکیشن را بفرست (مثلاً 🇩🇪 آلمان):", admin_back("a:panels"))
    if d == "psave":
        np = ctx.user_data.pop("np", None)
        if np:
            ex("INSERT INTO panels(name,ptype,url,user,password,extra) VALUES(?,?,?,?,?,?)",
               (np["name"], np["ptype"], np.get("url", ""), np.get("user", ""), np.get("password", ""), np.get("extra", "")))
        clear_state(ctx); return await admin_panels(update)
    if d.startswith("pv:"):
        p = q("SELECT * FROM panels WHERE id=?", (int(d[3:]),), True)
        t = (f"{E('panel')} <b>{html.escape(p['name'])}</b> (آیدی {p['id']})\nنوع: {p['ptype']}\nآدرس: {html.escape(p['url'] or '-')}\n"
             f"تنظیمات اضافه: <code>{html.escape(p['extra'] or '-')}</code>")
        kb = [row(btn("تست اتصال", f"pt:{p['id']}", BLUE, "search"),
                  btn("غیرفعال کن" if p["active"] else "فعال کن", f"pg:{p['id']}", RED if p["active"] else GREEN)),
              row(btn("وضعیت پنل", f"pi:{p['id']}", BLUE, "stats")),
              row(btn("حذف پنل", f"pd:{p['id']}", RED, "no"))] + admin_back("a:panels")
        return await show(update, t, kb)
    if d.startswith("pi:"):
        p = q("SELECT * FROM panels WHERE id=?", (int(d[3:]),), True)
        if not p: return await show(update, "پنل پیدا نشد.", admin_back("a:panels"))
        try:
            status = await panel_status(p)
            rows = q("SELECT * FROM services WHERE panel_id=? AND status!='deleted'", (p["id"],))
            status["clients"] = len(rows)
            status["main_accounts"] = sum(1 for r in rows if not r["is_test"])
            status["active_volume"] = sum(float(r["gb"] or 0) for r in rows
                                          if r["status"] == "active" and (r["expire"] or 0) > time.time())
            status["user_total"] = status["user_down"] + status["user_up"]
            return await show(update, panel_status_text(p, status),
                              [row(btn("🔄 بروزرسانی وضعیت", f"pi:{p['id']}", BLUE, "search")),
                               row(btn("بازگشت به پنل", f"pv:{p['id']}", RED, "back"))])
        except Exception as e:
            return await show(update, f"❌ دریافت وضعیت پنل ناموفق بود.\n<code>{html.escape(str(e))[:500]}</code>",
                              [row(btn("تلاش دوباره", f"pi:{p['id']}", BLUE, "search")),
                               row(btn("بازگشت به پنل", f"pv:{p['id']}", RED, "back"))])
    if d.startswith("pt:"):
        ok, msg = await panel_test(q("SELECT * FROM panels WHERE id=?", (int(d[3:]),), True))
        return await cq.message.reply_text(msg)
    if d.startswith("pg:"):
        ex("UPDATE panels SET active=1-active WHERE id=?", (int(d[3:]),)); return await admin_panels(update)
    if d.startswith("pd:"):
        ex("DELETE FROM panels WHERE id=?", (int(d[3:]),)); return await admin_panels(update)
    if d.startswith("plv:"):
        p = q("SELECT * FROM plans WHERE id=?", (int(d[4:]),), True)
        t = f"{E('plan')} پلن #{p['id']}\n{p['months']} ماهه | {p['gb']} گیگ | {p['days']} روز | {money(p['price'])} تومان"
        kb = [row(btn("ویرایش قیمت", f"plp:{p['id']}", BLUE, "price"),
                  btn("غیرفعال" if p["active"] else "فعال", f"plg:{p['id']}", RED if p["active"] else GREEN)),
              row(btn("حذف پلن", f"pld:{p['id']}", RED, "no"))] + admin_back("a:plans")
        return await show(update, t, kb)
    if d.startswith("plp:"):
        set_state(ctx, "plprice", int(d[4:])); return await show(update, "قیمت جدید (تومان):", admin_back("a:plans"))
    if d.startswith("plg:"):
        ex("UPDATE plans SET active=1-active WHERE id=?", (int(d[4:]),)); return await admin_plans(update)
    if d.startswith("pld:"):
        ex("DELETE FROM plans WHERE id=?", (int(d[4:]),)); return await admin_plans(update)
    if d == "a:texts":
        kb = [row(btn(v[0], f"tx:{k}", None, "text")) for k, v in TEXTS.items()]
        return await show(update, "✏️ <b>ویرایشگر متن‌ها</b>\nکدام متن را عوض کنیم؟", kb + admin_back())
    if d.startswith("tx:"):
        k = d[3:]; set_state(ctx, "text", k)
        cur = S("text:" + k) or TEXTS[k][1]
        return await show(update, f"متن فعلی «{TEXTS[k][0]}»:\n\n<code>{html.escape(cur)}</code>\n\n"
                                  "متغیرها: {BOT} {USER} {ID} {BALANCE} {PRICE} {GB} {DAYS} {LINK} {NAME} {DATE}\n"
                                  "ایموجی پریمیوم: {E:کلید} یا مستقیم ایموجی پریمیوم داخل متن بذار.\n\n"
                                  "متن جدید را بفرست (یا <code>reset</code> برای پیش‌فرض):",
                          [row(btn("بازگشت", "a:texts", RED, "back"))])
    if d == "a:emoji":
        set_state(ctx, "emojiquick")  # ➕ ارسال مستقیم ایموجی پریمیوم در همین صفحه
        kb = [row(btn(f"{EMOJI[k]} {k} {'✅' if S('emoji:' + k) else ''}", f"em:{k}")) for k in EMOJI]
        kb = [kb[i][0:1] + (kb[i + 1][0:1] if i + 1 < len(kb) else []) for i in range(0, len(kb), 2)]
        kb.append(row(btn(f"ایموجی پریمیوم: {'روشن' if S('premium_on') == '1' else 'خاموش'}", "tg:premium_on",
                          GREEN if S("premium_on") == "1" else RED)))
        kb.append(row(btn("ثبت گروهی با کد ایموجی", "emb", BLUE, "emoji")))  # ➕
        return await show(update, "😀 <b>ایموجی‌های پریمیوم</b>\nروی هر کلید بزن و ایموجی پریمیوم دلخواهت را بفرست.\n"
                                  "(باید صاحب ربات تلگرام پریمیوم داشته باشد)\n\n"
                                  "➕ یا همین‌جا <b>خود ایموجی پریمیوم</b> را بفرست تا بپرسم برای کدام دکمه ثبت شود.", kb + admin_back())
    if d.startswith("em:"):
        ctx.user_data.pop("eq", None)
        set_state(ctx, "emoji", d[3:])
        return await show(update, f"ایموجی پریمیوم برای «{d[3:]}» را بفرست (یا <code>reset</code>):"
                                  "\n\n➕ <b>خود ایموجی پریمیوم</b> را همین‌جا بفرست تا ثبت شود (کد عددی هم قبول است).", admin_back("a:emoji"))
    if d == "emb":  # ➕ ثبت گروهی ایموجی با کد
        set_state(ctx, "emojibulk")
        return await show(update, "هر خط: <code>کلید ایموجی‌پریمیوم</code> (یا کلید کد)\nمثال:\n<code>buy 🛍\nok ✅</code>  ← به جای این‌ها خود ایموجی پریمیوم را بگذار\n\n"
                                  "کلیدها: " + " ".join(f"<code>{k}</code>" for k in EMOJI), admin_back("a:emoji"))
    if d == "a:color" or d.startswith("cp:"):  # ➕ رنگ دکمه‌ها (هر دکمه جدا)
        return await show(update, "🎨 <b>رنگ دکمه‌ها</b>\nروی هر دکمه بزن و رنگش را انتخاب کن.\n"
                                  "⚪️ اورجینال  🟢 سبز  🔴 قرمز  🔵 آبی  ⚫️ بی‌رنگ",
                          color_list_kb(int(d[3:]) if d.startswith("cp:") else 0))
    if d.startswith("cb:"):
        _, i, pg = d.split(":"); i = int(i)
        if not 0 <= i < len(BTN_NAMES): return await show(update, "دکمه پیدا نشد.", color_list_kb())
        return await show(update, f"🎨 رنگ دکمه «<b>{html.escape(BTN_NAMES[i])}</b>» را انتخاب کن:", color_pick_kb(i, int(pg)))
    if d.startswith("cs:"):
        _, i, k, pg = d.split(":"); i = int(i)
        if 0 <= i < len(BTN_NAMES) and k in BTN_COLOR_MODES: set_S("color:" + BTN_NAMES[i], "" if k == "orig" else k)
        return await show(update, f"✅ رنگ «<b>{html.escape(BTN_NAMES[i])}</b>» شد: <b>{BTN_COLOR_MODES[k][0]}</b>",
                          color_list_kb(int(pg)))
    if d == "cr":
        ex("DELETE FROM settings WHERE k LIKE 'color:%'")
        return await show(update, "♻️ رنگ همه دکمه‌ها به حالت اورجینال برگشت.", color_list_kb())
    if d == "a:admins" or d.startswith("adm:"):  # ➕ مدیریت ادمین‌ها (فقط ادمین اصلی)
        if not is_main_admin(uid): return await show(update, "⛔️ فقط ادمین اصلی به این بخش دسترسی دارد.", admin_back())
        if d == "adm:add":
            set_state(ctx, "admadd"); return await show(update, "آیدی عددی ادمین جدید را بفرست:", admin_back("a:admins"))
        if d.startswith("adm:del:"):
            rid = int(d[8:]); save_admins([i for i in extra_admins() if i != rid])
            if rid != MAIN_ADMIN_ID and rid not in ENV_ADMIN_IDS: ADMIN_IDS.discard(rid)
        return await admin_admins(update)
    if d.startswith("eq:"):  # ➕ ثبت ایموجی ارسال‌شده روی دکمه انتخابی
        k, e = d[3:], ctx.user_data.get("eq")
        if not e or k not in EMOJI: return await show(update, "اول ایموجی پریمیوم را بفرست.", admin_back("a:emoji"))
        set_S("emoji:" + k, e[0]); set_S("emoji_fb:" + k, e[1]); set_state(ctx, "emojiquick")
        msg = f'✅ ثبت شد: <b>{k}</b> ← <tg-emoji emoji-id="{e[0]}">{e[1]}</tg-emoji>\nایموجی بعدی را بفرست یا برگرد.'
        return await show(update, msg, admin_back("a:emoji"))
    # ➕ تراکنش‌ها
    if d == "a:trx" or d.startswith("trx:"):
        return await admin_trx(update, d[4:] if d.startswith("trx:") else "today")
    # ➕ کدهای تخفیف
    if d == "a:dc": clear_state(ctx); return await admin_discounts(update)
    if d == "dca":
        set_state(ctx, "dcadd")
        return await show(update, "🎟 نام کد تخفیف را بفرست (حروف انگلیسی، عدد، - و _ | ۲ تا ۲۰ کاراکتر)\n"
                                  "یا <code>-</code> بفرست تا کد تصادفی ساخته شود:", admin_back("a:dc"))
    if d.startswith("dcp:"):
        _, code, pc = d.split(":"); clear_state(ctx)
        dc_save(code, int(pc)); return await admin_discount_view(update, code)
    if d.startswith("dcv:"): clear_state(ctx); return await admin_discount_view(update, d[4:])
    if d.startswith("dce:"):
        set_state(ctx, "dcpct", d[4:]); return await show(update, f"درصد تخفیف کد <code>{d[4:]}</code> را انتخاب کن یا عددش را بفرست (۱ تا ۱۰۰):",
                                                         dc_percent_kb(d[4:]))
    if d.startswith("dcg:"):
        ex("UPDATE discounts SET active=1-active WHERE code=?", (d[4:],)); return await admin_discount_view(update, d[4:])
    if d.startswith("dcl:"):
        set_state(ctx, "dclimit", d[4:])
        return await show(update, f"سقف تعداد استفاده از کد <code>{d[4:]}</code> را بفرست (<code>0</code> = نامحدود):",
                          admin_back(f"dcv:{d[4:]}"))
    if d.startswith("dcd:"):
        ex("DELETE FROM discounts WHERE code=?", (d[4:],)); return await admin_discounts(update)
    if d == "a:test":
        panels = "\n".join(f"{p['id']}: {html.escape(p['name'])}" for p in q("SELECT * FROM panels")) or "-"
        return await show(update, f"🆓 <b>تنظیمات اکانت تست</b>\nپنل‌ها:\n{panels}",
                          settings_kb(["test_gb", "test_days", "test_panel"], [("test_enabled", "تست رایگان")]))
    if d == "a:pay":
        return await show(update, "💳 <b>تنظیمات پرداخت و هدیه</b>",
                          settings_kb(["card_number", "card_owner", "gift_min", "gift_percent", "ref_percent"]))
    if d == "a:gen":
        return await show(update, "⚙️ <b>تنظیمات عمومی</b>",
                          settings_kb(["support_url", "channel_url", "start_sticker", "suggest_plan", "bridge_url"]))
    if d.startswith("set:"):
        k = d[4:]; set_state(ctx, "set", k)
        return await show(update, f"مقدار جدید «{SETTING_TITLES[k]}» را بفرست (یا <code>-</code> برای خالی):\nفعلی: <code>{html.escape(S(k))}</code>",
                          admin_back())
    if d.startswith("tg:"):
        k = d[3:]; set_S(k, "0" if S(k) == "1" else "1")
        return await show(update, f"✅ {k} = {'روشن' if S(k) == '1' else 'خاموش'}", admin_kb())
    if d.startswith("pa:") or d.startswith("pr:"):
        pay = q("SELECT * FROM payments WHERE id=?", (int(d[3:]),), True)
        if not pay or pay["status"] != "pending": return await cq.message.reply_text("قبلاً بررسی شده.")
        if d.startswith("pa:"):
            total = pay["amount"] + pay["bonus"]
            ex("UPDATE payments SET status='ok' WHERE id=?", (pay["id"],))
            ex("UPDATE users SET balance=balance+? WHERE id=?", (total, pay["user_id"]))
            payer = get_user(pay["user_id"])
            if payer["ref_by"]:
                share = pay["amount"] * int(S("ref_percent")) // 100
                if share:
                    ex("UPDATE users SET balance=balance+? WHERE id=?", (share, payer["ref_by"]))
                    try: await ctx.bot.send_message(payer["ref_by"], f"🤝 {money(share)} تومان پاداش زیرمجموعه گرفتی!")
                    except Exception: pass
            await ctx.bot.send_message(pay["user_id"], f"✅ {money(total)} تومان به کیف پولت اضافه شد.")
            await cq.edit_message_caption(f"✅ تأیید شد #{pay['id']} | {money(total)}")
        else:
            ex("UPDATE payments SET status='rejected' WHERE id=?", (pay["id"],))
            await ctx.bot.send_message(pay["user_id"], "❌ رسید شما رد شد. با پشتیبانی در ارتباط باشید.")
            await cq.edit_message_caption(f"❌ رد شد #{pay['id']}")
        return
    if d.startswith("dl:"):
        set_state(ctx, "deliver", int(d[3:])); return await cq.message.reply_text("لینک/کانفیگ این سفارش را بفرست:")

async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    m = update.effective_message; uid = update.effective_user.id
    u = touch(update.effective_user)
    if u["banned"]: return
    if m.contact and m.contact.user_id == uid:
        ex("UPDATE users SET phone=? WHERE id=?", (m.contact.phone_number, uid))
        await m.reply_text("✅ شماره ثبت شد.", reply_markup=ReplyKeyboardRemove())
        return await page_account(update, uid)
    st = ctx.user_data.get("state")
    if not st: return
    name, txt = st[0], (m.text or "").strip()

    # ---------- کاربر ----------
    if name == "amount":
        if not txt.replace(",", "").isdigit() or int(txt.replace(",", "")) < 10000:
            return await m.reply_text("فقط عدد بالای ۱۰,۰۰۰ تومان بفرست.")
        return await ask_receipt(update, ctx, int(txt.replace(",", "")), st[1])
    if name == "receipt":
        if not m.photo: return await m.reply_text("لطفاً عکس رسید را بفرست.")
        amount, gift = st[1], st[2]
        bonus = amount * int(S("gift_percent")) // 100 if gift and amount >= int(S("gift_min")) else 0
        pid = ex("INSERT INTO payments(user_id,amount,bonus,photo,created) VALUES(?,?,?,?,?)",
                 (uid, amount, bonus, m.photo[-1].file_id, int(time.time())))
        clear_state(ctx)
        cap = (f"🧾 رسید #{pid}\nکاربر: <code>{uid}</code> ({html.escape(u['name'] or '')})\n"
               f"مبلغ: {money(amount)}{f' + هدیه {money(bonus)}' if bonus else ''} تومان")
        kb = IKM([row(btn("تأیید", f"pa:{pid}", GREEN, "ok"), btn("رد", f"pr:{pid}", RED, "no"))])
        for a in ADMIN_IDS:
            try: await ctx.bot.send_photo(a, m.photo[-1].file_id, caption=cap, parse_mode=ParseMode.HTML, reply_markup=kb)
            except Exception: pass
        return await m.reply_text(render("receipt_wait"), parse_mode=ParseMode.HTML, reply_markup=IKM(back_home()))

    if name == "transfer":  # ➕ انتقال سرویس
        t = txt.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
        if not t.isdigit(): return await m.reply_text("فقط آیدی عددی بفرست.")
        if int(t) == uid: return await m.reply_text("نمی‌توانی به خودت منتقل کنی.")
        if not get_user(int(t)): return await m.reply_text("این کاربر پیدا نشد (باید یک‌بار ربات را استارت کرده باشد).")
        s = q("SELECT * FROM services WHERE id=? AND user_id=?", (st[1], uid), True)
        if not s: clear_state(ctx); return await m.reply_text("سرویس پیدا نشد.")
        kb = [row(btn("تأیید انتقال", f"trc:{s['id']}:{t}", GREEN, "ok"), btn("انصراف", "transfer", RED, "no"))]
        return await m.reply_text(f"سرویس <code>{html.escape(s['username'])}</code> به کاربر <code>{t}</code> منتقل شود؟",
                                  parse_mode=ParseMode.HTML, reply_markup=IKM(kb))
    if name == "dcode":  # ➕ وارد کردن کد تخفیف
        code = txt.upper().replace(" ", "")
        row_, reason = dc_check(uid, code)
        back = st[1]
        if not row_:
            return await m.reply_text(render("discount_bad", REASON=reason), parse_mode=ParseMode.HTML,
                                      reply_markup=IKM([row(btn("بازگشت", back, RED, "back"))]))
        DC_PENDING[uid] = code; clear_state(ctx)
        _, a, b = back.split(":")
        if back.startswith("inv:"): return await page_invoice(update, uid, int(a), int(b))
        return await page_renew_invoice(update, uid, int(a), int(b))
    if name == "subsearch":
        clear_state(ctx)
        return await page_sub_search(update, uid, txt)
    if name == "srename":  # ➕ تغییر نام سرویس
        new = " ".join(txt.split())
        if not new or len(new) > 32: return await m.reply_text("نام باید بین ۱ تا ۳۲ کاراکتر باشد. دوباره بفرست:")
        s = q("SELECT * FROM services WHERE id=? AND user_id=? AND status!='deleted'", (st[1], uid), True)
        clear_state(ctx)
        if not s: return await m.reply_text("سرویس پیدا نشد.")
        ex("UPDATE services SET title=? WHERE id=?", (new, s["id"]))
        return await show(update, render("rename_done", NAME=html.escape(new)),
                          [row(btn("بازگشت به سرویس", f"sv:{s['id']}", BLUE, "back"))] + back_home())
    if not is_admin(uid): return
    # ---------- ادمین ----------
    if name == "dcadd":  # ➕ ساخت کد تخفیف
        code = secrets.token_hex(3).upper() if txt == "-" else txt.upper().replace(" ", "")
        if not re.fullmatch(r"[A-Z0-9_-]{2,20}", code):
            return await m.reply_text("فقط حروف انگلیسی، عدد، - و _ (۲ تا ۲۰ کاراکتر). دوباره بفرست:")
        if q("SELECT 1 FROM discounts WHERE code=?", (code,), True):
            return await m.reply_text("این کد قبلاً ساخته شده. یک نام دیگر بفرست:")
        set_state(ctx, "dcpct", code)
        return await show(update, f"🎟 کد <code>{code}</code>\nچند درصد تخفیف بدهد؟ انتخاب کن یا عددش را بفرست (۱ تا ۱۰۰):",
                          dc_percent_kb(code))
    if name == "dcpct":
        t = txt.replace("%", "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
        if not t.isdigit() or not 1 <= int(t) <= 100: return await m.reply_text("فقط عدد بین ۱ تا ۱۰۰ بفرست.")
        clear_state(ctx); dc_save(st[1], int(t)); return await admin_discount_view(update, st[1])
    if name == "dclimit":
        t = txt.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
        if not t.isdigit(): return await m.reply_text("فقط عدد بفرست (0 = نامحدود).")
        ex("UPDATE discounts SET max_uses=? WHERE code=?", (int(t), st[1])); clear_state(ctx)
        return await admin_discount_view(update, st[1])
    if name == "emojiinfo" or name == "emoji":
        ids = premium_ids(m)  # ➕ متن و کپشن
        if name == "emoji":
            if txt.lower() == "reset": set_S("emoji:" + st[1], "")
            elif not ids and parse_emoji_ids(txt):  # ➕ کد عددی ایموجی
                eid = parse_emoji_ids(txt)[0]
                valid, fb = await check_emoji(ctx.bot, eid)
                if not valid: return await m.reply_text(f"❌ کد <code>{eid}</code> در تلگرام وجود ندارد. کد درست را بفرست.", parse_mode=ParseMode.HTML)
                set_S("emoji:" + st[1], eid); set_S("emoji_fb:" + st[1], fb); clear_state(ctx)
                try:
                    return await m.reply_text(f"✅ ذخیره شد: {st[1]}  →  <tg-emoji emoji-id=\"{eid}\">{fb}</tg-emoji>\n<code>{eid}</code>",
                                              parse_mode=ParseMode.HTML, reply_markup=IKM(admin_back("a:emoji")))
                except Exception as e:
                    return await m.reply_text(f"✅ ذخیره شد: {st[1]} ({eid})\n⚠️ تلگرام اجازه نمایش این ایموجی را به ربات نداد: {e}\n"
                                              "(برای نمایش ایموجی پریمیوم، صاحب ربات باید تلگرام پریمیوم داشته باشد)",
                                              reply_markup=IKM(admin_back("a:emoji")))
            elif not ids: return await m.reply_text("ایموجی پریمیوم پیدا نکردم. یک ایموجی پریمیوم بفرست.")
            else: set_S("emoji:" + st[1], ids[0])
            if ids and txt.lower() != "reset":  # ➕ ذخیره خود ایموجی + پیش‌نمایش
                fb = entity_fb(m, ids[0]); set_S("emoji_fb:" + st[1], fb)
                try: await m.reply_text(f'پیش‌نمایش: <tg-emoji emoji-id="{ids[0]}">{fb}</tg-emoji>', parse_mode=ParseMode.HTML)
                except Exception as e: await m.reply_text(f"⚠️ ذخیره شد ولی تلگرام اجازه نمایش نداد: {e}")
            clear_state(ctx); return await m.reply_text(f"✅ ذخیره شد: {st[1]}", reply_markup=IKM(admin_back("a:emoji")))
        if not ids and parse_emoji_ids(txt):  # ➕ پیش‌نمایش کد عددی
            return await m.reply_text("\n".join(f'<tg-emoji emoji-id="{i}">⭐️</tg-emoji> <code>{i}</code>' for i in parse_emoji_ids(txt)),
                                      parse_mode=ParseMode.HTML)
        if m.sticker: return await m.reply_text(f"file_id استیکر:\n<code>{m.sticker.file_id}</code>", parse_mode=ParseMode.HTML)
        return await m.reply_text("\n".join(f"<code>{i}</code>" for i in ids) or "ایموجی پریمیوم نبود.", parse_mode=ParseMode.HTML)
    if name == "emojiquick":  # ➕ ایموجی پریمیوم مستقیم → انتخاب دکمه
        ids = premium_ids(m)
        if ids: eid, fb = ids[0], entity_fb(m, ids[0])
        elif parse_emoji_ids(txt):
            eid = parse_emoji_ids(txt)[0]; valid, fb = await check_emoji(ctx.bot, eid)
            if not valid: return await m.reply_text("❌ این کد custom emoji معتبر نیست یا تلگرام فعلاً آن را در دسترس ربات قرار نداده است.")
        else:
            return await m.reply_text("ایموجی پریمیوم پیدا نکردم. (فرستنده باید تلگرام پریمیوم داشته باشد تا ایموجی پریمیوم بفرستد)")
        ctx.user_data["eq"] = (eid, fb)
        t = f'این ایموجی <tg-emoji emoji-id="{eid}">{fb}</tg-emoji> برای کدام دکمه ثبت شود؟\n<code>{eid}</code>'
        try: return await m.reply_text(t, parse_mode=ParseMode.HTML, reply_markup=IKM(emoji_pick_kb()))
        except Exception:
            t2, _ = strip_premium(t, None)
            return await m.reply_text(t2, parse_mode=ParseMode.HTML, reply_markup=IKM(emoji_pick_kb()))
    if name == "emojibulk":  # ➕ ثبت گروهی ایموجی با کد
        ok, bad = [], []
        pl = premium_by_line(m)
        for li, line in enumerate((m.text or "").splitlines()):
            parts = line.replace("»", " ").replace(":", " ").split()
            if not parts: continue
            if li in pl and parts[0] in EMOJI:  # ➕ خود ایموجی پریمیوم
                set_S("emoji:" + parts[0], pl[li][0]); set_S("emoji_fb:" + parts[0], pl[li][1])
                ok.append(f'{parts[0]} <tg-emoji emoji-id="{pl[li][0]}">{pl[li][1]}</tg-emoji>'); continue
            ids = parse_emoji_ids(line)
            if parts[0] in EMOJI and ids:
                valid, fb = await check_emoji(ctx.bot, ids[0])
                if not valid: bad.append(html.escape(line) + " (کد نامعتبر)"); continue
                set_S("emoji:" + parts[0], ids[0]); set_S("emoji_fb:" + parts[0], fb); ok.append(f'{parts[0]} <tg-emoji emoji-id="{ids[0]}">{fb}</tg-emoji>')
            else: bad.append(html.escape(line))
        clear_state(ctx)
        msg = ("✅ ذخیره شد:\n" + "\n".join(ok) if ok else "چیزی ذخیره نشد.") + ("\n\n❌ نامعتبر:\n" + "\n".join(bad) if bad else "")
        try: return await m.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=IKM(admin_back("a:emoji")))
        except Exception:
            t2, _ = strip_premium(msg, None)
            return await m.reply_text(t2 + "\n\n⚠️ تلگرام اجازه نمایش ایموجی پریمیوم را به ربات نداد (صاحب ربات باید پریمیوم باشد).",
                                      parse_mode=ParseMode.HTML, reply_markup=IKM(admin_back("a:emoji")))
    if name == "admadd":  # ➕ افزودن ادمین
        if not is_main_admin(uid): clear_state(ctx); return
        fo = getattr(m, "forward_origin", None); fu = getattr(fo, "sender_user", None) if fo else None
        if fu: txt = str(fu.id)  # پیام فوروارد‌شده از خود شخص هم قبول است
        txt = txt.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
        if not txt.isdigit(): return await m.reply_text("فقط آیدی عددی بفرست (یا یک پیام از خود شخص فوروارد کن).")
        nid = int(txt); save_admins(extra_admins() + [nid]); ADMIN_IDS.add(nid); clear_state(ctx)
        try: await ctx.bot.send_message(nid, "🛠 شما به عنوان ادمین ربات اضافه شدید. /start را بزنید.")
        except Exception: pass
        return await m.reply_text(f"✅ ادمین <code>{nid}</code> اضافه شد.", parse_mode=ParseMode.HTML,
                                  reply_markup=IKM([row(btn("مدیریت ادمین‌ها", "a:admins", BLUE, "admin"))] + admin_back()))
    if name == "set":
        k = st[1]
        val = m.sticker.file_id if (k == "start_sticker" and m.sticker) else ("" if txt == "-" else txt)
        set_S(k, val); clear_state(ctx)
        return await m.reply_text(f"✅ {SETTING_TITLES[k]} ذخیره شد.", reply_markup=IKM(admin_kb()))
    if name == "text":
        if txt.lower() == "reset": set_S("text:" + st[1], "")
        else: set_S("text:" + st[1], m.text_html)  # ایموجی‌های پریمیوم و فرمت‌ها حفظ می‌شوند
        clear_state(ctx); return await m.reply_text("✅ متن ذخیره شد.", reply_markup=IKM(admin_back("a:texts")))
    if name in ("addbal", "subbal"):
        parts = txt.split()
        if len(parts) != 2 or not all(x.isdigit() for x in parts): return await m.reply_text("فرمت: آیدی مبلغ")
        tid, amt = int(parts[0]), int(parts[1])
        if not get_user(tid): return await m.reply_text("کاربر پیدا نشد (باید یک‌بار ربات را استارت کرده باشد).")
        ex("UPDATE users SET balance=balance" + ("+" if name == "addbal" else "-") + "? WHERE id=?", (amt, tid))
        clear_state(ctx)
        try: await ctx.bot.send_message(tid, f"{'➕' if name == 'addbal' else '➖'} {money(amt)} تومان {'به' if name == 'addbal' else 'از'} کیف پول شما {'اضافه' if name == 'addbal' else 'کسر'} شد.")
        except Exception: pass
        return await m.reply_text(f"✅ انجام شد. موجودی جدید: {money(get_user(tid)['balance'])}", reply_markup=IKM(admin_kb()))
    if name in ("ban", "unban"):
        if not txt.isdigit(): return await m.reply_text("آیدی عددی بفرست.")
        ex("UPDATE users SET banned=? WHERE id=?", (1 if name == "ban" else 0, int(txt))); clear_state(ctx)
        return await m.reply_text(f"✅ کاربر {txt} {'بن' if name == 'ban' else 'آن‌بن'} شد.", reply_markup=IKM(admin_kb()))
    if name == "bc":
        clear_state(ctx); ok = 0
        for r in q("SELECT id FROM users WHERE banned=0"):
            try: await m.copy(r["id"]); ok += 1
            except Exception: pass
        return await m.reply_text(f"📢 ارسال شد برای {ok} نفر.", reply_markup=IKM(admin_kb()))
    if name == "search":
        out = []
        for p in q("SELECT * FROM panels WHERE active=1 AND ptype!='manual'"):
            try:
                i = await panel_info(p, txt)
                if i and i.get("status"): out.append(f"📍 {html.escape(p['name'])}: {i['status']} | {i['used']:.2f}/{i['total']:.0f}GB | {i['expire']}")
            except Exception: pass
        s = q("SELECT * FROM services WHERE username=?", (txt,), True)
        if s: out.append(f"👤 مالک تلگرام: <code>{s['user_id']}</code>")
        clear_state(ctx)
        return await m.reply_text("\n".join(out) or "روی هیچ پنلی پیدا نشد.", parse_mode=ParseMode.HTML, reply_markup=IKM(admin_kb()))
    if name == "pladd":
        parts = txt.split()
        if len(parts) != 4 or not all(x.isdigit() for x in parts): return await m.reply_text("فرمت: ماه حجم روز قیمت")
        ex("INSERT INTO plans(months,gb,days,price) VALUES(?,?,?,?)", tuple(map(int, parts))); clear_state(ctx)
        return await m.reply_text("✅ پلن اضافه شد.", reply_markup=IKM(admin_back("a:plans")))
    if name == "plprice":
        if not txt.isdigit(): return await m.reply_text("فقط عدد.")
        ex("UPDATE plans SET price=? WHERE id=?", (int(txt), st[1])); clear_state(ctx)
        return await m.reply_text("✅ قیمت به‌روز شد.", reply_markup=IKM(admin_back("a:plans")))
    if name == "deliver":
        s = q("SELECT * FROM services WHERE id=?", (st[1],), True)
        ex("UPDATE services SET link=?, sub=?, status='active', created=?, expire=? WHERE id=?",
           (txt, txt, int(time.time()), int(time.time()) + s["days"] * 86400, s["id"]))
        clear_state(ctx); await deliver(ctx, s["user_id"], s["id"], "test_delivery" if s["is_test"] else "delivery")
        return await m.reply_text("✅ برای کاربر ارسال شد.")
    if name == "padd":
        np, step = ctx.user_data.setdefault("np", {}), st[1]
        manual = np.get("ptype") == "manual"
        flow = ["name"] if manual else ["name", "url", "user", "password", "extra"]
        key = {"name": "name", "url": "url", "user": "user", "password": "password", "extra": "extra"}[step]
        np[key] = "" if (step == "extra" and txt == "-") else txt.rstrip("/") if step == "url" else txt
        nxt = flow.index(step) + 1
        asks = {"url": "آدرس پنل با پورت (مثل https://panel.site.com:8000):", "user": "یوزرنیم ادمین پنل:",
                "password": "پسورد ادمین پنل:",
                "extra": f"تنظیمات اضافه: {EXTRA_HINT.get(np['ptype'], '-')}\n(یا - برای رد کردن)"}
        if nxt < len(flow):
            set_state(ctx, "padd", flow[nxt]); return await m.reply_text(asks[flow[nxt]])
        await m.reply_text("⏳ در حال تست اتصال...")
        ok, msg = await panel_test(np)
        kb = [row(btn("ذخیره", "psave", GREEN, "ok") if ok else btn("ذخیره به هر حال", "psave", RED, "no")),
              row(btn("لغو", "a:panels", RED, "back"))]
        return await m.reply_text(msg, reply_markup=IKM(kb))

# ───────────────────────── کار زمان‌بندی‌شده (پیگیری تست/انقضا) ─────────────────────────
async def job_followup(ctx: ContextTypes.DEFAULT_TYPE):
    now = int(time.time())
    for s in q("SELECT * FROM services WHERE status='active'"):
        if not s["is_test"] and not remind_on(s["user_id"]):  # ➕ یادآور خاموش
            if now >= s["expire"]: ex("UPDATE services SET status='expired' WHERE id=?", (s["id"],))
            continue
        u = get_user(s["user_id"]); name = html.escape(u["name"] or "") if u else ""
        buy_kb = IKM([row(btn("خرید اشتراک", "buy", GREEN, "buy"))])
        try:
            if s["is_test"]:
                if not s["mid_sent"] and now >= (s["created"] + s["expire"]) // 2:
                    await ctx.bot.send_message(s["user_id"], render("test_mid", USER=name), parse_mode=ParseMode.HTML, reply_markup=buy_kb)
                    ex("UPDATE services SET mid_sent=1 WHERE id=?", (s["id"],))
                if not s["end_sent"] and now >= s["expire"]:
                    await ctx.bot.send_message(s["user_id"], render("test_end", USER=name), parse_mode=ParseMode.HTML, reply_markup=buy_kb)
                    ex("UPDATE services SET end_sent=1, status='expired' WHERE id=?", (s["id"],))
            else:
                if not s["mid_sent"] and 0 < s["expire"] - now < 86400:
                    await ctx.bot.send_message(s["user_id"], render("expire_soon", NAME=s["username"]), parse_mode=ParseMode.HTML, reply_markup=buy_kb)
                    ex("UPDATE services SET mid_sent=1 WHERE id=?", (s["id"],))
                if now >= s["expire"]: ex("UPDATE services SET status='expired' WHERE id=?", (s["id"],))
        except Exception as e:
            log.warning("followup %s: %s", s["id"], e)


# ───────────────────────── افزودنی‌های جدید: پشتیبانی و ابزارهای کمکی ─────────────────────────
# این بخش فقط به کد قبلی اضافه شده و هیچ قابلیت قبلی را حذف یا جایگزین نمی‌کند.
import shutil

async def init_added_features():
    CON.executescript("""
    CREATE TABLE IF NOT EXISTS support_tickets(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        subject TEXT DEFAULT '', status TEXT DEFAULT 'open', created INTEGER,
        updated INTEGER, admin_id INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS support_messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id INTEGER NOT NULL,
        sender_id INTEGER NOT NULL, body TEXT, created INTEGER
    );
    CREATE TABLE IF NOT EXISTS audit_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT, actor_id INTEGER,
        action TEXT, target TEXT DEFAULT '', details TEXT DEFAULT '', created INTEGER
    );
    """)
    CON.commit()
    # افزودنی‌های رابط تیکت: فقط ثبت تنظیمات/کلیدها، بدون حذف یا تغییر قابلیت‌های قبلی
    EMOJI.update({"ticket_reply": "↩️", "ticket_close": "🔒"})
    BTN_GROUPS.update({
        "ticket_reply": "دکمه پاسخ تیکت",
        "ticket_close": "دکمه بستن تیکت",
        "ticket_open": "دکمه باز کردن تیکت",
    })
    for _n in BTN_GROUPS.values():
        if _n not in BTN_NAMES:
            BTN_NAMES.append(_n)

def added_audit(actor, action, target='', details=''):
    try: ex("INSERT INTO audit_log(actor_id,action,target,details,created) VALUES(?,?,?,?,?)", (actor,action,str(target),str(details)[:1000],int(time.time())))
    except Exception as e: log.warning("audit: %s", e)

def added_ticket_kb(tid, admin=False):
    if admin:
        return IKM([
            [btn('پاسخ', f'addtkreply:{tid}', BLUE, 'ticket_reply')],
            [btn('بستن تیکت', f'addtkclose:{tid}', RED, 'ticket_close')],
            [btn('بازگشت به تیکت‌ها', 'addtks', None, 'back')]
        ])
    return IKM([
        [btn('پاسخ', f'addtkmsg:{tid}', BLUE, 'ticket_reply')],
        [btn('بستن تیکت', f'addtkclose:{tid}', RED, 'ticket_close')]
    ])

async def added_support_menu(update, ctx):
    await show(update, f"{E('support')} <b>پشتیبانی</b>\n\nیکی از گزینه‌ها را انتخاب کن:",
               [row(btn('باز کردن تیکت', 'addtkopen', BLUE, 'ticket')),
                row(btn('ارتباط مستقیم', url=S('support_url'), ek='direct'))] + back_home())

async def added_ticket_open(update, ctx):
    uid=update.effective_user.id; now=int(time.time())
    t=q("SELECT * FROM support_tickets WHERE user_id=? AND status='open' ORDER BY id DESC LIMIT 1",(uid,),True)
    if t: tid=t['id']; text=f'🎫 تیکت باز شما #{tid} است. پیام جدید را بفرست.'
    else:
        tid=ex('INSERT INTO support_tickets(user_id,created,updated) VALUES(?,?,?)',(uid,now,now)); added_audit(uid,'ticket_open',tid)
        text=f'🎫 تیکت #{tid} ساخته شد. پیام یا مشکل خودت را بفرست.'
    set_state(ctx,'addticket',tid)
    if update.callback_query:
        return await show(update, text, [row(btn('لغو','home',RED,'no'))])
    return await update.message.reply_text(text, reply_markup=IKM([[btn('لغو','home',RED,'no')]]))

def added_ticket_text(tid):
    t=q('SELECT * FROM support_tickets WHERE id=?',(tid,),True)
    if not t:return None
    msgs=q('SELECT * FROM support_messages WHERE ticket_id=? ORDER BY id ASC LIMIT 100',(tid,))
    lines=[f"🎫 <b>تیکت #{tid}</b> | کاربر <code>{t['user_id']}</code> | {t['status']}"]
    for m in msgs:
        who='کاربر' if m['sender_id']==t['user_id'] else f"ادمین {m['sender_id']}"
        lines.append(f"\n<b>{who}:</b> {html.escape(m['body'] or '')}")
    return '\n'.join(lines)

async def added_tickets(update, ctx):
    uid=update.effective_user.id
    if not is_admin(uid): return
    rows=q("SELECT * FROM support_tickets WHERE status='open' ORDER BY updated DESC LIMIT 30")
    kb=[[btn(f"#{r['id']} | کاربر {r['user_id']}",f"addtk:{r['id']}",None,'ticket')] for r in rows]
    await update.message.reply_text('🎫 تیکت‌های باز:' if rows else 'تیکت باز نداریم.',reply_markup=IKM(kb) if kb else None)

async def added_ticket_callback(update,ctx):
    cq=update.callback_query; uid=cq.from_user.id; d=cq.data
    if d=='addtkopen': await cq.answer(); return await added_ticket_open(update,ctx)
    if d=='addtks':
        if not is_admin(uid): return await cq.answer('دسترسی ندارید',show_alert=True)
        await cq.answer(); rows=q("SELECT * FROM support_tickets WHERE status='open' ORDER BY updated DESC LIMIT 30")
        kb=[[btn(f"#{r['id']} | کاربر {r['user_id']}",f"addtk:{r['id']}",None,'ticket')] for r in rows]
        return await cq.edit_message_text('🎫 تیکت‌های باز:' if rows else 'تیکت باز نداریم.',reply_markup=IKM(kb) if kb else None)
    if d.startswith('addtk:'):
        if not is_admin(uid): return await cq.answer('دسترسی ندارید',show_alert=True)
        await cq.answer(); tid=int(d.split(':')[1]); return await cq.edit_message_text(added_ticket_text(tid) or 'تیکت پیدا نشد.',parse_mode=ParseMode.HTML,reply_markup=added_ticket_kb(tid,True))
    if d.startswith('addtkmsg:'):
        tid=int(d.split(':')[1]); t=q('SELECT * FROM support_tickets WHERE id=? AND user_id=? AND status="open"',(tid,uid),True)
        if not t:return await cq.answer('تیکت پیدا نشد',show_alert=True)
        set_state(ctx,'addticket',tid); await cq.answer(); return await cq.edit_message_text('پیامت را بفرست.')
    if d.startswith('addtkreply:'):
        if not is_admin(uid): return await cq.answer('دسترسی ندارید',show_alert=True)
        tid=int(d.split(':')[1]); t=q('SELECT * FROM support_tickets WHERE id=? AND status="open"',(tid,),True)
        if not t:return await cq.answer('تیکت پیدا نشد یا بسته است',show_alert=True)
        set_state(ctx,'addticketreply',tid); await cq.answer()
        return await cq.edit_message_text(
            f'↩️ پاسخ تیکت #{tid} را بفرست:',
            reply_markup=added_ticket_kb(tid,True)
        )
    if d.startswith('addtkclose:'):
        tid=int(d.split(':')[1]); t=q('SELECT * FROM support_tickets WHERE id=?',(tid,),True)
        if not t or (t['user_id']!=uid and not is_admin(uid)): return await cq.answer('دسترسی ندارید',show_alert=True)
        ex('UPDATE support_tickets SET status="closed",updated=? WHERE id=?',(int(time.time()),tid)); added_audit(uid,'ticket_close',tid); clear_state(ctx); await cq.answer('تیکت بسته شد')
        return await cq.edit_message_text(f'✅ تیکت #{tid} بسته شد.')

async def added_ticket_message(update,ctx):
    st=ctx.user_data.get('state') or []
    if not st or st[0] not in ('addticket', 'addticketreply') or not update.message or not update.message.text:return
    uid=update.effective_user.id; tid=int(st[1]); t=q('SELECT * FROM support_tickets WHERE id=? AND status="open"',(tid,),True)
    if not t or (t['user_id']!=uid and not is_admin(uid)):return
    body=update.message.text.strip()
    if not body:return
    ex('INSERT INTO support_messages(ticket_id,sender_id,body,created) VALUES(?,?,?,?)',(tid,uid,body,int(time.time())))
    ex('UPDATE support_tickets SET updated=?,admin_id=? WHERE id=?',(int(time.time()),uid if is_admin(uid) else 0,tid)); added_audit(uid,'ticket_message',tid,body)
    if is_admin(uid) and st[0] == 'addticketreply':
        try: await ctx.bot.send_message(t['user_id'],f'📩 پاسخ تیکت #{tid}:\n{html.escape(body)}',parse_mode=ParseMode.HTML)
        except Exception:pass
        await update.message.reply_text('✅ پیام شما به کاربر ارسال شد.',reply_markup=added_ticket_kb(tid,True))
        try:
            await ctx.bot.send_message(
                t['user_id'],
                f'📩 <b>پاسخ پشتیبانی برای تیکت #{tid}</b>\n\n{html.escape(body)}',
                parse_mode=ParseMode.HTML,
                reply_markup=added_ticket_kb(tid,False)
            )
        except Exception:
            pass
    elif is_admin(uid):
        try: await ctx.bot.send_message(t['user_id'],f'📩 پاسخ تیکت #{tid}:\n{html.escape(body)}',parse_mode=ParseMode.HTML)
        except Exception:pass
        await update.message.reply_text('✅ پاسخ ثبت و برای کاربر ارسال شد.',reply_markup=added_ticket_kb(tid,True))
    else:
        for a in ADMIN_IDS:
            try: await ctx.bot.send_message(a,f'🎫 پیام جدید در تیکت #{tid} از کاربر {uid}:\n{html.escape(body)}',
                                            parse_mode=ParseMode.HTML, reply_markup=added_ticket_kb(tid,True))
            except Exception:pass
        await update.message.reply_text('✅ پیام ثبت شد. منتظر پاسخ پشتیبانی باش.')
    clear_state(ctx)

async def added_backup(update,ctx):
    if not is_admin(update.effective_user.id):return
    stamp=dt.datetime.now().strftime('%Y%m%d_%H%M%S'); path=f'{DB_PATH}.backup_{stamp}'; CON.commit(); shutil.copy2(DB_PATH,path); added_audit(update.effective_user.id,'database_backup',path)
    with open(path,'rb') as f: await update.message.reply_document(f,filename=path,caption='✅ بکاپ دیتابیس آماده شد.')

async def added_report(update,ctx):
    if not is_admin(update.effective_user.id):return
    now=int(time.time()); day=now-86400
    users=q('SELECT COUNT(*) c FROM users',one=True)['c']; active=q("SELECT COUNT(*) c FROM services WHERE status='active' AND expire>?",(now,),True)['c']; sales=q("SELECT COALESCE(SUM(price),0) s FROM services WHERE created>? AND status!='deleted'",(day,),True)['s']; topups=q("SELECT COALESCE(SUM(amount),0) s FROM payments WHERE created>? AND status='ok'",(day,),True)['s']; tickets=q("SELECT COUNT(*) c FROM support_tickets WHERE status='open'",one=True)['c']
    added_audit(update.effective_user.id,'daily_report'); await update.message.reply_text(f'📊 گزارش ۲۴ ساعت اخیر\n\nکاربران: {users}\nسرویس فعال: {active}\nفروش: {money(sales)} تومان\nشارژ تأییدشده: {money(topups)} تومان\nتیکت باز: {tickets}')

async def added_panel_integration_test(update, ctx):
    """تست اتصال همه پنل‌های ثبت‌شده؛ فقط خواندنی و بدون ساخت/حذف سرویس."""
    if not is_admin(update.effective_user.id):
        return
    panels = q("SELECT * FROM panels ORDER BY id")
    if not panels:
        return await update.message.reply_text("🔌 هیچ پنلی برای تست ثبت نشده است.")
    out = ["🧪 <b>تست اتصال پنل‌ها</b>"]
    for p in panels:
        if not p["active"]:
            out.append(f"⏸ {html.escape(p['name'])} ({p['ptype']}): غیرفعال")
            continue
        ok, msg = await panel_test(p)
        clean = re.sub(r"<[^>]+>", "", msg or "")
        out.append(f"{'✅' if ok else '❌'} {html.escape(p['name'])} ({p['ptype']}): {html.escape(clean)}")
        added_audit(update.effective_user.id, "panel_integration_test", p["id"], f"ok={ok}")
    await update.message.reply_text("\n".join(out), parse_mode=ParseMode.HTML)

def main():
    init_db()
    init_db_extra()  # ➕ جدول‌های کد تخفیف / تراکنش / نام سرویس
    import asyncio
    asyncio.get_event_loop().run_until_complete(init_added_features())
    load_admins()  # ➕
    app = Application.builder().token(BOT_TOKEN).build()
    app.post_init = ip_server_start  # ➕ وب‌سرور اطلاعات IP
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("emoji", cmd_emoji))
    app.add_handler(CommandHandler("ticket", added_ticket_open))
    app.add_handler(CommandHandler("tickets", added_tickets))
    app.add_handler(CommandHandler("backup", added_backup))
    app.add_handler(CommandHandler("report", added_report))
    app.add_handler(CommandHandler("paneltest", added_panel_integration_test))
    app.add_handler(CallbackQueryHandler(added_ticket_callback, pattern=r"^addtk"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, added_ticket_message), group=-1)
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(~filters.COMMAND, on_message))
    app.job_queue.run_repeating(job_followup, interval=300, first=30)
    log.info("bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

# ═══════════════════════════════════════════════════════════════════════════════════════
# ➕➕ افزودنی‌های نسخه جدید
# این بلوک فقط «اضافه» شده است. هیچ خطی از کد قبلی حذف یا ویرایش نشده؛
# قابلیت‌های جدید با پوشاندن (wrap) توابع قبلی اضافه می‌شوند و در آخر همان تابع قبلی صدا زده می‌شود.
# ═══════════════════════════════════════════════════════════════════════════════════════
import contextvars

# ---------- ایموجی‌های دکمه‌های جدید (در پنل ایموجی پریمیوم نمایش داده می‌شوند) ----------
EMOJI.update({
    "profile": "🪪", "pending": "🧾", "audit": "📜", "backup": "💾", "autobackup": "⏱", "report": "📈",
    "paneltest": "🧪", "maintenance": "🚧", "forcejoin": "📌", "gateway": "🏦", "groups": "👥", "bc2": "📣",
    "mytickets": "🗂", "zarinpal": "💠", "crypto": "💎", "verify": "🔍", "files": "📎", "addgb": "📶",
    "adddays": "📅", "manualsvc": "🛠", "msg": "✉️", "history": "📚", "newticket": "🆕",
})

# ---------- گروه رنگ دکمه‌های جدید (در پنل رنگ دکمه‌ها نمایش داده می‌شوند) ----------
for _k, _n in {"nup": "دکمه‌های پروفایل کاربر (ادمین)", "nsv": "لیست سرویس‌های کاربر (ادمین)",
               "nrc": "لیست رسیدهای در انتظار (ادمین)", "ngp": "لیست گروه‌های کاربری (ادمین)",
               "nmk": "دکمه‌های ساخت سرویس دستی (ادمین)", "nmt": "لیست تیکت‌های من",
               "nbc": "دکمه‌های پیام همگانی پیشرفته (ادمین)", "nzp": "دکمه‌های پرداخت آنلاین",
               "ncr": "دکمه‌های پرداخت ارز دیجیتال"}.items():
    if _k not in BTN_GROUPS and _n not in BTN_NAMES:
        BTN_GROUPS[_k] = _n; BTN_NAMES.append(_n)

# ---------- تنظیمات جدید ----------
DEFAULT_SETTINGS.update({
    "mnt_on": "0", "fj_on": "0", "fj_chat": "", "fj_url": "",
    "zp_on": "0", "zp_merchant": "", "zp_sandbox": "0", "zp_callback": "",
    "cr_on": "0", "cr_wallet": "", "cr_network": "USDT (TRC20)", "cr_rate": "",
    "abk_on": "0", "abk_hours": "24", "abk_last": "0", "groups": "",
})
SETTING_TITLES.update({
    "fj_chat": "آیدی کانال عضویت اجباری (مثل @channel یا -100...)",
    "fj_url": "لینک عضویت کانال (اختیاری)",
    "zp_merchant": "مرچنت کد زرین‌پال", "zp_callback": "آدرس بازگشت درگاه (اختیاری)",
    "cr_wallet": "آدرس کیف پول ارز دیجیتال", "cr_network": "شبکه/ارز (مثل USDT TRC20)",
    "cr_rate": "قیمت هر واحد ارز به تومان", "abk_hours": "فاصله بکاپ خودکار (ساعت)",
})

# ---------- متن‌های جدید (از ویرایش متن‌ها قابل تغییرند) ----------
TEXTS.update({
    "maintenance": ("حالت تعمیرات", "🚧 <b>ربات در حال بروزرسانی است</b>\n\nلطفاً کمی بعد دوباره سر بزنید. {E:bot}"),
    "force_join": ("عضویت اجباری",
        "{E:forcejoin} <b>عضویت در کانال</b>\n\nبرای استفاده از ربات، اول در کانال ما عضو شوید و بعد دکمه «عضو شدم» را بزنید."),
    "zp_pay": ("پرداخت آنلاین",
        "{E:zarinpal} <b>پرداخت آنلاین</b>\n<blockquote>مبلغ: <b>{PRICE}</b> تومان</blockquote>\n\n"
        "۱. روی «پرداخت آنلاین» بزنید و پرداخت را انجام دهید.\n۲. بعد از پرداخت، «بررسی پرداخت» را بزنید."),
    "crypto_pay": ("پرداخت ارز دیجیتال",
        "{E:crypto} <b>پرداخت با ارز دیجیتال</b>\n<blockquote>مبلغ: <b>{PRICE}</b> تومان\n"
        "معادل: <b>{AMOUNT}</b>\nشبکه: <b>{NETWORK}</b>\nآدرس کیف پول:\n<code>{WALLET}</code></blockquote>\n\n"
        "بعد از واریز، <b>اسکرین‌شات تراکنش</b> را بفرستید (TXID را در کپشن بنویسید)."),
    "my_tickets": ("تیکت‌های من", "{E:mytickets} <b>تیکت‌های من</b>\nروی هر تیکت بزن تا تاریخچه‌اش را ببینی."),
})

NX_PREFIXES_ADMIN = {"nx", "nup", "nsv", "nrc", "ngp", "nmk", "nbc"}
NX_PREFIXES_USER = {"nmt", "nzp", "nzv", "ncr"}
NX_STATES_ADMIN = {"nxprof", "nxbal", "nxmsg", "nxsvadd", "ngpadd", "ngpset", "nxbc"}
NX_STATES_USER = {"nxcrypto"}
_NX_FJ_CACHE = {}
_NX_EXTRA = contextvars.ContextVar("nx_extra_rows", default=None)


def nx_init_db():
    CON.executescript("""
    CREATE TABLE IF NOT EXISTS support_files(id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id INTEGER,
        sender_id INTEGER, file_id TEXT, kind TEXT, caption TEXT, created INTEGER);
    CREATE TABLE IF NOT EXISTS gw_payments(id INTEGER PRIMARY KEY AUTOINCREMENT, authority TEXT, user_id INTEGER,
        amount INTEGER, bonus INTEGER DEFAULT 0, status TEXT DEFAULT 'pending', ref_id TEXT, created INTEGER);
    """)
    CON.commit()


def nx_digits(t):
    return (t or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")).replace(",", "").strip()


class _NxShim:
    """برای صدا زدن دستورهای قبلی (/backup ، /report ، /paneltest) از روی دکمه."""
    def __init__(self, update):
        self.effective_user = update.effective_user
        self.effective_chat = update.effective_chat
        self.message = update.callback_query.message
        self.callback_query = None


# ---------- پوشاندن show: اضافه کردن ردیف دکمه جدید به صفحه‌های قبلی، قبل از دکمه بازگشت ----------
_nx_orig_show = show
async def show(update, text, kb=None):
    extra = _NX_EXTRA.get()
    if extra and kb is not None:
        _NX_EXTRA.set(None)
        kb = list(kb); pos = max(len(kb) - 1, 0); kb[pos:pos] = extra
    return await _nx_orig_show(update, text, kb)


def _nx_with_extra(fn, rows_fn):
    async def wrapper(*a, **k):
        try: rows = rows_fn(*a, **k)
        except Exception as e: log.warning("nx extra rows: %s", e); rows = None
        tok = _NX_EXTRA.set(rows or None)
        try: return await fn(*a, **k)
        finally: _NX_EXTRA.reset(tok)
    wrapper.__name__ = getattr(fn, "__name__", "wrapper")
    return wrapper


def _nx_support_rows(update, ctx):
    return [row(btn("تیکت‌های من", "nmt:list", BLUE, "mytickets"))]


def _nx_receipt_rows(update, ctx, amount, gift):
    g = 1 if gift else 0; rows = []
    if S("zp_on") == "1" and S("zp_merchant"):
        rows.append(row(btn("پرداخت آنلاین (زرین‌پال)", f"nzp:{amount}:{g}", GREEN, "zarinpal")))
    if S("cr_on") == "1" and S("cr_wallet"):
        rows.append(row(btn("پرداخت با ارز دیجیتال", f"ncr:{amount}:{g}", BLUE, "crypto")))
    return rows


added_support_menu = _nx_with_extra(added_support_menu, _nx_support_rows)
ask_receipt = _nx_with_extra(ask_receipt, _nx_receipt_rows)


# ---------- منوی ادمین: دکمه‌های جدید قبل از «بازگشت» ----------
_nx_orig_admin_kb = admin_kb
def admin_kb():
    kb = _nx_orig_admin_kb()
    extra = [
        row(btn("پروفایل کاربر", "nx:prof", BLUE, "profile"), btn("رسیدهای در انتظار", "nx:pend", GREEN, "pending")),
        row(btn("تیکت‌های پشتیبانی", "addtks", BLUE, "ticket"), btn("لاگ ادمین‌ها", "nx:audit", None, "audit")),
        row(btn("بکاپ دیتابیس", "nx:bk", None, "backup"), btn("بکاپ خودکار", "nx:abk", None, "autobackup")),
        row(btn("گزارش ۲۴ ساعته", "nx:rep", None, "report"), btn("تست اتصال پنل‌ها", "nx:ptest", None, "paneltest")),
        row(btn("حالت تعمیرات", "nx:mnt", None, "maintenance"), btn("عضویت اجباری", "nx:fj", None, "forcejoin")),
        row(btn("درگاه و ارز دیجیتال", "nx:gw", None, "gateway"), btn("گروه‌های کاربری", "nx:grp", None, "groups")),
        row(btn("پیام همگانی پیشرفته", "nx:bc", BLUE, "bc2")),
    ]
    return kb[:-1] + extra + kb[-1:]


# ---------- تخفیف گروه کاربری (روی قیمت بعد از کد تخفیف اعمال می‌شود) ----------
def nx_groups():
    return [g for g in (S("groups") or "").split("|") if g]

def nx_group_pct(g):
    try: return max(0, min(100, int(S("grp_pct:" + (g or "عادی")) or 0)))
    except Exception: return 0

_nx_orig_dc_price = dc_price
def dc_price(uid, price):
    final, line, code = _nx_orig_dc_price(uid, price)
    try:
        u = get_user(uid); g = (u["grp"] if u else None) or "عادی"; pct = nx_group_pct(g)
        if pct and final > 0:
            off = final * pct // 100; final = final - off
            line += (f"\n\n<blockquote>{E('groups')} تخفیف گروه <b>{html.escape(g)}</b>: <b>{pct}%</b> ({money(off)} تومان)\n"
                     f"{E('ok')} مبلغ نهایی: <b>{money(final)}</b> تومان</blockquote>")
    except Exception as e:
        log.warning("group price: %s", e)
    return final, line, code


# ---------- فایل/عکس در تیکت ----------
def _nx_ticket_files(tid):
    return q("SELECT * FROM support_files WHERE ticket_id=? ORDER BY id", (tid,))

_nx_orig_ticket_kb = added_ticket_kb
def added_ticket_kb(tid, admin=False):
    kb = _nx_orig_ticket_kb(tid, admin)
    try:
        if _nx_ticket_files(tid):
            rows = [list(r) for r in kb.inline_keyboard]
            rows.insert(len(rows) - 1 if admin else len(rows), [btn("فایل‌های تیکت", f"nmt:f:{tid}", None, "files")])
            return IKM(rows)
    except Exception as e:
        log.warning("ticket kb: %s", e)
    return kb


async def nx_ticket_file(update, ctx, uid, st):
    m = update.effective_message; tid = int(st[1])
    t = q("SELECT * FROM support_tickets WHERE id=? AND status='open'", (tid,), True)
    if not t or (t["user_id"] != uid and not is_admin(uid)): clear_state(ctx); return await m.reply_text("تیکت پیدا نشد یا بسته است.")
    if m.photo: fid, kind = m.photo[-1].file_id, "photo"
    else: fid, kind = m.document.file_id, "document"
    cap = (m.caption or "").strip(); now = int(time.time())
    ex("INSERT INTO support_files(ticket_id,sender_id,file_id,kind,caption,created) VALUES(?,?,?,?,?,?)", (tid, uid, fid, kind, cap, now))
    ex("INSERT INTO support_messages(ticket_id,sender_id,body,created) VALUES(?,?,?,?)",
       (tid, uid, ("📷 [عکس] " if kind == "photo" else "📎 [فایل] ") + cap, now))
    ex("UPDATE support_tickets SET updated=? WHERE id=?", (now, tid)); added_audit(uid, "ticket_file", tid, kind)
    send = (lambda chat, **k: ctx.bot.send_photo(chat, fid, **k)) if kind == "photo" else (lambda chat, **k: ctx.bot.send_document(chat, fid, **k))
    if is_admin(uid) and t["user_id"] != uid:
        try: await send(t["user_id"], caption=f"📩 پاسخ پشتیبانی برای تیکت #{tid}\n{cap}"[:1000], reply_markup=added_ticket_kb(tid, False))
        except Exception as e: log.warning("ticket file to user: %s", e)
        await m.reply_text("✅ فایل برای کاربر ارسال شد.", reply_markup=added_ticket_kb(tid, True))
    else:
        for a in ADMIN_IDS:
            try: await send(a, caption=f"🎫 فایل جدید در تیکت #{tid} از کاربر {uid}\n{cap}"[:1000], reply_markup=added_ticket_kb(tid, True))
            except Exception: pass
        await m.reply_text("✅ فایل ثبت شد. منتظر پاسخ پشتیبانی باش.")
    clear_state(ctx)


async def nx_my_tickets(update, uid):
    rows = q("SELECT * FROM support_tickets WHERE user_id=? ORDER BY id DESC LIMIT 20", (uid,))
    kb = [row(btn(f"{'🟢' if r['status'] == 'open' else '🔒'} #{r['id']} | {jdate(r['created'])}", f"nmt:v:{r['id']}")) for r in rows]
    kb += [row(btn("باز کردن تیکت", "addtkopen", BLUE, "newticket")), row(btn("بازگشت", "supportmenu", RED, "back"))]
    await show(update, render("my_tickets") + ("" if rows else "\n\nهنوز تیکتی نداری."), kb)


async def nx_my_ticket_view(update, uid, tid):
    t = q("SELECT * FROM support_tickets WHERE id=?", (tid,), True)
    if not t or (t["user_id"] != uid and not is_admin(uid)): return await nx_my_tickets(update, uid)
    text = added_ticket_text(tid) or "تیکت پیدا نشد."
    if len(text) > 3900: text = text[:3900] + "\n…"
    kb = [list(r) for r in added_ticket_kb(tid, False).inline_keyboard] if t["status"] == "open" else []
    if t["status"] != "open" and _nx_ticket_files(tid): kb.append([btn("فایل‌های تیکت", f"nmt:f:{tid}", None, "files")])
    kb += [row(btn("بازگشت", "nmt:list", RED, "back"))]
    await show(update, text, kb)


# ---------- عضویت اجباری و حالت تعمیرات ----------
def nx_maint_block(uid):
    return S("mnt_on") == "1" and not is_admin(uid)

def _nx_plain(t):
    return re.sub(r"<[^>]+>", "", t or "")[:190]

async def nx_fj_ok(bot, uid):
    chat = (S("fj_chat") or "").strip()
    if S("fj_on") != "1" or not chat or is_admin(uid): return True
    if time.time() - _NX_FJ_CACHE.get(uid, 0) < 60: return True
    try:
        mem = await bot.get_chat_member(chat, uid)
        ok = mem.status in ("member", "administrator", "creator", "owner") or (mem.status == "restricted" and getattr(mem, "is_member", False))
    except Exception as e:
        log.warning("force join check (ربات باید ادمین کانال باشد): %s", e); return True
    if ok: _NX_FJ_CACHE[uid] = time.time()
    return ok

def nx_fj_kb():
    chat = (S("fj_chat") or "").strip()
    link = S("fj_url") or (f"https://t.me/{chat[1:]}" if chat.startswith("@") else S("channel_url"))
    return [row(btn("عضویت در کانال", url=link, ek="channel")), row(btn("عضو شدم", "nfj:check", GREEN, "ok"))]


_nx_orig_cmd_start = cmd_start
async def cmd_start(update, ctx):
    uid = update.effective_user.id
    ref = None
    if ctx.args and ctx.args[0].startswith("ref_") and ctx.args[0][4:].isdigit(): ref = int(ctx.args[0][4:])
    u = touch(update.effective_user, ref)  # ثبت معرف حتی اگر کاربر هنوز عضو کانال نشده باشد
    if u["banned"]: return await _nx_orig_cmd_start(update, ctx)
    if nx_maint_block(uid):
        return await update.message.reply_text(render("maintenance"), parse_mode=ParseMode.HTML)
    if not await nx_fj_ok(ctx.bot, uid):
        clear_state(ctx)
        return await update.message.reply_text(render("force_join"), parse_mode=ParseMode.HTML, reply_markup=IKM(nx_fj_kb()))
    return await _nx_orig_cmd_start(update, ctx)


# ---------- پروفایل کاربر (ادمین) ----------
async def nx_profile(update, tid):
    u = get_user(tid)
    if not u: return await show(update, "کاربر پیدا نشد.", admin_back())
    now = int(time.time())
    act = q("SELECT COUNT(*) c FROM services WHERE user_id=? AND status='active' AND expire>?", (tid, now), True)["c"]
    tot = q("SELECT COUNT(*) c FROM services WHERE user_id=? AND status!='deleted'", (tid,), True)["c"]
    paid = q("SELECT COALESCE(SUM(amount),0) s FROM payments WHERE user_id=? AND status='ok'", (tid,), True)["s"]
    spent = q("SELECT COALESCE(SUM(amount),0) s FROM txlog WHERE user_id=?", (tid,), True)["s"]
    refs = q("SELECT COUNT(*) c FROM users WHERE ref_by=?", (tid,), True)["c"]
    pend = q("SELECT COUNT(*) c FROM payments WHERE user_id=? AND status='pending'", (tid,), True)["c"]
    tks = q("SELECT COUNT(*) c FROM support_tickets WHERE user_id=?", (tid,), True)["c"]
    g = u["grp"] or "عادی"
    t = (f"{E('profile')} <b>پروفایل کاربر</b>\n<blockquote>🆔 آیدی: <code>{tid}</code>\n"
         f"👤 نام: <b>{html.escape(u['name'] or '-')}</b>\n🔗 یوزرنیم: {('@' + html.escape(u['username'])) if u['username'] else '-'}\n"
         f"{E('phone')} شماره: {html.escape(u['phone'] or 'ثبت نشده')}\n👥 گروه: <b>{html.escape(g)}</b> ({nx_group_pct(g)}% تخفیف)\n"
         f"🚦 وضعیت: <b>{'🚫 مسدود' if u['banned'] else '✅ فعال'}</b>\n🕒 عضویت: {jdate(u['created'])}\n"
         f"👀 آخرین بازدید: {jdate(u['last_seen'])}</blockquote>\n"
         f"<blockquote>{E('wallet')} موجودی: <b>{money(u['balance'])}</b> تومان\n"
         f"{E('plan')} سرویس فعال: <b>{act}</b> از <b>{tot}</b>\n💳 شارژ تأییدشده: <b>{money(paid)}</b> تومان\n"
         f"🛒 خرید/تمدید: <b>{money(spent)}</b> تومان\n🧾 رسید در انتظار: <b>{pend}</b>\n"
         f"{E('ref')} زیرمجموعه: <b>{refs}</b> | معرف: <code>{u['ref_by'] or '-'}</code>\n🎫 تیکت‌ها: <b>{tks}</b></blockquote>")
    kb = [row(btn("افزایش موجودی کاربر", f"nup:add:{tid}", GREEN, "addbal"), btn("کسر موجودی کاربر", f"nup:sub:{tid}", RED, "subbal")),
          row(btn("آن‌بن کاربر", f"nup:ban:{tid}", GREEN, "unban") if u["banned"] else btn("بن کاربر", f"nup:ban:{tid}", RED, "ban")),
          row(btn("سرویس‌های کاربر", f"nup:svc:{tid}", BLUE, "subs"), btn("ساخت سرویس دستی", f"nup:mk:{tid}", GREEN, "manualsvc")),
          row(btn("تراکنش‌های کاربر", f"nup:trx:{tid}", None, "trx"), btn("تغییر گروه کاربر", f"nup:grp:{tid}", None, "groups")),
          row(btn("ارسال پیام به کاربر", f"nup:msg:{tid}", None, "msg"), btn("تیکت‌های کاربر", f"nup:tk:{tid}", None, "ticket")),
          row(btn("بروزرسانی پروفایل", f"nup:v:{tid}", None, "search"))] + admin_back()
    await show(update, t, kb)


async def nx_user_services(update, tid):
    rows = q("SELECT * FROM services WHERE user_id=? AND status!='deleted' ORDER BY id DESC LIMIT 30", (tid,))
    now = time.time()
    kb = [row(btn(f"{'🟢' if s['status'] == 'active' and s['expire'] > now else ('⏳' if s['status'] == 'pending' else '🔴')} "
                  f"{(s['title'] if 'title' in s.keys() and s['title'] else s['username'])} | {s['gb']}GB", f"nsv:v:{s['id']}")) for s in rows]
    kb += [row(btn("بازگشت به پروفایل", f"nup:v:{tid}", RED, "back"))]
    await show(update, f"{E('subs')} <b>سرویس‌های کاربر</b> <code>{tid}</code>" + ("" if rows else "\n\nسرویسی ندارد."), kb)


async def nx_service_view(update, sid):
    s = q("SELECT * FROM services WHERE id=?", (sid,), True)
    if not s: return await show(update, "سرویس پیدا نشد.", admin_back())
    pn = q("SELECT * FROM panels WHERE id=?", (s["panel_id"],), True)
    t = (f"{E('plan')} <b>{svc_name(s)}</b>\n<blockquote>👤 کاربر: <code>{s['user_id']}</code>\n"
         f"📍 پنل: {html.escape(pn['name'] if pn else '-')}\n{E('volume')} حجم: {s['gb']} گیگ\n"
         f"{E('time')} انقضا: {jdate(s['expire'])}\n🚦 وضعیت: {s['status']}{' (تست)' if s['is_test'] else ''}\n"
         f"{E('price')} مبلغ: {money(s['price'] or 0)} تومان</blockquote>\n"
         f"{E('link')} <code>{html.escape((s['sub'] or s['link'] or '-')[:900])}</code>")
    kb = [row(btn("افزایش حجم", f"nsv:gb:{sid}", GREEN, "addgb"), btn("افزایش روز", f"nsv:dy:{sid}", GREEN, "adddays")),
          row(btn("بازگشت به سرویس‌ها", f"nup:svc:{s['user_id']}", RED, "back"))]
    await show(update, t, kb)


async def panel_edit(p, username, gb, exp):
    """ویرایش حجم/انقضا روی پنل بدون ریست مصرف (برخلاف تمدید)."""
    t = p["ptype"]; limit = int(float(gb) * 1024 ** 3); exp = int(exp)
    async with _http(p) as c:
        if t in ("marzban", "pasarguard"):
            h = await _token(c, p)
            body = {"expire": exp, "data_limit": limit, "status": "active"}
            r = await c.put(f"/api/user/{username}", json=body, headers=h)
            if t == "pasarguard" and r.status_code == 422:
                body["expire"] = dt.datetime.fromtimestamp(exp, dt.timezone.utc).isoformat()
                r = await c.put(f"/api/user/{username}", json=body, headers=h)
            if r.status_code >= 400: raise Exception(f"HTTP {r.status_code}: {r.text[:300]}")
        elif t == "marzneshin":
            h = await _token(c, p)
            body = {"username": username, "expire_strategy": "fixed_date", "data_limit": limit,
                    "expire_date": dt.datetime.fromtimestamp(exp, dt.timezone.utc).isoformat()}
            r = await c.put(f"/api/users/{username}", json=body, headers=h)
            if r.status_code >= 400: raise Exception(f"HTTP {r.status_code}: {r.text[:300]}")
        elif t in XUI_PREFIX:
            await _xlogin(c, p)
            inb, inbound, client = await _xui_find(c, t, p, username)
            if not client: raise Exception("کلاینت روی پنل پیدا نشد")
            client.update({"totalGB": limit, "expiryTime": exp * 1000, "enable": True})
            r = await c.post(f"{XUI_PREFIX[t]}/updateClient/{_xui_cid(inbound, client)}",
                             data={"id": inb, "settings": json.dumps({"clients": [client]})})
            j = r.json()
            if not j.get("success"): raise Exception(j.get("msg") or "updateClient failed")
        else:
            raise Exception("نوع پنل پشتیبانی نمی‌شود")


async def nx_service_add(update, ctx, uid, sid, kind, val):
    s = q("SELECT * FROM services WHERE id=?", (sid,), True)
    if not s: return await update.effective_message.reply_text("سرویس پیدا نشد.")
    pn = q("SELECT * FROM panels WHERE id=?", (s["panel_id"],), True)
    gb = float(s["gb"] or 0) + (val if kind == "gb" else 0)
    exp = int(max(time.time(), s["expire"] or 0) + val * 86400) if kind == "dy" else int(s["expire"] or time.time())
    gb_db = int(gb) if float(gb).is_integer() else gb
    try:
        if pn and pn["ptype"] != "manual" and s["status"] != "pending":
            await panel_edit(pn, s["username"], gb, exp)
    except Exception as e:
        log.exception("panel edit")
        return await update.effective_message.reply_text(f"❌ خطای پنل: {html.escape(str(e))[:400]}", parse_mode=ParseMode.HTML,
                                                         reply_markup=IKM([row(btn("بازگشت به سرویس", f"nsv:v:{sid}", RED, "back"))]))
    ex("UPDATE services SET gb=?, expire=?, status=CASE WHEN status='expired' THEN 'active' ELSE status END, mid_sent=0 WHERE id=?",
       (gb_db, exp, sid))
    added_audit(uid, "service_add_" + kind, sid, val)
    try: await ctx.bot.send_message(s["user_id"], f"🎁 به سرویس <code>{html.escape(s['username'])}</code> "
                                    f"{('%s گیگ حجم' % val) if kind == 'gb' else ('%s روز' % val)} اضافه شد.", parse_mode=ParseMode.HTML)
    except Exception: pass
    await update.effective_message.reply_text("✅ انجام شد.", reply_markup=IKM([row(btn("بازگشت به سرویس", f"nsv:v:{sid}", BLUE, "back"))]))


async def nx_user_trx(update, tid):
    lines = [f"{E('trx')} <b>تراکنش‌های کاربر</b> <code>{tid}</code>"]
    tx = q("SELECT * FROM txlog WHERE user_id=? ORDER BY id DESC LIMIT 15", (tid,))
    if tx:
        lines.append("\n🛒 <b>خرید/تمدید</b><blockquote>" + "\n".join(
            f"{jdate(r['created'])} | {r['kind']} | {money(r['amount'])} تومان" + (f" | کد {html.escape(r['code'])}" if r['code'] else "")
            for r in tx) + "</blockquote>")
    pays = q("SELECT * FROM payments WHERE user_id=? ORDER BY id DESC LIMIT 15", (tid,))
    if pays:
        st = {"ok": "✅", "pending": "⏳", "rejected": "❌"}
        lines.append("\n💳 <b>شارژها</b><blockquote>" + "\n".join(
            f"{st.get(r['status'], r['status'])} #{r['id']} | {jdate(r['created'])} | {money(r['amount'])}" + (f" + {money(r['bonus'])}" if r['bonus'] else "")
            for r in pays) + "</blockquote>")
    if len(lines) == 1: lines.append("\nتراکنشی ثبت نشده.")
    await show(update, "\n".join(lines)[:4000], [row(btn("بازگشت به پروفایل", f"nup:v:{tid}", RED, "back"))])


# ---------- گروه‌های کاربری ----------
async def nx_groups_page(update):
    gs = ["عادی"] + nx_groups()
    kb = [row(btn(f"{g} | {nx_group_pct(g)}% | {q('SELECT COUNT(*) c FROM users WHERE grp=?', (g,), True)['c']} نفر", f"ngp:e:{i - 1}"))
          for i, g in enumerate(gs)]
    kb += [row(btn("افزودن گروه", "ngp:add", GREEN, "addbal"))] + admin_back()
    await show(update, f"{E('groups')} <b>گروه‌های کاربری</b>\nهر گروه درصد تخفیف خودش را روی خرید و تمدید دارد.\n"
                       "گروه هر کاربر از «پروفایل کاربر» تغییر می‌کند.", kb)

def _nx_group_by_idx(i):
    i = int(i)
    if i < 0: return "عادی"
    gs = nx_groups(); return gs[i] if i < len(gs) else None


# ---------- پرداخت آنلاین زرین‌پال ----------
def _nx_zp_base():
    return "https://sandbox.zarinpal.com" if S("zp_sandbox") == "1" else "https://payment.zarinpal.com"

async def nx_zp_request(amount_toman, uid, callback):
    body = {"merchant_id": S("zp_merchant"), "amount": int(amount_toman) * 10, "callback_url": callback,
            "description": f"شارژ کیف پول {uid}"}
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(_nx_zp_base() + "/pg/v4/payment/request.json", json=body)
    j = r.json(); d = j.get("data") or {}
    if isinstance(d, dict) and d.get("code") == 100 and d.get("authority"):
        return d["authority"], f"{_nx_zp_base()}/pg/StartPay/{d['authority']}"
    raise Exception(str(j.get("errors") or j)[:300])

async def nx_zp_verify(amount_toman, authority):
    body = {"merchant_id": S("zp_merchant"), "amount": int(amount_toman) * 10, "authority": authority}
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(_nx_zp_base() + "/pg/v4/payment/verify.json", json=body)
    j = r.json(); d = j.get("data") or {}
    if isinstance(d, dict) and d.get("code") in (100, 101): return True, str(d.get("ref_id") or "")
    return False, str(j.get("errors") or d)[:300]

async def nx_ref_share(ctx, payer_id, amount):
    payer = get_user(payer_id)
    if not payer or not payer["ref_by"]: return
    try: share = int(amount) * int(S("ref_percent") or 0) // 100
    except Exception: share = 0
    if share:
        ex("UPDATE users SET balance=balance+? WHERE id=?", (share, payer["ref_by"]))
        try: await ctx.bot.send_message(payer["ref_by"], f"🤝 {money(share)} تومان پاداش زیرمجموعه گرفتی!")
        except Exception: pass


# ---------- پیام همگانی پیشرفته ----------
async def nx_broadcast(update, ctx, uid, mode, target):
    m = update.effective_message; now = int(time.time())
    if target == "act":
        ids = [r["user_id"] for r in q("SELECT DISTINCT user_id FROM services WHERE status='active' AND expire>?", (now,))]
        banned = {r["id"] for r in q("SELECT id FROM users WHERE banned=1")}; ids = [i for i in ids if i not in banned]
    else:
        ids = [r["id"] for r in q("SELECT id FROM users WHERE banned=0")]
    prog = await m.reply_text(f"⏳ در حال ارسال برای {len(ids)} نفر...")
    ok = blocked = fail = 0
    for n, cid in enumerate(ids, 1):
        try:
            if mode == "fwd": await m.forward(cid)
            else: await m.copy(cid)
            ok += 1
        except Exception as e:
            s = (type(e).__name__ + " " + str(e)).lower()
            if "forbidden" in s or "blocked" in s or "deactivated" in s: blocked += 1
            else: fail += 1
        if n % 50 == 0:
            try: await prog.edit_text(f"⏳ {n} از {len(ids)} | موفق {ok} | بلاک {blocked} | خطا {fail}")
            except Exception: pass
        await asyncio.sleep(0.04)
    added_audit(uid, "broadcast_" + mode, target, f"ok={ok} blocked={blocked} fail={fail}")
    return await m.reply_text(f"📣 <b>گزارش پیام همگانی</b>\n<blockquote>کل: {len(ids)}\n✅ موفق: {ok}\n"
                              f"🚫 ربات را بلاک کرده‌اند: {blocked}\n⚠️ خطا: {fail}</blockquote>",
                              parse_mode=ParseMode.HTML, reply_markup=IKM(admin_kb()))


# ---------- بکاپ خودکار (داخل همان کار زمان‌بندی‌شده قبلی) ----------
async def nx_auto_backup(ctx):
    if S("abk_on") != "1": return
    try: hours = max(1, int(nx_digits(S("abk_hours")) or 24))
    except Exception: hours = 24
    now = int(time.time())
    try: last = int(S("abk_last") or 0)
    except Exception: last = 0
    if now - last < hours * 3600: return
    set_S("abk_last", now)
    try:
        stamp = dt.datetime.now().strftime('%Y%m%d_%H%M%S'); path = f"{DB_PATH}.auto_{stamp}"
        CON.commit(); shutil.copy2(DB_PATH, path); added_audit(0, "auto_backup", path)
        for a in {MAIN_ADMIN_ID} | set(ENV_ADMIN_IDS):
            try:
                with open(path, "rb") as f:
                    await ctx.bot.send_document(a, f, filename=os.path.basename(path), caption="💾 بکاپ خودکار دیتابیس")
            except Exception as e: log.warning("auto backup send %s: %s", a, e)
    except Exception as e:
        log.warning("auto backup: %s", e)

_nx_orig_job_followup = job_followup
async def job_followup(ctx):
    try: await _nx_orig_job_followup(ctx)
    finally: await nx_auto_backup(ctx)


# ---------- مسیریابی دکمه‌های جدید ----------
async def nx_callback(update, ctx, uid, d):
    cq = update.callback_query; p = d.split(":")
    # ---- کاربر ----
    if p[0] == "nmt":
        if p[1] == "list": return await nx_my_tickets(update, uid)
        if p[1] == "v": return await nx_my_ticket_view(update, uid, int(p[2]))
        if p[1] == "f":
            tid = int(p[2]); t = q("SELECT * FROM support_tickets WHERE id=?", (tid,), True)
            if not t or (t["user_id"] != uid and not is_admin(uid)): return
            for f in _nx_ticket_files(tid)[:20]:
                cap = f"#{tid} | {'کاربر' if f['sender_id'] == t['user_id'] else 'پشتیبانی'} | {f['caption'] or ''}"[:1000]
                try:
                    if f["kind"] == "photo": await ctx.bot.send_photo(uid, f["file_id"], caption=cap)
                    else: await ctx.bot.send_document(uid, f["file_id"], caption=cap)
                except Exception as e: log.warning("ticket file: %s", e)
            return
    if p[0] == "nzp":
        if S("zp_on") != "1" or not S("zp_merchant"): return await show(update, "درگاه فعلاً غیرفعال است.", back_home())
        amount, gift = int(p[1]), p[2] == "1"
        bonus = amount * int(S("gift_percent")) // 100 if gift and amount >= int(S("gift_min")) else 0
        cb = S("zp_callback") or f"https://t.me/{getattr(ctx.bot, 'username', '') or BOT_REF.get('username') or ''}"
        try: auth, link = await nx_zp_request(amount, uid, cb)
        except Exception as e:
            log.warning("zarinpal request: %s", e)
            return await show(update, "❌ اتصال به درگاه ممکن نشد. از کارت به کارت استفاده کنید یا بعداً امتحان کنید.", back_home())
        gid = ex("INSERT INTO gw_payments(authority,user_id,amount,bonus,created) VALUES(?,?,?,?,?)", (auth, uid, amount, bonus, int(time.time())))
        clear_state(ctx)
        return await show(update, render("zp_pay", PRICE=money(amount)),
                          [row(btn("پرداخت آنلاین", url=link, ek="zarinpal")),
                           row(btn("بررسی پرداخت", f"nzv:{gid}", GREEN, "verify")), row(btn("انصراف", "account", RED, "no"))])
    if p[0] == "nzv":
        g = q("SELECT * FROM gw_payments WHERE id=? AND user_id=?", (int(p[1]), uid), True)
        if not g: return
        if g["status"] != "pending": return await cq.answer("این پرداخت قبلاً بررسی شده.", show_alert=True)
        ok, info = await nx_zp_verify(g["amount"], g["authority"])
        if not ok: return await cq.answer("پرداخت هنوز تأیید نشده. اگر پرداخت کردی چند لحظه بعد دوباره بزن.", show_alert=True)
        cur = CON.execute("UPDATE gw_payments SET status='ok', ref_id=? WHERE id=? AND status='pending'", (info, g["id"])); CON.commit()
        if cur.rowcount != 1: return
        total = g["amount"] + g["bonus"]
        ex("UPDATE users SET balance=balance+? WHERE id=?", (total, uid))
        pid = ex("INSERT INTO payments(user_id,amount,bonus,photo,status,created) VALUES(?,?,?,?,?,?)",
                 (uid, g["amount"], g["bonus"], f"zarinpal:{info}", "ok", int(time.time())))
        await nx_ref_share(ctx, uid, g["amount"]); added_audit(uid, "zarinpal_ok", pid, info)
        for a in ADMIN_IDS:
            try: await ctx.bot.send_message(a, f"💠 پرداخت آنلاین #{pid}\nکاربر: {uid}\nمبلغ: {money(g['amount'])} تومان\nکد پیگیری: {info}")
            except Exception: pass
        return await show(update, f"✅ پرداخت تأیید شد و {money(total)} تومان به کیف پولت اضافه شد.\nکد پیگیری: <code>{html.escape(info)}</code>", back_home())
    if p[0] == "ncr":
        if S("cr_on") != "1" or not S("cr_wallet"): return await show(update, "پرداخت ارز دیجیتال فعلاً غیرفعال است.", back_home())
        amount, gift = int(p[1]), p[2] == "1"
        try: rate = float(nx_digits(S("cr_rate")) or 0)
        except Exception: rate = 0
        amt = f"{amount / rate:.2f} {html.escape(S('cr_network').split()[0])}" if rate > 0 else "از پشتیبانی بپرسید"
        set_state(ctx, "nxcrypto", amount, gift)
        return await show(update, render("crypto_pay", PRICE=money(amount), AMOUNT=amt, NETWORK=html.escape(S("cr_network")),
                                         WALLET=html.escape(S("cr_wallet"))), [row(btn("انصراف", "account", RED, "no"))])
    if not is_admin(uid): return
    # ---- ادمین ----
    if d == "nx:prof":
        set_state(ctx, "nxprof"); return await show(update, "آیدی عددی یا یوزرنیم کاربر را بفرست:", admin_back())
    if d == "nx:pend":
        rows = q("SELECT * FROM payments WHERE status='pending' ORDER BY id DESC LIMIT 40")
        kb = [row(btn(f"#{r['id']} | {r['user_id']} | {money(r['amount'])}", f"nrc:{r['id']}")) for r in rows]
        return await show(update, f"{E('pending')} <b>رسیدهای در انتظار</b> ({len(rows)})\nروی هر رسید بزن تا عکس و دکمه تأیید/رد بیاید."
                          if rows else "✅ رسید در انتظاری نداریم.", kb + admin_back())
    if p[0] == "nrc":
        r = q("SELECT * FROM payments WHERE id=?", (int(p[1]),), True)
        if not r or r["status"] != "pending": return await cq.answer("قبلاً بررسی شده.", show_alert=True)
        u = get_user(r["user_id"])
        cap = (f"🧾 رسید #{r['id']}\nکاربر: <code>{r['user_id']}</code> ({html.escape((u['name'] if u else '') or '')})\n"
               f"مبلغ: {money(r['amount'])}{(' + هدیه ' + money(r['bonus'])) if r['bonus'] else ''} تومان\n🕒 {jdate(r['created'])}")
        kb = IKM([row(btn("تأیید", f"pa:{r['id']}", GREEN, "ok"), btn("رد", f"pr:{r['id']}", RED, "no"))])
        try: return await ctx.bot.send_photo(uid, r["photo"], caption=cap, parse_mode=ParseMode.HTML, reply_markup=kb)
        except Exception as e: return await cq.message.reply_text(f"عکس رسید باز نشد: {e}")
    if d == "nx:audit":
        rows = q("SELECT * FROM audit_log ORDER BY id DESC LIMIT 30")
        t = "\n".join(f"{jdate(r['created'])} | <code>{r['actor_id']}</code> | {html.escape(r['action'])} {html.escape(str(r['target'] or ''))[:30]}" for r in rows)
        return await show(update, f"{E('audit')} <b>لاگ ادمین‌ها (۳۰ مورد آخر)</b>\n<blockquote>{t or 'خالی'}</blockquote>"[:4000], admin_back())
    if d == "nx:bk": return await added_backup(_NxShim(update), ctx)
    if d == "nx:rep": return await added_report(_NxShim(update), ctx)
    if d == "nx:ptest":
        await cq.message.reply_text("⏳ در حال تست اتصال پنل‌ها..."); return await added_panel_integration_test(_NxShim(update), ctx)
    if d == "nx:abk":
        return await show(update, f"{E('autobackup')} <b>بکاپ خودکار</b>\nفایل دیتابیس هر چند ساعت یک‌بار برای ادمین اصلی فرستاده می‌شود.\n"
                                  f"آخرین بکاپ: {jdate(int(S('abk_last') or 0)) if S('abk_last') not in ('', '0') else '-'}",
                          settings_kb(["abk_hours"], [("abk_on", "بکاپ خودکار")]))
    if d == "nx:mnt":
        return await show(update, f"{E('maintenance')} <b>حالت تعمیرات</b>\nوقتی روشن باشد، فقط ادمین‌ها از ربات استفاده می‌کنند.",
                          [row(btn("ویرایش متن تعمیرات", "tx:maintenance", None, "text"))] + settings_kb([], [("mnt_on", "حالت تعمیرات")]))
    if d == "nx:fj":
        return await show(update, f"{E('forcejoin')} <b>عضویت اجباری</b>\nربات باید ادمین کانال باشد تا عضویت را چک کند.",
                          [row(btn("ویرایش متن عضویت اجباری", "tx:force_join", None, "text"))] +
                          settings_kb(["fj_chat", "fj_url"], [("fj_on", "عضویت اجباری")]))
    if d == "nx:gw":
        return await show(update, f"{E('gateway')} <b>درگاه پرداخت و ارز دیجیتال</b>\nگزینه‌های فعال در صفحه پرداخت کاربر کنار کارت به کارت نمایش داده می‌شوند.",
                          settings_kb(["zp_merchant", "zp_callback", "cr_wallet", "cr_network", "cr_rate"],
                                      [("zp_on", "درگاه زرین‌پال"), ("zp_sandbox", "حالت تست زرین‌پال"), ("cr_on", "پرداخت ارز دیجیتال")]))
    if d == "nx:grp": clear_state(ctx); return await nx_groups_page(update)
    if d == "nx:bc":
        return await show(update, f"{E('bc2')} <b>پیام همگانی پیشرفته</b>\nنوع ارسال و گیرنده‌ها را انتخاب کن:",
                          [row(btn("کپی برای همه", "nbc:copy:all", BLUE, "bc"), btn("فوروارد برای همه", "nbc:fwd:all", BLUE, "bc")),
                           row(btn("کپی برای دارندگان سرویس فعال", "nbc:copy:act", GREEN, "subs")),
                           row(btn("فوروارد برای دارندگان سرویس فعال", "nbc:fwd:act", GREEN, "subs"))] + admin_back())
    if p[0] == "nbc":
        set_state(ctx, "nxbc", p[1], p[2])
        return await show(update, "پیامت را بفرست (متن، عکس، ویدیو یا هر چیزی). بعد از ارسال، گزارش کامل می‌گیری.", admin_back("nx:bc"))
    if p[0] == "ngp":
        if p[1] == "add":
            set_state(ctx, "ngpadd"); return await show(update, "نام گروه و درصد تخفیف را بفرست:\n<code>VIP 10</code>", admin_back("nx:grp"))
        if p[1] == "e":
            g = _nx_group_by_idx(p[2])
            if not g: return await nx_groups_page(update)
            kb = [row(btn("تغییر درصد تخفیف", f"ngp:p:{p[2]}", BLUE, "price"))]
            if g != "عادی": kb.append(row(btn("حذف گروه", f"ngp:d:{p[2]}", RED, "no")))
            return await show(update, f"{E('groups')} گروه <b>{html.escape(g)}</b>\nتخفیف: <b>{nx_group_pct(g)}%</b>", kb + admin_back("nx:grp"))
        if p[1] == "p":
            set_state(ctx, "ngpset", p[2]); return await show(update, "درصد تخفیف جدید را بفرست (۰ تا ۱۰۰):", admin_back("nx:grp"))
        if p[1] == "d":
            g = _nx_group_by_idx(p[2])
            if g and g != "عادی":
                set_S("groups", "|".join(x for x in nx_groups() if x != g))
                ex("UPDATE users SET grp='عادی' WHERE grp=?", (g,)); added_audit(uid, "group_delete", g)
            return await nx_groups_page(update)
        if p[1] == "s":
            tid, g = int(p[2]), _nx_group_by_idx(p[3])
            if g: ex("UPDATE users SET grp=? WHERE id=?", (g, tid)); added_audit(uid, "user_group", tid, g)
            return await nx_profile(update, tid)
    if p[0] == "nup":
        act, tid = p[1], int(p[2])
        if not get_user(tid): return await show(update, "کاربر پیدا نشد.", admin_back())
        if act == "v": clear_state(ctx); return await nx_profile(update, tid)
        if act in ("add", "sub"):
            set_state(ctx, "nxbal", act, tid)
            return await show(update, f"مبلغ {'افزایش' if act == 'add' else 'کسر'} برای <code>{tid}</code> را بفرست (تومان):", [row(btn("بازگشت به پروفایل", f"nup:v:{tid}", RED, "back"))])
        if act == "ban":
            nb = 0 if get_user(tid)["banned"] else 1
            ex("UPDATE users SET banned=? WHERE id=?", (nb, tid)); added_audit(uid, "ban" if nb else "unban", tid)
            return await nx_profile(update, tid)
        if act == "svc": return await nx_user_services(update, tid)
        if act == "trx": return await nx_user_trx(update, tid)
        if act == "grp":
            gs = ["عادی"] + nx_groups()
            kb = [row(btn(f"{g} ({nx_group_pct(g)}%)", f"ngp:s:{tid}:{i - 1}", BLUE)) for i, g in enumerate(gs)]
            return await show(update, f"گروه جدید کاربر <code>{tid}</code> را انتخاب کن:", kb + [row(btn("بازگشت به پروفایل", f"nup:v:{tid}", RED, "back"))])
        if act == "msg":
            set_state(ctx, "nxmsg", tid)
            return await show(update, f"پیام برای کاربر <code>{tid}</code> را بفرست (متن/عکس/هرچی):", [row(btn("بازگشت به پروفایل", f"nup:v:{tid}", RED, "back"))])
        if act == "tk":
            rows = q("SELECT * FROM support_tickets WHERE user_id=? ORDER BY id DESC LIMIT 20", (tid,))
            kb = [row(btn(f"{'🟢' if r['status'] == 'open' else '🔒'} #{r['id']} | {jdate(r['created'])}", f"addtk:{r['id']}")) for r in rows]
            return await show(update, f"🎫 تیکت‌های کاربر <code>{tid}</code>" + ("" if rows else "\n\nتیکتی ندارد."), kb + [row(btn("بازگشت به پروفایل", f"nup:v:{tid}", RED, "back"))])
        if act == "mk":
            pans = q("SELECT * FROM panels WHERE active=1")
            kb = [row(btn(f"{x['name']} ({x['ptype']})", f"nmk:p:{tid}:{x['id']}", BLUE)) for x in pans]
            return await show(update, "پنل/لوکیشن سرویس رایگان را انتخاب کن:" if pans else "هیچ پنل فعالی نداریم.", kb + [row(btn("بازگشت به پروفایل", f"nup:v:{tid}", RED, "back"))])
    if p[0] == "nmk":
        tid, pid = int(p[2]), int(p[3])
        if p[1] == "p":
            pls = q("SELECT * FROM plans WHERE active=1 ORDER BY months, gb")
            kb = [row(btn(f"{x['months']}ماهه | {x['gb']}گیگ | {x['days']}روز", f"nmk:s:{tid}:{pid}:{x['id']}", GREEN)) for x in pls]
            return await show(update, "پلن سرویس را انتخاب کن (برای کاربر رایگان ساخته می‌شود و از موجودی کم نمی‌شود):", kb + [row(btn("بازگشت به پروفایل", f"nup:v:{tid}", RED, "back"))])
        if p[1] == "s":
            pn = q("SELECT * FROM panels WHERE id=?", (pid,), True); pl = q("SELECT * FROM plans WHERE id=?", (int(p[4]),), True)
            if not pn or not pl: return await show(update, "پنل یا پلن پیدا نشد.", admin_back())
            try: sid, manual = await build_service(ctx, tid, pn, pl["gb"], pl["days"], 0, pl["id"])
            except Exception as e:
                log.exception("admin manual service")
                return await show(update, f"❌ ساخت سرویس خطا داد: {html.escape(str(e))[:400]}", [row(btn("بازگشت به پروفایل", f"nup:v:{tid}", RED, "back"))])
            trx_log(tid, "admin", sid, pl["id"], pn["id"], pl["gb"], pl["days"], 0); added_audit(uid, "admin_service", tid, sid)
            if not manual:
                try: await deliver(ctx, tid, sid)
                except Exception as e: log.warning("deliver admin svc: %s", e)
            return await show(update, "✅ سرویس ساخته شد" + (" (دستی: لینک را از پیام سفارش بفرست)." if manual else " و برای کاربر ارسال شد."),
                              [row(btn("بازگشت به پروفایل", f"nup:v:{tid}", BLUE, "back"))])
    if p[0] == "nsv":
        sid = int(p[2])
        if p[1] == "v": clear_state(ctx); return await nx_service_view(update, sid)
        if p[1] in ("gb", "dy"):
            set_state(ctx, "nxsvadd", sid, p[1])
            return await show(update, f"چند {'گیگ' if p[1] == 'gb' else 'روز'} اضافه شود؟ عددش را بفرست:", [row(btn("بازگشت به سرویس", f"nsv:v:{sid}", RED, "back"))])


async def nx_message(update, ctx, uid, st):
    m = update.effective_message; name = st[0]; txt = (m.text or "").strip()
    if name == "nxcrypto":
        if not m.photo: return await m.reply_text("لطفاً اسکرین‌شات تراکنش را بفرست (TXID در کپشن).")
        amount, gift = st[1], st[2]
        bonus = amount * int(S("gift_percent")) // 100 if gift and amount >= int(S("gift_min")) else 0
        pid = ex("INSERT INTO payments(user_id,amount,bonus,photo,created) VALUES(?,?,?,?,?)", (uid, amount, bonus, m.photo[-1].file_id, int(time.time())))
        clear_state(ctx); u = get_user(uid)
        cap = (f"💎 رسید ارز دیجیتال #{pid}\nکاربر: <code>{uid}</code> ({html.escape(u['name'] or '')})\n"
               f"مبلغ: {money(amount)}{f' + هدیه {money(bonus)}' if bonus else ''} تومان\nTXID: <code>{html.escape((m.caption or '-')[:200])}</code>")
        kb = IKM([row(btn("تأیید", f"pa:{pid}", GREEN, "ok"), btn("رد", f"pr:{pid}", RED, "no"))])
        for a in ADMIN_IDS:
            try: await ctx.bot.send_photo(a, m.photo[-1].file_id, caption=cap, parse_mode=ParseMode.HTML, reply_markup=kb)
            except Exception: pass
        return await m.reply_text(render("receipt_wait"), parse_mode=ParseMode.HTML, reply_markup=IKM(back_home()))
    if not is_admin(uid): clear_state(ctx); return
    if name == "nxprof":
        t = nx_digits(txt).lstrip("@")
        u = get_user(int(t)) if t.isdigit() else q("SELECT * FROM users WHERE LOWER(username)=LOWER(?)", (t,), True)
        if not u: return await m.reply_text("کاربر پیدا نشد. آیدی عددی یا یوزرنیم درست بفرست.")
        clear_state(ctx); return await nx_profile(update, u["id"])
    if name == "nxbal":
        t = nx_digits(txt)
        if not t.isdigit() or int(t) <= 0: return await m.reply_text("فقط عدد مثبت بفرست.")
        act, tid, amt = st[1], st[2], int(t)
        ex("UPDATE users SET balance=balance" + ("+" if act == "add" else "-") + "? WHERE id=?", (amt, tid))
        added_audit(uid, "balance_" + act, tid, amt); clear_state(ctx)
        try: await ctx.bot.send_message(tid, f"{'➕' if act == 'add' else '➖'} {money(amt)} تومان {'به' if act == 'add' else 'از'} کیف پول شما {'اضافه' if act == 'add' else 'کسر'} شد.")
        except Exception: pass
        await m.reply_text(f"✅ انجام شد. موجودی جدید: {money(get_user(tid)['balance'])}")
        return await nx_profile(update, tid)
    if name == "nxmsg":
        tid = st[1]; clear_state(ctx)
        try:
            await ctx.bot.send_message(tid, "📩 <b>پیام از پشتیبانی:</b>", parse_mode=ParseMode.HTML); await m.copy(tid)
            added_audit(uid, "user_message", tid); res = "✅ پیام ارسال شد."
        except Exception as e: res = f"❌ ارسال نشد: {e}"
        return await m.reply_text(res, reply_markup=IKM([row(btn("بازگشت به پروفایل", f"nup:v:{tid}", BLUE, "back"))]))
    if name == "nxsvadd":
        t = nx_digits(txt)
        try: val = float(t)
        except Exception: val = 0
        if val <= 0: return await m.reply_text("فقط عدد مثبت بفرست.")
        if val.is_integer(): val = int(val)
        clear_state(ctx); return await nx_service_add(update, ctx, uid, st[1], st[2], val)
    if name == "ngpadd":
        parts = txt.split()
        if len(parts) < 2 or not nx_digits(parts[-1]).isdigit(): return await m.reply_text("فرمت: نام درصد\nمثال: <code>VIP 10</code>", parse_mode=ParseMode.HTML)
        g = " ".join(parts[:-1]).replace("|", "").replace(":", "")[:20]; pct = max(0, min(100, int(nx_digits(parts[-1]))))
        if g == "عادی" or g in nx_groups(): set_S("grp_pct:" + g, pct)
        else: set_S("groups", "|".join(nx_groups() + [g])); set_S("grp_pct:" + g, pct)
        added_audit(uid, "group_save", g, pct); clear_state(ctx); return await nx_groups_page(update)
    if name == "ngpset":
        t = nx_digits(txt).replace("%", "")
        if not t.isdigit() or int(t) > 100: return await m.reply_text("فقط عدد ۰ تا ۱۰۰ بفرست.")
        g = _nx_group_by_idx(st[1])
        if g: set_S("grp_pct:" + g, int(t)); added_audit(uid, "group_pct", g, t)
        clear_state(ctx); return await nx_groups_page(update)
    if name == "nxbc":
        clear_state(ctx); return await nx_broadcast(update, ctx, uid, st[1], st[2])


# ---------- پوشاندن هندلرهای اصلی (در آخر همان تابع قبلی اجرا می‌شود) ----------
_nx_orig_on_callback = on_callback
async def on_callback(update, ctx):
    cq = update.callback_query; uid = cq.from_user.id; d = cq.data or ""
    u = touch(cq.from_user)
    if u["banned"]: return await _nx_orig_on_callback(update, ctx)
    if nx_maint_block(uid): return await cq.answer(_nx_plain(render("maintenance")), show_alert=True)
    if d == "nfj:check":
        _NX_FJ_CACHE.pop(uid, None)
        if await nx_fj_ok(ctx.bot, uid):
            await cq.answer("✅ عضویت تأیید شد"); clear_state(ctx); return await send_home(update, ctx, uid)
        return await cq.answer("هنوز عضو کانال نشده‌ای.", show_alert=True)
    if not await nx_fj_ok(ctx.bot, uid):
        await cq.answer(); return await show(update, render("force_join"), nx_fj_kb())
    pre = d.split(":")[0]
    if pre in NX_PREFIXES_USER or pre in NX_PREFIXES_ADMIN:
        if pre in NX_PREFIXES_ADMIN and not is_admin(uid): return await cq.answer()
        if pre not in ("nzv", "nrc"): await cq.answer()
        try: return await nx_callback(update, ctx, uid, d)
        except Exception as e:
            log.exception("nx callback %s", d)
            try: await cq.answer("خطا: " + str(e)[:150], show_alert=True)
            except Exception: pass
            return
    return await _nx_orig_on_callback(update, ctx)


_nx_orig_on_message = on_message
async def on_message(update, ctx):
    m = update.effective_message
    if not m or not update.effective_user: return await _nx_orig_on_message(update, ctx)
    uid = update.effective_user.id
    u = touch(update.effective_user)
    if u["banned"]: return await _nx_orig_on_message(update, ctx)
    if nx_maint_block(uid): return await m.reply_text(render("maintenance"), parse_mode=ParseMode.HTML)
    st = ctx.user_data.get("state")
    if st and st[0] in (NX_STATES_ADMIN | NX_STATES_USER):
        return await nx_message(update, ctx, uid, st)
    if st and st[0] in ("addticket", "addticketreply") and (m.photo or m.document):
        return await nx_ticket_file(update, ctx, uid, st)
    return await _nx_orig_on_message(update, ctx)


_nx_orig_init_db_extra = init_db_extra
def init_db_extra():
    _nx_orig_init_db_extra()
    nx_init_db()
# ═══════════════════════════════ پایان افزودنی‌های نسخه جدید ═══════════════════════════════


# Card-to-card purchase extension: additive only.
_cardpay_orig_init_db_extra = init_db_extra
def init_db_extra():
    _cardpay_orig_init_db_extra()
    CON.executescript("""
    CREATE TABLE IF NOT EXISTS card_orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        plan_id INTEGER NOT NULL, panel_id INTEGER NOT NULL, amount INTEGER NOT NULL,
        bonus INTEGER DEFAULT 0, status TEXT DEFAULT 'pending', payment_id INTEGER,
        created INTEGER, updated INTEGER
    );
    """)
    cols = [r["name"] for r in q("PRAGMA table_info(payments)")]
    if "order_id" not in cols:
        ex("ALTER TABLE payments ADD COLUMN order_id INTEGER")
    CON.commit()

# Appearance groups for the three card-payment controls.
BTN_GROUPS.update({
    "ccp": "دکمه پرداخت کارت‌به‌کارت",
    "ccopy": "دکمه کپی شماره کارت",
    "ccpaid": "دکمه ارسال رسید کارت‌به‌کارت",
    "ccopyamt": "دکمه کپی مبلغ ریال",
})
EMOJI.update({
    "copycard": "📋",
    "copyamount": "💰",
})
for _n in BTN_GROUPS.values():
    if _n not in BTN_NAMES:
        BTN_NAMES.append(_n)

def _copy_text_btn(text, value, ek=None):
    """Native Telegram copy button. It copies locally and sends no message."""
    eid = emoji_id(ek) if ek else None
    kw = {}
    if eid:
        kw["icon_custom_emoji_id"] = eid
    label = text if eid else f"{text} {EMOJI.get(ek, '')}".strip()
    try:
        return IKB(label, copy_text={"text": str(value)}, **kw)
    except (TypeError, AttributeError):
        try:
            return IKB(label, api_kwargs={"copy_text": {"text": str(value)}, **kw})
        except TypeError:
            # Old Telegram libraries cannot expose native copy buttons.
            # Keep a harmless callback fallback rather than breaking the flow.
            return IKB(label, callback_data="copy_unavailable", **kw)

async def _cardpay_invoice(update, uid, plan_id, panel_id):
    p = q("SELECT * FROM plans WHERE id=? AND active=1", (plan_id,), True)
    pn = q("SELECT * FROM panels WHERE id=? AND active=1", (panel_id,), True)
    if not p or not pn:
        return await show(update, "این پلن/لوکیشن در دسترس نیست.", back_home())
    price, dcline, _ = dc_price(uid, p["price"])
    text = render("invoice", GB=p["gb"], DAYS=p["days"], PRICE=money(price),
                  BALANCE=money(get_user(uid)["balance"]), LOCATION=html.escape(pn["name"])) + dcline
    kb = [row(btn("پرداخت از کیف پول", f"pay:{plan_id}:{panel_id}", GREEN, "ok")),
          row(btn("پرداخت کارت‌به‌کارت", f"ccp:{plan_id}:{panel_id}", BLUE, "card")),
          row(btn("افزایش موجودی", "topup", None, "wallet")),
          row(btn("استفاده از کد تخفیف", f"dc:b:{plan_id}:{panel_id}", BLUE, "discount")),
          row(btn("بازگشت", "buy", RED, "back"))]
    return await show(update, text, kb)

async def _cardpay_start(update, ctx, uid, plan_id, panel_id):
    p = q("SELECT * FROM plans WHERE id=? AND active=1", (plan_id,), True)
    pn = q("SELECT * FROM panels WHERE id=? AND active=1", (panel_id,), True)
    if not p or not pn:
        return await show(update, "این پلن/لوکیشن در دسترس نیست.", back_home())
    price, _, _ = dc_price(uid, p["price"])
    now = int(time.time())
    oid = ex("INSERT INTO card_orders(user_id,plan_id,panel_id,amount,created,updated) VALUES(?,?,?,?,?,?)",
             (uid, plan_id, panel_id, price, now, now))
    DC_PENDING.pop(uid, None)
    text = (f"💳 <b>پرداخت کارت به کارت</b>\n\n"
            f"لطفاً مبلغ <b>{money(price)} تومان</b> را به شماره کارت زیر واریز کنید:\n\n"
            f"<code>{html.escape(S('card_number'))}</code>\n\n"
            "⏳ این تراکنش تا ۳۰ دقیقه مهلت پرداخت دارد.\n\n"
            "📸 پس از واریز، روی دکمه «پرداخت کردم» بزنید و عکس رسید را ارسال کنید.")
    kb = [row(_copy_text_btn("کپی مبلغ (ریال)", price * 10, "copyamount"),
              _copy_text_btn("کپی شماره کارت", S("card_number"), "copycard")),
          row(btn("پرداخت کردم، ارسال رسید", f"ccpaid:{oid}", GREEN, "ok")),
          row(btn("بازگشت به روش‌ها", f"inv:{plan_id}:{panel_id}", RED, "back"))]
    return await show(update, text, kb)

async def _cardpay_receipt_prompt(update, ctx, uid, oid):
    order = q("SELECT * FROM card_orders WHERE id=? AND user_id=? AND status='pending'", (oid, uid), True)
    if not order:
        return await update.callback_query.message.reply_text("این سفارش دیگر در انتظار پرداخت نیست.")
    set_state(ctx, "cardreceipt", oid)
    return await show(update, "📸 <b>لطفاً عکس رسید واریزی را ارسال کنید.</b>\n✅ رسید معمولاً طی ۵ تا ۱۵ دقیقه بررسی می‌شود.",
                      [row(btn("انصراف", f"inv:{order['plan_id']}:{order['panel_id']}", RED, "no"))])

_cardpay_orig_on_callback = on_callback
async def on_callback(update, ctx):
    d = update.callback_query.data or ""
    uid = update.effective_user.id
    if d.startswith(("pa:", "pr:")):
        if not is_admin(uid):
            return await update.callback_query.answer("دسترسی ندارید.", show_alert=True)
        pid = int(d[3:])
        pay = q("SELECT * FROM payments WHERE id=? AND status='pending'", (pid,), True)
        if pay and pay["order_id"]:
            order = q("SELECT * FROM card_orders WHERE id=? AND status='pending'", (pay["order_id"],), True)
            if not order:
                return await update.callback_query.answer("این سفارش قبلاً بررسی شده.", show_alert=True)
            if d.startswith("pr:"):
                ex("UPDATE payments SET status='rejected' WHERE id=?", (pid,))
                ex("UPDATE card_orders SET status='rejected',updated=? WHERE id=?", (int(time.time()), order["id"]))
                try: await ctx.bot.send_message(order["user_id"], "❌ رسید خرید رد شد. با پشتیبانی در ارتباط باشید.")
                except Exception: pass
                return await update.callback_query.edit_message_caption(f"❌ رد شد #{pid}")
            p = q("SELECT * FROM plans WHERE id=?", (order["plan_id"],), True)
            pn = q("SELECT * FROM panels WHERE id=? AND active=1", (order["panel_id"],), True)
            if not p or not pn:
                return await update.callback_query.answer("پلن یا پنل دیگر در دسترس نیست.", show_alert=True)
            try:
                sid, manual = await build_service(ctx, order["user_id"], pn, p["gb"], p["days"],
                                                  order["amount"], p["id"])
                ex("UPDATE payments SET status='ok' WHERE id=?", (pid,))
                ex("UPDATE card_orders SET status='ok',updated=? WHERE id=?", (int(time.time()), order["id"]))
                trx_log(order["user_id"], "card_buy", sid, p["id"], pn["id"], p["gb"], p["days"], order["amount"])
                if not manual:
                    try:
                        await deliver(ctx, order["user_id"], sid)
                    except Exception:
                        log.exception("card service delivery failed sid=%s", sid)
                        try:
                            await ctx.bot.send_message(
                                order["user_id"],
                                "✅ پرداخت تأیید و سرویس ساخته شد، اما ارسال خودکار لینک ناموفق بود. "
                                "از بخش «اشتراک‌های من» سرویس را باز کنید.")
                        except Exception:
                            pass
                else:
                    await ctx.bot.send_message(order["user_id"], "✅ پرداخت تأیید شد. کانفیگ شما به‌زودی ارسال می‌شود.")
                return await update.callback_query.edit_message_caption(f"✅ تأیید و سرویس ساخته شد #{pid}")
            except Exception as e:
                log.exception("card purchase approval failed")
                return await update.callback_query.answer("ساخت سرویس ناموفق بود؛ رسید هنوز تأیید نشده.", show_alert=True)
    if d.startswith("ccp:"):
        _, a, b = d.split(":")
        return await _cardpay_start(update, ctx, uid, int(a), int(b))
    if d.startswith("ccpaid:"):
        return await _cardpay_receipt_prompt(update, ctx, uid, int(d.split(":")[1]))
    return await _cardpay_orig_on_callback(update, ctx)

_cardpay_orig_on_message = on_message
async def on_message(update, ctx):
    st = ctx.user_data.get("state") or []
    if st and st[0] == "cardreceipt":
        uid = update.effective_user.id
        m = update.effective_message
        if not m.photo:
            return await m.reply_text("📸 لطفاً فقط عکس رسید واریزی را ارسال کنید.")
        oid = int(st[1])
        order = q("SELECT * FROM card_orders WHERE id=? AND user_id=? AND status='pending'", (oid, uid), True)
        if not order:
            clear_state(ctx)
            return await m.reply_text("این سفارش دیگر معتبر نیست.")
        pid = ex("INSERT INTO payments(user_id,amount,bonus,photo,created,order_id) VALUES(?,?,?,?,?,?)",
                 (uid, order["amount"], order["bonus"], m.photo[-1].file_id, int(time.time()), oid))
        ex("UPDATE card_orders SET payment_id=?,updated=? WHERE id=?", (pid, int(time.time()), oid))
        clear_state(ctx)
        u = get_user(uid)
        cap = (f"🧾 <b>رسید خرید مستقیم #{pid}</b>\nکاربر: <code>{uid}</code> ({html.escape(u['name'] or '')})\n"
               f"مبلغ: <b>{money(order['amount'])} تومان</b>\nپلن: <code>#{order['plan_id']}</code> | پنل: <code>#{order['panel_id']}</code>")
        kb = IKM([row(btn("تأیید", f"pa:{pid}", GREEN, "ok"), btn("رد", f"pr:{pid}", RED, "no"))])
        for a in ADMIN_IDS:
            try:
                await ctx.bot.send_photo(a, m.photo[-1].file_id, caption=cap,
                                         parse_mode=ParseMode.HTML, reply_markup=kb)
            except Exception:
                pass
        return await m.reply_text("✅ رسید شما ثبت شد.\n⏱ تأیید رسید معمولاً طی ۵ تا ۱۵ دقیقه بررسی می‌شود.",
                                  reply_markup=IKM(back_home()))
    return await _cardpay_orig_on_message(update, ctx)

_cardpay_orig_page_invoice = page_invoice
async def page_invoice(update, uid, plan_id, panel_id):
    return await _cardpay_invoice(update, uid, plan_id, panel_id)

# Subscription-link rotation extension. Existing service actions remain unchanged.
BTN_GROUPS.update({"sublink": "دکمه تغییر لینک ساب"})
EMOJI.update({"sublink": "🔗"})
if "دکمه تغییر لینک ساب" not in BTN_NAMES:
    BTN_NAMES.append("دکمه تغییر لینک ساب")

async def _rotate_subscription_link(update, ctx, uid, sid):
    s = q("SELECT * FROM services WHERE id=? AND user_id=? AND status!='deleted'", (sid, uid), True)
    if not s:
        return await show(update, "سرویس پیدا نشد.", back_home())
    p = q("SELECT * FROM panels WHERE id=?", (s["panel_id"],), True)
    if not p or p["ptype"] == "manual":
        return await show(update, "برای این نوع سرویس تغییر خودکار لینک ساب از پنل پشتیبانی نمی‌شود.",
                          [row(btn("بازگشت به سرویس", f"sv:{sid}", RED, "back"))])
    try:
        async with _http(p) as c:
            if p["ptype"] in XUI_PREFIX:
                await _xlogin(c, p)
                inb, inbound, client = await _xui_find(c, p["ptype"], p, s["username"])
                if not client:
                    raise Exception("کلاینت روی پنل پیدا نشد")
                new_sid = secrets.token_hex(8)
                client["subId"] = new_sid
                r = await c.post(f"{XUI_PREFIX[p['ptype']].rstrip('/')}/updateClient/{_xui_cid(inbound, client)}",
                                 data={"id": inb, "settings": json.dumps({"clients": [client]})})
                j = r.json()
                if not j.get("success"):
                    raise Exception(j.get("msg") or "updateClient failed")
                parts = (p["extra"] or "").split("|")
                if len(parts) > 1 and parts[1].strip():
                    new_sub = parts[1].strip().rstrip("/") + "/" + new_sid
                else:
                    new_sub = await _xui_sub(c, p["ptype"], p, new_sid)
                if not new_sub:
                    raise Exception("لینک ساب در تنظیمات پنل فعال نیست")
            else:
                return await show(update,
                    "این پنل لینک ساب را با شناسه داخلی خودش می‌سازد و تغییر امن آن از API ممکن نیست؛ "
                    "برای حفظ سرویس، چیزی حذف یا بازسازی نشد.",
                    [row(btn("بازگشت به سرویس", f"sv:{sid}", RED, "back"))])
        links = await _sub_links(new_sub) if new_sub.startswith("http") else []
        ex("UPDATE services SET sub=?, link=? WHERE id=?", (new_sub, links[0] if links else new_sub, sid))
        text = (f"✅ <b>لینک ساب تغییر کرد.</b>\n\n"
                f"لینک قبلی دیگر روی پنل معتبر نیست.\n"
                f"🔗 لینک جدید:\n<code>{html.escape(new_sub)}</code>")
        return await show(update, text, [row(btn("بازگشت به سرویس", f"sv:{sid}", BLUE, "back"))] + back_home())
    except Exception as e:
        log.exception("rotate subscription link")
        return await show(update, f"❌ تغییر لینک ساب انجام نشد:\n<code>{html.escape(str(e))[:400]}</code>",
                          [row(btn("تلاش دوباره", f"sublink:{sid}", BLUE, "sublink")),
                           row(btn("بازگشت به سرویس", f"sv:{sid}", RED, "back"))])

_sublink_orig_page_service = page_service
async def page_service(update, uid, sid):
    s = q("SELECT * FROM services WHERE id=? AND user_id=? AND status!='deleted'", (sid, uid), True)
    if not s:
        return await _sublink_orig_page_service(update, uid, sid)
    # Insert the new control before the existing service controls, preserving their order.
    p = q("SELECT * FROM panels WHERE id=?", (s["panel_id"],), True)
    extra = ""
    if p and p["ptype"] != "manual" and s["status"] == "active":
        try:
            i = await panel_info(p, s["username"])
            if i:
                extra = (f"\nوضعیت: <b>{i['status']}</b>\nمصرف: <b>{i['used']:.2f}</b> از "
                         f"<b>{i['total']:.0f}</b> گیگ\nانقضا: {i['expire']}")
        except Exception:
            extra = "\n(دریافت وضعیت از پنل ممکن نشد)"
    link = s["sub"] or s["link"] or "هنوز ارسال نشده"
    text = (f"{E('plan')} <b>{svc_name(s)}</b>\n<blockquote>📍 لوکیشن: {html.escape(p['name'] if p else '-')}\n"
            f"{E('volume')} حجم: {s['gb']} گیگ\n{E('time')} انقضا: {jdate(s['expire'])}{extra}</blockquote>\n\n"
            f"{E('link')} لینک:\n<code>{html.escape(link)}</code>")
    kb = [row(btn("تغییر لینک ساب", f"sublink:{sid}", BLUE, "sublink"))]
    kb += [row(btn("دریافت QR", f"qr:{sid}", BLUE, "qr"), btn("بروزرسانی وضعیت", f"sv:{sid}", None, "search")),
           row(btn("QR کانفیگ", f"qrc:{sid}", BLUE, "qr")) if s["link"] and s["sub"] and s["link"] != s["sub"] else [],
           row(btn("تمدید پلن", f"rn:{sid}", GREEN, "renew")) if s["status"] != "pending" else [],
           row(btn("تغییر نام سرویس", f"sren:{sid}", BLUE, "rename"), btn("حذف سرویس", f"sdel:{sid}", RED, "delsrv")),
           row(btn("بازگشت", "subs", RED, "back"))]
    return await show(update, text, [r for r in kb if r])

_sublink_orig_on_callback = on_callback
async def on_callback(update, ctx):
    d = update.callback_query.data or ""
    if d.startswith("sublink:"):
        uid = update.effective_user.id
        return await _rotate_subscription_link(update, ctx, uid, int(d.split(":")[1]))
    return await _sublink_orig_on_callback(update, ctx)

if __name__ == "__main__":
    main()
