# NAYI Mini App · v5 user extras (additive only; nothing from v4 is removed).
# In-app card top-up with receipt, support tickets, rename / transfer service, referral, IP info.
import asyncio, base64, html, json, logging, re, time, urllib.request
from fastapi import APIRouter, Header, HTTPException, Request, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from miniapp import tgapi

log = logging.getLogger("nayi-extras")
router = APIRouter()

MIN_TOPUP, MAX_TOPUP = 10000, 500_000_000
MAX_IMG = 6 * 1024 * 1024
FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _core():
    import importlib
    return importlib.import_module("miniapp.app")   # late import: avoids circular import at startup


def ctx(x_telegram_init_data):
    core = _core(); u = core.auth(x_telegram_init_data); b = core.bot_module(); uid = int(u["id"])
    dbu = b.get_user(uid)
    if not dbu: raise HTTPException(404, "اول یک بار ربات را استارت کن")
    if int(dbu["banned"] or 0): raise HTTPException(403, "حساب شما مسدود است")
    return core, b, uid, dbu


def S(b, k, default=""):
    try:
        v = b.S(k); return default if v in (None, "") else v
    except Exception: return default


def audit(b, actor, action, target="", details=""):
    fn = getattr(b, "added_audit", None)
    if fn:
        try: fn(actor, action, target, details)
        except Exception: pass


def ensure_tables(b):
    """Same schema the bot creates; harmless if it already exists."""
    try:
        b.CON.executescript("""
        CREATE TABLE IF NOT EXISTS support_tickets(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            subject TEXT DEFAULT '', status TEXT DEFAULT 'open', created INTEGER, updated INTEGER, admin_id INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS support_messages(id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id INTEGER NOT NULL,
            sender_id INTEGER NOT NULL, body TEXT, created INTEGER);
        """); b.CON.commit()
    except Exception: log.exception("ensure tables")


def ticket_kb(b, tid, admin):
    fn = getattr(b, "added_ticket_kb", None)
    if not fn: return None
    try: return fn(tid, admin)
    except Exception: return None


def int_or_400(v, msg):
    t = str(v or "").translate(FA_DIGITS).replace(",", "").strip()
    if not t.isdigit(): raise HTTPException(400, msg)
    return int(t)


# ---------- models ----------
class TopupReq(BaseModel):
    amount: int | str
    gift: bool = False
    image: str            # data URL or base64 (jpeg/png/webp)

class TicketReq(BaseModel):
    body: str

class RenameReq(BaseModel):
    title: str

class TransferReq(BaseModel):
    to: int | str


# ---------- features ----------
@router.get("/api/x/features")
def x_features(x_telegram_init_data: str | None = Header(default=None)):
    core, b, uid, dbu = ctx(x_telegram_init_data)
    return {"ok": True, "card_topup": bool(S(b, "card_number")), "tickets": True, "rename": True, "transfer": True,
            "referral": True, "ip": True, "zarinpal": S(b, "zp_on") == "1" and bool(S(b, "zp_merchant")),
            "crypto": S(b, "cr_on") == "1" and bool(S(b, "cr_wallet"))}


# ---------- in-app card top-up ----------
@router.get("/api/x/topup")
def topup_info(x_telegram_init_data: str | None = Header(default=None)):
    core, b, uid, dbu = ctx(x_telegram_init_data)
    pays = b.q("SELECT id,amount,bonus,status,created FROM payments WHERE user_id=? ORDER BY id DESC LIMIT 15", (uid,))
    return {"ok": True, "card": S(b, "card_number"), "owner": S(b, "card_owner"), "min": MIN_TOPUP,
            "gift_min": int(float(S(b, "gift_min", "0") or 0)), "gift_percent": int(float(S(b, "gift_percent", "0") or 0)),
            "balance": int(dbu["balance"] or 0), "payments": [dict(p) for p in pays]}


def _decode_image(raw: str):
    m = re.match(r"^data:(image/(?:jpeg|jpg|png|webp));base64,(.+)$", raw or "", re.S)
    mime, data = (m.group(1), m.group(2)) if m else ("image/jpeg", raw or "")
    try: content = base64.b64decode(data, validate=False)
    except Exception: raise HTTPException(400, "تصویر رسید خراب است")
    if not content or len(content) < 200: raise HTTPException(400, "تصویر رسید را انتخاب کن")
    if len(content) > MAX_IMG: raise HTTPException(413, "حجم عکس رسید زیاد است (حداکثر ۶ مگ)")
    head = content[:12]
    if head.startswith(b"\x89PNG"): mime = "image/png"
    elif head.startswith(b"\xff\xd8"): mime = "image/jpeg"
    elif head[:4] == b"RIFF" and head[8:12] == b"WEBP": mime = "image/webp"
    else: raise HTTPException(400, "فقط عکس JPG / PNG / WEBP قبول است")
    if mime == "image/jpg": mime = "image/jpeg"
    return content, mime


@router.post("/api/x/topup")
async def topup_send(req: TopupReq, x_telegram_init_data: str | None = Header(default=None)):
    core, b, uid, dbu = ctx(x_telegram_init_data)
    amount = int_or_400(req.amount, "مبلغ را فقط عدد وارد کن")
    if amount < MIN_TOPUP: raise HTTPException(400, "حداقل مبلغ شارژ ۱۰,۰۰۰ تومان است")
    if amount > MAX_TOPUP: raise HTTPException(400, "مبلغ بیش از حد مجاز است")
    if not S(b, "card_number"): raise HTTPException(409, "پرداخت کارت‌به‌کارت فعلاً فعال نیست")
    content, mime = _decode_image(req.image)
    async with core.user_lock(uid):
        pend = b.q("SELECT COUNT(*) c FROM payments WHERE user_id=? AND status='pending'", (uid,), True)["c"]
        if pend >= 3: raise HTTPException(429, "۳ رسید در انتظار بررسی داری؛ صبر کن تا بررسی شوند")
        gift_min = int(float(S(b, "gift_min", "0") or 0)); gift_pct = int(float(S(b, "gift_percent", "0") or 0))
        bonus = amount * gift_pct // 100 if req.gift and amount >= gift_min else 0
        pid = b.ex("INSERT INTO payments(user_id,amount,bonus,photo,created) VALUES(?,?,?,?,?)", (uid, amount, bonus, "", int(time.time())))
        name = html.escape(dbu["name"] or "")
        cap = (f"🧾 رسید #{pid} (مینی‌اپ)\nکاربر: <code>{uid}</code> ({name})\n"
               f"مبلغ: {b.money(amount)}{f' + هدیه {b.money(bonus)}' if bonus else ''} تومان")
        kb = {"inline_keyboard": [[{"text": "تأیید", "callback_data": f"pa:{pid}"}, {"text": "رد", "callback_data": f"pr:{pid}"}]]}
        file_id, delivered = "", 0
        for a in list(b.ADMIN_IDS):
            try:
                if file_id:
                    await asyncio.to_thread(tgapi.call, "sendPhoto", {"chat_id": a, "photo": file_id, "caption": cap, "parse_mode": "HTML", "reply_markup": kb})
                else:
                    msg = await asyncio.to_thread(tgapi.send_photo_bytes, a, content, "receipt" + (".png" if mime == "image/png" else ".jpg"), mime, cap, kb, "HTML")
                    file_id = (msg.get("photo") or [{}])[-1].get("file_id", "")
                delivered += 1
            except Exception as e: log.warning("receipt to admin %s: %s", a, e)
        if not delivered:
            b.ex("UPDATE payments SET status='error' WHERE id=?", (pid,))
            raise HTTPException(502, "ارسال رسید برای ادمین ناموفق بود؛ دوباره تلاش کن یا از ربات بفرست")
        b.ex("UPDATE payments SET photo=? WHERE id=?", (file_id or "miniapp", pid))
        audit(b, uid, "miniapp_topup", pid, amount)
        try: await asyncio.to_thread(tgapi.safe_send, uid, "✅ رسید شما از مینی‌اپ دریافت شد و پس از بررسی ادمین، موجودی شارژ می‌شود.")
        except Exception: pass
        return {"ok": True, "id": pid, "amount": amount, "bonus": bonus, "status": "pending"}


# ---------- support tickets ----------
def _ticket(b, tid, uid):
    t = b.q("SELECT * FROM support_tickets WHERE id=? AND user_id=?", (tid, uid), True)
    if not t: raise HTTPException(404, "تیکت پیدا نشد")
    return t


def _notify_admins_ticket(b, tid, uid, body, new):
    head = "🎫 تیکت جدید" if new else "🎫 پیام جدید در تیکت"
    for a in list(b.ADMIN_IDS):
        tgapi.safe_send(a, f"{head} #{tid} از کاربر <code>{uid}</code> (مینی‌اپ):\n{html.escape(body)}", ticket_kb(b, tid, True))


@router.get("/api/x/tickets")
def tickets(x_telegram_init_data: str | None = Header(default=None)):
    core, b, uid, dbu = ctx(x_telegram_init_data); ensure_tables(b)
    rows = b.q("SELECT * FROM support_tickets WHERE user_id=? ORDER BY id DESC LIMIT 20", (uid,))
    out = []
    for r in rows:
        last = b.q("SELECT body,sender_id,created FROM support_messages WHERE ticket_id=? ORDER BY id DESC LIMIT 1", (r["id"],), True)
        out.append({"id": r["id"], "status": r["status"], "created": r["created"], "updated": r["updated"],
                    "last": (last["body"] or "")[:120] if last else "", "last_admin": bool(last and int(last["sender_id"]) != uid)})
    return {"ok": True, "items": out}


@router.get("/api/x/tickets/{tid}")
def ticket_view(tid: int, x_telegram_init_data: str | None = Header(default=None)):
    core, b, uid, dbu = ctx(x_telegram_init_data); ensure_tables(b); t = _ticket(b, tid, uid)
    msgs = b.q("SELECT sender_id,body,created FROM support_messages WHERE ticket_id=? ORDER BY id ASC LIMIT 200", (tid,))
    return {"ok": True, "id": tid, "status": t["status"], "created": t["created"],
            "messages": [{"me": int(m["sender_id"]) == uid, "body": m["body"] or "", "created": m["created"]} for m in msgs]}


def _clean_body(raw):
    body = (raw or "").strip()
    if not body: raise HTTPException(400, "متن پیام را بنویس")
    if len(body) > 2000: raise HTTPException(400, "پیام خیلی طولانی است (حداکثر ۲۰۰۰ کاراکتر)")
    return body


@router.post("/api/x/tickets")
async def ticket_new(req: TicketReq, x_telegram_init_data: str | None = Header(default=None)):
    core, b, uid, dbu = ctx(x_telegram_init_data); ensure_tables(b); body = _clean_body(req.body)
    async with core.user_lock(uid):
        now = int(time.time())
        t = b.q("SELECT * FROM support_tickets WHERE user_id=? AND status='open' ORDER BY id DESC LIMIT 1", (uid,), True)
        new = not t
        tid = b.ex("INSERT INTO support_tickets(user_id,created,updated) VALUES(?,?,?)", (uid, now, now)) if new else t["id"]
        b.ex("INSERT INTO support_messages(ticket_id,sender_id,body,created) VALUES(?,?,?,?)", (tid, uid, body, now))
        b.ex("UPDATE support_tickets SET updated=? WHERE id=?", (now, tid))
        audit(b, uid, "ticket_open" if new else "ticket_message", tid, body)
    await asyncio.to_thread(_notify_admins_ticket, b, tid, uid, body, new)
    return {"ok": True, "id": tid, "new": new}


@router.post("/api/x/tickets/{tid}/reply")
async def ticket_reply(tid: int, req: TicketReq, x_telegram_init_data: str | None = Header(default=None)):
    core, b, uid, dbu = ctx(x_telegram_init_data); ensure_tables(b); body = _clean_body(req.body)
    async with core.user_lock(uid):
        t = _ticket(b, tid, uid)
        if t["status"] != "open": raise HTTPException(409, "این تیکت بسته شده؛ تیکت جدید باز کن")
        now = int(time.time())
        b.ex("INSERT INTO support_messages(ticket_id,sender_id,body,created) VALUES(?,?,?,?)", (tid, uid, body, now))
        b.ex("UPDATE support_tickets SET updated=?,admin_id=0 WHERE id=?", (now, tid)); audit(b, uid, "ticket_message", tid, body)
    await asyncio.to_thread(_notify_admins_ticket, b, tid, uid, body, False)
    return {"ok": True, "id": tid}


@router.post("/api/x/tickets/{tid}/close")
async def ticket_close(tid: int, x_telegram_init_data: str | None = Header(default=None)):
    core, b, uid, dbu = ctx(x_telegram_init_data); ensure_tables(b)
    async with core.user_lock(uid):
        _ticket(b, tid, uid)
        b.ex("UPDATE support_tickets SET status='closed',updated=? WHERE id=? AND user_id=?", (int(time.time()), tid, uid))
    audit(b, uid, "ticket_close", tid)
    return {"ok": True}


# ---------- rename / transfer ----------
def _service(b, sid, uid):
    s = b.q("SELECT * FROM services WHERE id=? AND user_id=? AND status!='deleted'", (sid, uid), True)
    if not s: raise HTTPException(404, "سرویس پیدا نشد")
    return s


@router.post("/api/x/service/{sid}/rename")
def rename(sid: int, req: RenameReq, x_telegram_init_data: str | None = Header(default=None)):
    core, b, uid, dbu = ctx(x_telegram_init_data); _service(b, sid, uid)
    new = " ".join((req.title or "").split())
    if not new or len(new) > 32: raise HTTPException(400, "نام باید بین ۱ تا ۳۲ کاراکتر باشد")
    try: b.ex("UPDATE services SET title=? WHERE id=?", (new, sid))
    except Exception:
        b.ex("ALTER TABLE services ADD COLUMN title TEXT"); b.ex("UPDATE services SET title=? WHERE id=?", (new, sid))
    return {"ok": True, "id": sid, "title": new}


@router.post("/api/x/service/{sid}/transfer")
async def transfer(sid: int, req: TransferReq, x_telegram_init_data: str | None = Header(default=None)):
    core, b, uid, dbu = ctx(x_telegram_init_data)
    to = int_or_400(req.to, "فقط آیدی عددی کاربر مقصد را وارد کن")
    if to == uid: raise HTTPException(400, "نمی‌توانی به خودت منتقل کنی")
    if not b.get_user(to): raise HTTPException(404, "کاربر مقصد پیدا نشد (باید یک بار ربات را استارت کرده باشد)")
    async with core.user_lock(uid):
        s = _service(b, sid, uid)
        cur = b.CON.execute("UPDATE services SET user_id=? WHERE id=? AND user_id=?", (to, sid, uid)); b.CON.commit()
        if cur.rowcount != 1: raise HTTPException(409, "انتقال انجام نشد؛ دوباره تلاش کن")
        audit(b, uid, "miniapp_transfer", sid, to)
    await asyncio.to_thread(tgapi.safe_send, to, f"🔁 سرویس <code>{html.escape(s['username'])}</code> به حساب شما منتقل شد.")
    return {"ok": True, "id": sid, "to": to}


# ---------- referral ----------
@router.get("/api/x/referral")
def referral(x_telegram_init_data: str | None = Header(default=None)):
    core, b, uid, dbu = ctx(x_telegram_init_data)
    refs = b.q("SELECT COUNT(*) c FROM users WHERE ref_by=?", (uid,), True)["c"]
    bot = core.bot_username()
    return {"ok": True, "link": f"https://t.me/{bot}?start=ref_{uid}" if bot else "", "percent": int(float(S(b, "ref_percent", "0") or 0)), "count": refs}




# ---------- signed browser IP callback ----------
def _ip_sig(bot, uid, exp):
    token = getattr(bot, "BOT_TOKEN", "")
    return __import__("hmac").new(token.encode(), f"{uid}:{exp}".encode(), __import__("hashlib").sha256).hexdigest()[:40]

async def _signed_ip_page(request: Request, uid: int, exp: int, sig: str):
    core = _core(); b = core.bot_module()
    if not uid or exp <= int(time.time()) or not sig or not __import__("hmac").compare_digest(sig, _ip_sig(b, uid, exp)):
        return HTMLResponse("<h1>لینک نامعتبر یا منقضی شده</h1>", status_code=403)
    ip = _client_ip(request)
    fn = getattr(b, "ip_send_result", None)
    if callable(fn):
        try: await fn(uid, ip)
        except Exception: log.exception("signed ip callback failed")
    return HTMLResponse("<meta charset='utf-8'><title>اطلاعات IP</title><body style='font-family:Tahoma;text-align:center;padding:48px;background:#0b1120;color:white'><h2>✓ درخواست ارسال شد</h2><p>نتیجه اطلاعات IP داخل ربات برای شما ارسال شد.</p></body>")

@router.get("/ip-info")
async def ip_info_callback(request: Request, uid: int = Query(0), exp: int = Query(0), sig: str = Query("")):
    return await _signed_ip_page(request, uid, exp, sig)

@router.get("/api/x/ip/ip-info")
async def ip_info_callback_alias(request: Request, uid: int = Query(0), exp: int = Query(0), sig: str = Query("")):
    return await _signed_ip_page(request, uid, exp, sig)

# ---------- IP info ----------
def _client_ip(request: Request):
    for h in ("cf-connecting-ip", "x-real-ip"):
        v = request.headers.get(h)
        if v: return v.strip()
    xf = request.headers.get("x-forwarded-for")
    if xf: return xf.split(",")[0].strip()
    return request.client.host if request.client else ""


def _ip_lookup(ip):
    try:
        safe_ip = ip.replace("/", "").replace("\\", "")
        with urllib.request.urlopen(f"https://ipwho.is/{safe_ip}", timeout=6) as r:
            payload = json.loads(r.read())
            return payload if payload.get("success", True) else {}
    except Exception: return {}


@router.get("/api/x/ip")
async def ip_info(request: Request, x_telegram_init_data: str | None = Header(default=None)):
    ctx(x_telegram_init_data)
    ip = _client_ip(request)
    if not ip: raise HTTPException(500, "IP پیدا نشد")
    d = await asyncio.to_thread(_ip_lookup, ip)
    conn = d.get("connection") or {}; tz = d.get("timezone") or {}; fl = d.get("flag") or {}
    return {"ok": True, "ip": ip, "version": d.get("type") or ("IPv6" if ":" in ip else "IPv4"), "country": d.get("country") or "—",
            "flag": fl.get("emoji") or "🌐", "region": d.get("region") or "—", "city": d.get("city") or "—",
            "isp": conn.get("isp") or conn.get("org") or "—", "asn": conn.get("asn") or "—", "tz": tz.get("id") or "—", "provider": "ipwho.is"}
