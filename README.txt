NAYI Mini App · v4.2 tested package

ساختار اجرا:
- bot.py در ریشه است.
- miniapp/app.py و miniapp/static/* رابط مینی‌اپ هستند.
- bot.py و ظاهر/رنگ‌بندی/گرافیک مینی‌اپ حفظ شده‌اند.

اصلاحات این نسخه:
- اتصال تخفیف به discounts واقعی bot.py با dc_check / dc_price / dc_use؛ مبلغ نهایی دوباره در سرور محاسبه می‌شود.
- اکانت تست به تنظیمات واقعی ربات وصل شد: test_enabled، test_used، test_gb، test_days و test_panel.
- test_used بعد از ثبت موفق قفل می‌شود و پنل اکانت تست از انتخاب کاربر یا test_panel واقعی می‌آید.
- panel_info واقعی ربات به گزارش مصرف وصل شد.
- panel_renew و panel_delete واقعی ربات شناسایی شدند.
- انتخاب چند پنل فقط از پنل‌های active و غیر manual می‌آید و panel_id انتخابی در خرید ارسال می‌شود.
- نسخه تکراری قدیمی داخل ZIP حذف شد.
- qrcode[pil] در requirements اضافه است.
- خرید، تخفیف، تست و تمدید با قفل کاربر و برگشت وجه در خطا محافظت شده‌اند.

نصب:
pip install -r requirements.txt
سپس طبق run.py پروژه اجرا و Railway redeploy شود.

تست انجام‌شده:
- py_compile برای Python موفق.
- node --check برای JavaScript موفق.
- بررسی اتصال نام توابع واقعی bot.py انجام شد.
- تست زنده پنل/Telegram قابل اجرا نبود چون این محیط FastAPI و credential/network پروژه را ندارد؛ بعد از deploy باید با یک کاربر تستی، کد تخفیف واقعی، تست رایگان، انتخاب دو پنل و یک خرید کم‌مبلغ بررسی شود.
