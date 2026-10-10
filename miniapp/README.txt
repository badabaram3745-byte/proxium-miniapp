NAYI Mini App · نسخه ۴.۱

این بسته فقط یک نسخه دارد: miniapp/. فایل قدیمی و پوشه تکراری داخل بسته نیست.
جایگزینی:
1) miniapp/app.py
2) miniapp/static/index.html
3) miniapp/static/style.css
4) miniapp/static/app.js
requirements.txt را هم به ریشه پروژه اضافه کن. bot.py و run.py حذف یا جایگزین نمی‌شوند.

اتصال واقعی:
- خرید، کسر موجودی، انتخاب پنل فعال، ثبت سرویس و برگشت وجه در خطا از bot.py استفاده می‌کند.
- کد تخفیف قبل از پرداخت روی خود ربات اعتبارسنجی می‌شود و موقع خرید دوباره مبلغ از سمت سرور محاسبه می‌شود. قیمت مرورگر قابل اعتماد نیست.
- اکانت تست به صورت پیش‌فرض ۱ گیگ / ۱ روز فعال است. برای تغییر: TEST_GB و TEST_DAYS در Railway.
- چند پنل فعال با ptype غیر manual در کاتالوگ می‌آیند و panel_id انتخاب‌شده به خرید ارسال می‌شود.
- QR با qrcode ساخته می‌شود. اگر پنل یا سرویس خراب شود، مبلغ برمی‌گردد و تلاش می‌شود کاربر یتیم از پنل پاک شود.

نکته مهم تخفیف:
برای اعتبارسنجی دقیق، bot.py باید یکی از این توابع را داشته باشد: dc_apply یا dc_set یا apply_discount با ورودی (user_id, code) و خروجی یکی از این‌ها: {price/final_price}, {percent}, {amount}, True/False. اگر تابع موجود نباشد، مینی‌اپ کد جعلی را قبول نمی‌کند.

برای تمدید، مصرف و حذف اکانت یتیم، نام‌های پشتیبانی‌شده:
panel_renew/panel_extend/panel_update_user
panel_usage/panel_get_user/panel_user_info
panel_delete/panel_remove/panel_delete_user
