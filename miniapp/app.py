# NAYI Mini App backend · v4
# همه‌ی endpointهای قبلی (/ , /health , /api/catalog , /api/profile , /api/buy) حفظ شده‌اند؛ فقط امکانات اضافه شده.
import asyncio, base64, hashlib, hmac, io, json, logging, os, time, urllib.request
from pathlib import Path
from urllib.parse import parse_qsl
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).parent
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "").lstrip("@")          # اختیاری؛ اگر خالی باشد از getMe خوانده می‌شود
SUPPORT = os.getenv("SUPPORT_USERNAME", "").strip()                # مثلا nayi_support یا لینک کامل
TEST_GB = float(os.getenv("TEST_GB", "0") or 0)                    # برای فعال‌سازی اکانت تست: TEST_GB=1
TEST_DAYS = int(os.getenv("TEST_DAYS", "0") or 0)                  # و TEST_DAYS=1
log = logging.getLogger("nayi-miniapp")

# اسم توابع احتمالی ربات؛ اگر در bot.py وجود داشته باشند، امکانش در مینی‌اپ فعال می‌شود
RENEW_FN = ("panel_renew", "panel_extend", "panel_update_user")      # (panel, username, gb, days)
USAGE_FN = ("panel_usage", "panel_get_user", "panel_user_info")      # (panel, username) -> dict
DELETE_FN = ("panel_delete", "panel_remove", "panel_delete_user")    # (panel, username)
DISCOUNT_FN = ("dc_apply", "dc_set", "apply_discount")               # (uid, code)

app = FastAPI(title="NAYI Mini App")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

class BuyRequest(BaseModel):
    plan_id: int
    panel_id: int | None = None

class RenewRequest(BaseModel):
    service_id: int
    plan_id: int

class TestRequest(BaseModel):
    panel_id: int | None = None

class DiscountRequest(BaseModel):
    code: str

def user_from_init(init_data: str):
    if not BOT_TOKEN or not init_data: raise HTTPException(401, "Telegram init data is required")
    pairs = dict(parse_qsl(init_data, keep_blank_values=True)); received = pairs.pop("hash", "")
    try: auth_date = int(pairs.get("auth_date", "0"))
    except ValueError: raise HTTPException(401, "Invalid Telegram init data")
    if not received or time.time() - auth_date > 86400: raise HTTPException(401, "Invalid or expired init data")
    check = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(hmac.new(secret, check.encode(), hashlib.sha256).hexdigest(), received): raise HTTPException(401, "Invalid Telegram signature")
    return json.loads(pairs.get("user", "{}"))

def auth(x_telegram_init_data: str | None):
    u = user_from_init(x_telegram_init_data or "")
    if not u.get("id"): raise HTTPException(401, "Telegram user missing")
    return u

def bot_module():
    import sys
    if "bot" not in sys.modules: import bot
    return sys.modules["bot"]

def qr_data(value: str):
    try:
        import qrcode
        img = qrcode.make(value); buf = io.BytesIO(); img.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception: return ""

# ---------- helpers (جدید) ----------
_locks: dict[int, asyncio.Lock] = {}
def user_lock(uid: int) -> asyncio.Lock:
    """جلوی دو خرید هم‌زمان یک کاربر را می‌گیرد."""
    return _locks.setdefault(uid, asyncio.Lock())

def find_fn(b, names):
    for n in names:
        f = getattr(b, n, None)
        if callable(f): return f
    return None

async def call(fn, *args):
    res = fn(*args)
    if asyncio.iscoroutine(res): res = await res
    return res

def col(row, key, default=None):
    try: return row[key] if key in row.keys() else default
    except Exception:
        try: return row[key]
        except Exception: return default

def charge(b, uid: int, price: int):
    """کسر موجودی با بررسی اینکه واقعا کم شد."""
    dbu = b.get_user(uid); before = int(dbu["balance"] or 0)
    if before < price: raise HTTPException(402, f"موجودی کافی نیست. موجودی: {b.money(dbu['balance'])}")
    b.ex("UPDATE users SET balance=balance-? WHERE id=? AND balance>=?", (price, uid, price))
    if int(b.get_user(uid)["balance"] or 0) > before - price:
        raise HTTPException(402, "موجودی کافی نیست؛ دوباره تلاش کن")

def refund(b, uid: int, price: int):
    if price: b.ex("UPDATE users SET balance=balance+? WHERE id=?", (price, uid))

async def cleanup_panel(b, pn, uname):
    fn = find_fn(b, DELETE_FN)
    if not fn: log.error("orphan panel user %s on panel %s (no delete fn)", uname, col(pn, "id")); return
    try: await call(fn, pn, uname)
    except Exception: log.exception("could not delete orphan panel user %s", uname)

def panel_names(b):
    try: return {p["id"]: p["name"] for p in b.q("SELECT id,name FROM panels")}
    except Exception: return {}

def features(b):
    return {"renew": bool(find_fn(b, RENEW_FN)), "usage": bool(find_fn(b, USAGE_FN)), "discount": bool(find_fn(b, DISCOUNT_FN)),
            "test": TEST_GB > 0 and TEST_DAYS > 0, "test_gb": TEST_GB, "test_days": TEST_DAYS}

_bot_name = {"v": BOT_USERNAME}
def bot_username():
    if not _bot_name["v"] and BOT_TOKEN:
        try:
            with urllib.request.urlopen(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe", timeout=5) as r:
                _bot_name["v"] = json.loads(r.read())["result"]["username"]
        except Exception: pass
    return _bot_name["v"]

def pick_panel(b, panel_id):
    pn = b.q("SELECT * FROM panels WHERE id=? AND active=1", (panel_id,), True) if panel_id else b.q("SELECT * FROM panels WHERE active=1 AND ptype!='manual' ORDER BY id LIMIT 1", one=True)
    if not pn or pn["ptype"] == "manual": raise HTTPException(409, "پنل متصل نیست؛ خرید انجام نشد")
    return pn

def user_services(b, uid, with_qr=True):
    rows = b.q("SELECT * FROM services WHERE user_id=? AND status NOT IN ('deleted') ORDER BY id DESC", (uid,))
    names = panel_names(b)
    return [{"id": r["id"], "name": r["username"], "gb": r["gb"], "days": r["days"], "expire": r["expire"], "status": r["status"], "link": r["link"] or "", "sub": r["sub"] or "",
             "qr": qr_data(r["link"] or r["sub"] or "") if with_qr else "",
             "panel_id": col(r, "panel_id"), "panel": names.get(col(r, "panel_id"), ""), "is_test": int(col(r, "is_test", 0) or 0), "created": col(r, "created"), "price": col(r, "price", 0)} for r in rows]

@app.get("/")
def index(): return FileResponse(ROOT / "static" / "index.html", headers={"Cache-Control": "no-cache"})
@app.get("/health")
def health(): return {"ok": True, "service": "nayi-mini-app"}

@app.get("/api/config")
def config(x_telegram_init_data: str | None = Header(default=None)):
    auth(x_telegram_init_data); b = bot_module()
    return {"ok": True, "bot": bot_username(), "support": SUPPORT, "features": features(b)}

@app.get("/api/catalog")
def catalog(x_telegram_init_data: str | None = Header(default=None)):
    u = auth(x_telegram_init_data); b = bot_module(); uid = int(u["id"]); dbu = b.get_user(uid)
    plans = b.q("SELECT * FROM plans WHERE active=1 ORDER BY months, gb, days")
    panels = b.q("SELECT id,name,ptype FROM panels WHERE active=1 ORDER BY id")
    out = []
    for p in plans:
        price, _, _ = b.dc_price(uid, p["price"])
        out.append({"id": p["id"], "months": p["months"], "gb": p["gb"], "days": p["days"], "price": price, "orig": p["price"]})
    svcs = user_services(b, uid, with_qr=False)   # QR جدا و فقط هنگام نیاز ساخته می‌شود (سرعت)
    return {"ok": True, "balance": int(dbu["balance"] or 0), "plans": out, "panels": [dict(x) for x in panels], "services": svcs,
            "features": features(b), "has_test": any(s["is_test"] for s in svcs), "bot": bot_username(), "support": SUPPORT}

@app.get("/api/profile")
def profile(x_telegram_init_data: str | None = Header(default=None)):
    u = auth(x_telegram_init_data); b = bot_module(); dbu = b.get_user(int(u["id"]))
    svcs = user_services(b, int(u["id"]), with_qr=False)
    return {"ok": True, "id": u["id"], "name": dbu["name"] or u.get("first_name", ""), "username": dbu["username"] or u.get("username", ""), "phone": dbu["phone"] or "",
            "balance": int(dbu["balance"] or 0), "services": len(svcs), "active": sum(1 for s in svcs if s["status"] == "active"),
            "spent": sum(int(s["price"] or 0) for s in svcs if not s["is_test"]), "photo": u.get("photo_url", "")}

@app.get("/api/service/{sid}")
async def service_detail(sid: int, x_telegram_init_data: str | None = Header(default=None)):
    u = auth(x_telegram_init_data); b = bot_module(); uid = int(u["id"])
    r = b.q("SELECT * FROM services WHERE id=? AND user_id=?", (sid, uid), True)
    if not r: raise HTTPException(404, "سرویس پیدا نشد")
    out = {"ok": True, "id": sid, "qr": qr_data(r["link"] or r["sub"] or ""), "usage": None}
    fn = find_fn(b, USAGE_FN)
    if fn and col(r, "panel_id"):
        try:
            pn = b.q("SELECT * FROM panels WHERE id=?", (r["panel_id"],), True)
            res = await call(fn, pn, r["username"])
            if isinstance(res, dict):
                out["usage"] = {"used": res.get("used") or res.get("used_traffic") or 0, "total": res.get("total") or res.get("data_limit") or 0,
                                "expire": res.get("expire"), "online": res.get("online") or res.get("online_at")}
        except Exception: log.exception("usage fetch failed")
    return out

@app.post("/api/buy")
async def buy(req: BuyRequest, x_telegram_init_data: str | None = Header(default=None)):
    u = auth(x_telegram_init_data); b = bot_module(); uid = int(u["id"])
    async with user_lock(uid):
        p = b.q("SELECT * FROM plans WHERE id=? AND active=1", (req.plan_id,), True)
        if not p: raise HTTPException(404, "Plan not found")
        pn = pick_panel(b, req.panel_id)
        price, _, code = b.dc_price(uid, p["price"])
        charge(b, uid, price)
        uname = f"{b.USER_PREFIX}{uid}_{b.secrets.token_hex(2)}"
        try:
            res = await b.panel_create(pn, uname, p["gb"], p["days"])
        except Exception:
            refund(b, uid, price); log.exception("panel_create failed")
            raise HTTPException(502, "ساخت سرویس ناموفق بود؛ مبلغ به کیف پول برگشت")
        now = int(time.time())
        try:
            sid = b.ex("INSERT INTO services(user_id,plan_id,panel_id,username,link,sub,gb,days,price,created,expire,is_test,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,0,'active')", (uid,p["id"],pn["id"],uname,res["link"],res["sub"],p["gb"],p["days"],price,now,now+p["days"]*86400))
        except Exception:
            # اکانت روی پنل ساخته شده ولی ثبت نشد -> پاکش کن تا اکانت مجانی نماند
            await cleanup_panel(b, pn, uname); refund(b, uid, price); log.exception("service insert failed")
            raise HTTPException(502, "ثبت سرویس ناموفق بود؛ مبلغ به کیف پول برگشت")
        try: b.dc_use(uid, code); b.trx_log(uid,"buy",sid,p["id"],pn["id"],p["gb"],p["days"],price,p["price"]-price,code)
        except Exception: log.exception("trx log failed")   # سرویس سالم است؛ پول برنمی‌گردد
        return {"ok": True, "service": {"id": sid, "name": uname, "gb": p["gb"], "days": p["days"], "price": price, "link": res["link"], "sub": res["sub"], "qr": qr_data(res["link"] or res["sub"] or ""),
                "expire": now+p["days"]*86400, "status": "active", "panel_id": pn["id"], "panel": pn["name"], "is_test": 0, "created": now}, "balance": int(b.get_user(uid)["balance"])}

@app.post("/api/test")
async def free_test(req: TestRequest, x_telegram_init_data: str | None = Header(default=None)):
    if not (TEST_GB > 0 and TEST_DAYS > 0): raise HTTPException(404, "اکانت تست فعال نیست")
    u = auth(x_telegram_init_data); b = bot_module(); uid = int(u["id"])
    async with user_lock(uid):
        if b.q("SELECT id FROM services WHERE user_id=? AND is_test=1 LIMIT 1", (uid,), True): raise HTTPException(409, "قبلاً اکانت تست گرفتی")
        pn = pick_panel(b, req.panel_id); uname = f"{b.USER_PREFIX}{uid}_t{b.secrets.token_hex(2)}"
        try: res = await b.panel_create(pn, uname, TEST_GB, TEST_DAYS)
        except Exception: log.exception("test create failed"); raise HTTPException(502, "ساخت اکانت تست ناموفق بود")
        now = int(time.time())
        try:
            sid = b.ex("INSERT INTO services(user_id,plan_id,panel_id,username,link,sub,gb,days,price,created,expire,is_test,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,1,'active')", (uid,0,pn["id"],uname,res["link"],res["sub"],TEST_GB,TEST_DAYS,0,now,now+TEST_DAYS*86400))
        except Exception:
            await cleanup_panel(b, pn, uname); raise HTTPException(502, "ثبت اکانت تست ناموفق بود")
        return {"ok": True, "service": {"id": sid, "name": uname, "gb": TEST_GB, "days": TEST_DAYS, "price": 0, "link": res["link"], "sub": res["sub"], "qr": "",
                "expire": now+TEST_DAYS*86400, "status": "active", "panel_id": pn["id"], "panel": pn["name"], "is_test": 1, "created": now}}

@app.post("/api/renew")
async def renew(req: RenewRequest, x_telegram_init_data: str | None = Header(default=None)):
    u = auth(x_telegram_init_data); b = bot_module(); uid = int(u["id"])
    fn = find_fn(b, RENEW_FN)
    if not fn: raise HTTPException(501, "تمدید از مینی‌اپ فعال نیست؛ از ربات تمدید کن")
    async with user_lock(uid):
        s = b.q("SELECT * FROM services WHERE id=? AND user_id=?", (req.service_id, uid), True)
        if not s: raise HTTPException(404, "سرویس پیدا نشد")
        p = b.q("SELECT * FROM plans WHERE id=? AND active=1", (req.plan_id,), True)
        if not p: raise HTTPException(404, "Plan not found")
        pn = b.q("SELECT * FROM panels WHERE id=?", (col(s, "panel_id"),), True)
        if not pn or pn["ptype"] == "manual": raise HTTPException(409, "پنل این سرویس متصل نیست")
        price, _, code = b.dc_price(uid, p["price"]); charge(b, uid, price)
        try: await call(fn, pn, s["username"], p["gb"], p["days"])
        except Exception:
            refund(b, uid, price); log.exception("renew failed"); raise HTTPException(502, "تمدید ناموفق بود؛ مبلغ برگشت خورد")
        now = int(time.time()); expire = max(now, int(s["expire"] or now)) + p["days"] * 86400
        b.ex("UPDATE services SET gb=?, days=?, expire=?, status='active' WHERE id=?", (p["gb"], p["days"], expire, s["id"]))
        try: b.dc_use(uid, code); b.trx_log(uid,"renew",s["id"],p["id"],pn["id"],p["gb"],p["days"],price,p["price"]-price,code)
        except Exception: log.exception("trx log failed")
        return {"ok": True, "expire": expire, "balance": int(b.get_user(uid)["balance"])}

@app.post("/api/discount")
async def discount(req: DiscountRequest, x_telegram_init_data: str | None = Header(default=None)):
    u = auth(x_telegram_init_data); b = bot_module(); uid = int(u["id"])
    fn = find_fn(b, DISCOUNT_FN)
    if not fn: raise HTTPException(501, "ثبت کد تخفیف از مینی‌اپ فعال نیست")
    code = (req.code or "").strip()[:40]
    if not code: raise HTTPException(400, "کد را وارد کن")
    try: ok = await call(fn, uid, code)
    except Exception: raise HTTPException(400, "کد تخفیف نامعتبر است")
    if ok is False: raise HTTPException(400, "کد تخفیف نامعتبر است")
    return {"ok": True}
