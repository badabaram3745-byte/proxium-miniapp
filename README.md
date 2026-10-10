# Telegram Mini App + VPN Bot

اسکلت آماده برای اجرای ربات و Mini App روی یک سرویس Railway. فایل `bot.py` همان کد پنل فعلی است؛ `miniapp/` رابط مینی‌اپ و API احراز هویت Telegram Web App را دارد.

## اجرای محلی

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# متغیرهای .env را تنظیم کن
python run.py
```

آدرس تست: `http://localhost:8080` و سلامت سرویس: `/health`.

## انتشار رایگان روی Railway

1. این پوشه را در GitHub به‌عنوان یک repository جدید آپلود کن.
2. در Railway گزینه **Deploy from GitHub Repo** را بزن.
3. متغیرهای `BOT_TOKEN`, `ADMIN_IDS`, `DB_PATH` و تنظیمات پنل‌ها را در Variables وارد کن.
4. برای سرویس یک دامنه عمومی بساز و آدرس `https://.../` را به‌عنوان URL مینی‌اپ استفاده کن.
5. چون SQLite روی دیسک موقت است، برای دیتای واقعی Railway Volume وصل کن و `DB_PATH=/data/bot.db` بگذار.

## اتصال دکمه مینی‌اپ به ربات

در BotFather یک Web App با URL دامنه Railway بساز. سپس در دکمه منوی ربات، از `WebAppInfo(url=WEBAPP_URL)` استفاده کن. این اسکلت API هدر `X-Telegram-Init-Data` را با توکن ربات اعتبارسنجی می‌کند و توکن را داخل فرانت‌اند ذخیره نمی‌کند.

## نکته مهم

این نسخه زیرساخت و اتصال امن اولیه را آماده می‌کند؛ صفحه‌های خرید، اشتراک و کیف پول باید به APIهای دیتابیس/پنل موجود متصل شوند. توکن‌ها را هیچ‌وقت داخل GitHub commit نکن.
