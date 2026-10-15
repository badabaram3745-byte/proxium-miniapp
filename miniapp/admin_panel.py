# NAYI web admin panel (/panel) · additive module, same database as the bot.
# Enable with Railway variables: PANEL_USER (default admin) and PANEL_PASS (required). Optional PANEL_SECRET.
import asyncio, re, base64, hashlib, hmac, html, json, logging, os, time
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

from miniapp import tgapi

log = logging.getLogger("nayi-panel")
router = APIRouter()
ROOT = os.path.dirname(os.path.abspath(__file__))
PANEL_USER = os.getenv("PANEL_USER", "admin").strip() or "admin"
PANEL_PASS = os.getenv("PANEL_PASS", "")
SECRET = (os.getenv("PANEL_SECRET") or hashlib.sha256(("nayi-panel|" + os.getenv("BOT_TOKEN", "") + "|" + PANEL_PASS).encode()).hexdigest()).encode()
COOKIE = "nayi_panel"
TTL = 12 * 3600
WEB_ACTOR = -1          # audit_log actor for web panel actions
_fails: dict[str, list[float]] = {}
_bc = {"running": False, "sent": 0, "failed": 0, "total": 0}


def b():
    import importlib
    return importlib.import_module("miniapp.app").bot_module()


def ip_of(request: Request):
    xf = request.headers.get("x-forwarded-for")
    return (xf.split(",")[0].strip() if xf else (request.client.host if request.client else "?"))


def make_token(user):
    body = base64.urlsafe_b64encode(json.dumps({"u": user, "e": int(time.time()) + TTL}).encode()).decode().rstrip("=")
    return body + "." + hmac.new(SECRET, body.encode(), hashlib.sha256).hexdigest()


def check_token(tok):
    try:
        body, sig = tok.rsplit(".", 1)
        if not hmac.compare_digest(sig, hmac.new(SECRET, body.encode(), hashlib.sha256).hexdigest()): return False
        d = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        return d.get("u") == PANEL_USER and int(d.get("e", 0)) > time.time()
    except Exception: return False


def guard(request: Request, write=False):
    if not PANEL_PASS: raise HTTPException(503, "پنل وب غیرفعال است؛ متغیر PANEL_PASS را در Railway تنظیم کن")
    if not check_token(request.cookies.get(COOKIE, "")): raise HTTPException(401, "وارد شو")
    if write and request.headers.get("x-panel") != "1": raise HTTPException(403, "درخواست نامعتبر")


def audit(action, target="", details=""):
    fn = getattr(b(), "added_audit", None)
    if fn:
        try: fn(WEB_ACTOR, "web_" + action, target, details)
        except Exception: pass


def rows(r): return [dict(x) for x in r]


def has_table(name):
    return bool(b().q("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,), True))


def cols(table):
    try: return {r["name"] for r in b().q(f"PRAGMA table_info({table})")}
    except Exception: return set()


# ---------- pages ----------
@router.get("/panel")
@router.get("/panel/")
def panel_page():
    return FileResponse(os.path.join(ROOT, "static", "panel.html"), headers={"Cache-Control": "no-cache"})


class LoginReq(BaseModel):
    username: str
    password: str


@router.post("/panel/api/login")
def login(req: LoginReq, request: Request):
    if not PANEL_PASS: raise HTTPException(503, "پنل وب غیرفعال است؛ متغیر PANEL_PASS را در Railway تنظیم کن")
    ip = ip_of(request); now = time.time()
    fl = [t for t in _fails.get(ip, []) if now - t < 900]; _fails[ip] = fl
    if len(fl) >= 6: raise HTTPException(429, "تلاش زیاد؛ ۱۵ دقیقه بعد دوباره امتحان کن")
    ok = hmac.compare_digest(req.username.strip().encode(), PANEL_USER.encode()) & hmac.compare_digest(req.password.encode(), PANEL_PASS.encode())
    if not ok:
        fl.append(now); raise HTTPException(401, "نام کاربری یا رمز اشتباه است")
    _fails.pop(ip, None)
    res = JSONResponse({"ok": True})
    secure = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    res.set_cookie(COOKIE, make_token(PANEL_USER), max_age=TTL, httponly=True, secure=secure, samesite="strict", path="/panel")
    audit("login", ip)
    return res


@router.post("/panel/api/logout")
def logout():
    res = JSONResponse({"ok": True}); res.delete_cookie(COOKIE, path="/panel"); return res


@router.get("/panel/api/me")
def me(request: Request):
    guard(request); return {"ok": True, "user": PANEL_USER}

# ---------- additive admin management ----------
def _temp_admins():
    try:
        raw = b().S("temp_admins") or "[]"
        return json.loads(raw) if isinstance(raw, str) else []
    except Exception:
        return []

def _save_temp_admins(items):
    b().set_S("temp_admins", json.dumps(items, ensure_ascii=False, separators=(",", ":")))

class AdminReq(BaseModel):
    user_id: int
    days: int = 0
    hours: int = 0

@router.get("/panel/api/admins")
def admins(request: Request):
    guard(request); x = b(); now = int(time.time())
    temp = [a for a in _temp_admins() if int(a.get("expires", 0)) > now]
    if len(temp) != len(_temp_admins()): _save_temp_admins(temp)
    permanent = sorted(set(getattr(x, "extra_admins", lambda: [])()))
    main = int(getattr(x, "MAIN_ADMIN_ID", 0))
    env = sorted(set(getattr(x, "ENV_ADMIN_IDS", set())))
    def user(uid):
        u = x.q("SELECT id,name,username FROM users WHERE id=?", (uid,), True)
        return {"id": uid, "name": (u["name"] if u else ""), "username": (u["username"] if u else "")}
    return {"ok": True, "main": user(main), "env": [user(i) for i in env if i != main],
            "permanent": [user(i) for i in permanent if i not in env and i != main], "temporary": [dict(user(int(a["id"])), expires=int(a["expires"])) for a in temp]}

@router.post("/panel/api/admins")
def admin_add(req: AdminReq, request: Request):
    guard(request, True); uid = int(req.user_id); x = b()
    if uid <= 0: raise HTTPException(400, "آیدی کاربر نامعتبر است")
    if not x.q("SELECT 1 FROM users WHERE id=?", (uid,), True): raise HTTPException(404, "کاربر پیدا نشد")
    duration = max(0, int(req.days or 0)) * 86400 + max(0, int(req.hours or 0)) * 3600
    if duration:
        items = [a for a in _temp_admins() if int(a.get("id", 0)) != uid]
        items.append({"id": uid, "expires": int(time.time()) + duration})
        _save_temp_admins(items); audit("admin_temp_add", uid, str(duration))
        return {"ok": True, "kind": "temporary"}
    ids = list(getattr(x, "extra_admins", lambda: [])())
    if uid not in ids: ids.append(uid)
    getattr(x, "save_admins")(ids); audit("admin_add", uid)
    return {"ok": True, "kind": "permanent"}

@router.post("/panel/api/admins/{uid}/delete")
def admin_delete(uid: int, request: Request):
    guard(request, True); x = b(); main = int(getattr(x, "MAIN_ADMIN_ID", 0))
    if uid == main or uid in set(getattr(x, "ENV_ADMIN_IDS", set())): raise HTTPException(400, "ادمین اصلی یا تنظیم‌شده قابل حذف نیست")
    getattr(x, "save_admins")([i for i in getattr(x, "extra_admins", lambda: [])() if int(i) != uid])
    _save_temp_admins([a for a in _temp_admins() if int(a.get("id", 0)) != uid]); audit("admin_delete", uid)
    return {"ok": True}


# ---------- dashboard ----------
@router.get("/panel/api/stats")
def stats(request: Request):
    guard(request); x = b(); now = int(time.time()); day = now - 86400
    one = lambda sql, a=(): (x.q(sql, a, True) or {"c": 0})["c"]
    out = {
        "users": one("SELECT COUNT(*) c FROM users"),
        "users_day": one("SELECT COUNT(*) c FROM users WHERE created>?", (day,)),
        "active": one("SELECT COUNT(*) c FROM services WHERE status='active' AND expire>?", (now,)),
        "services": one("SELECT COUNT(*) c FROM services WHERE status!='deleted'"),
        "sales_day": one("SELECT COALESCE(SUM(price),0) c FROM services WHERE created>? AND status!='deleted' AND is_test=0", (day,)),
        "sales_all": one("SELECT COALESCE(SUM(price),0) c FROM services WHERE status!='deleted' AND is_test=0"),
        "topup_day": one("SELECT COALESCE(SUM(amount),0) c FROM payments WHERE status='ok' AND created>?", (day,)),
        "topup_all": one("SELECT COALESCE(SUM(amount),0) c FROM payments WHERE status='ok'"),
        "pending": one("SELECT COUNT(*) c FROM payments WHERE status='pending'"),
        "balance_total": one("SELECT COALESCE(SUM(balance),0) c FROM users"),
        "tickets": one("SELECT COUNT(*) c FROM support_tickets WHERE status='open'") if has_table("support_tickets") else 0,
    }
    days = []
    for i in range(13, -1, -1):
        a = (now // 86400 - i) * 86400; z = a + 86400
        days.append({"t": a, "sales": one("SELECT COALESCE(SUM(price),0) c FROM services WHERE created>=? AND created<? AND status!='deleted' AND is_test=0", (a, z)),
                     "topup": one("SELECT COALESCE(SUM(amount),0) c FROM payments WHERE status='ok' AND created>=? AND created<?", (a, z))})
    out["days"] = days
    return {"ok": True, **out}


# ---------- users ----------
@router.get("/panel/api/users")
def users(request: Request, q: str = "", offset: int = 0):
    guard(request); x = b(); t = q.strip().lstrip("@")
    if t.isdigit():
        r = x.q("SELECT * FROM users WHERE id=? OR phone LIKE ? ORDER BY last_seen DESC LIMIT 50", (int(t), f"%{t}%"))
    elif t:
        r = x.q("SELECT * FROM users WHERE username LIKE ? OR name LIKE ? ORDER BY last_seen DESC LIMIT 50", (f"%{t}%", f"%{t}%"))
    else:
        r = x.q("SELECT * FROM users ORDER BY last_seen DESC LIMIT 50 OFFSET ?", (max(0, offset),))
    return {"ok": True, "items": rows(r)}


@router.get("/panel/api/users/{uid}")
def user_view(uid: int, request: Request):
    guard(request); x = b(); u = x.get_user(uid)
    if not u: raise HTTPException(404, "کاربر پیدا نشد")
    svcs = x.q("SELECT * FROM services WHERE user_id=? ORDER BY id DESC LIMIT 50", (uid,))
    pays = x.q("SELECT id,amount,bonus,status,created FROM payments WHERE user_id=? ORDER BY id DESC LIMIT 30", (uid,))
    refs = x.q("SELECT COUNT(*) c FROM users WHERE ref_by=?", (uid,), True)["c"]
    return {"ok": True, "user": dict(u), "services": rows(svcs), "payments": rows(pays), "refs": refs}


class BalReq(BaseModel):
    op: str
    amount: int
    notify: bool = True


@router.post("/panel/api/users/{uid}/balance")
def user_balance(uid: int, req: BalReq, request: Request):
    guard(request, True); x = b()
    if not x.get_user(uid): raise HTTPException(404, "کاربر پیدا نشد")
    if req.amount <= 0 or req.amount > 10_000_000_000: raise HTTPException(400, "مبلغ نامعتبر")
    if req.op not in ("add", "sub"): raise HTTPException(400, "عملیات نامعتبر")
    x.ex("UPDATE users SET balance=balance" + ("+" if req.op == "add" else "-") + "? WHERE id=?", (req.amount, uid))
    audit("balance_" + req.op, uid, req.amount)
    if req.notify:
        tgapi.safe_send(uid, f"{'➕' if req.op == 'add' else '➖'} {x.money(req.amount)} تومان {'به' if req.op == 'add' else 'از'} کیف پول شما {'اضافه' if req.op == 'add' else 'کسر'} شد.", parse_mode=None)
    return {"ok": True, "balance": int(x.get_user(uid)["balance"] or 0)}


class BanReq(BaseModel):
    banned: bool


@router.post("/panel/api/users/{uid}/ban")
def user_ban(uid: int, req: BanReq, request: Request):
    guard(request, True); x = b()
    if not x.get_user(uid): raise HTTPException(404, "کاربر پیدا نشد")
    if req.banned and (uid in x.ADMIN_IDS): raise HTTPException(400, "ادمین را نمی‌شود مسدود کرد")
    x.ex("UPDATE users SET banned=? WHERE id=?", (1 if req.banned else 0, uid)); audit("ban" if req.banned else "unban", uid)
    return {"ok": True}


class MsgReq(BaseModel):
    text: str
    button_text: str = ""
    button_start: str = ""


@router.post("/panel/api/users/{uid}/message")
def user_message(uid: int, req: MsgReq, request: Request):
    guard(request, True); text = (req.text or "").strip()
    if not text: raise HTTPException(400, "متن خالی است")
    ok = tgapi.safe_send(uid, "📩 پیام از پشتیبانی:\n\n" + text[:3800], parse_mode=None); audit("user_message", uid)
    if not ok: raise HTTPException(502, "ارسال نشد (احتمالاً کاربر ربات را بلاک کرده)")
    return {"ok": True}


# ---------- payments ----------
@router.get("/panel/api/payments")
def payments(request: Request, status: str = "pending"):
    guard(request); x = b()
    st = status if status in ("pending", "ok", "rejected", "error") else "pending"
    has_order = "order_id" in cols("payments")
    r = x.q(f"SELECT p.id,p.user_id,p.amount,p.bonus,p.status,p.created,{'p.order_id' if has_order else 'NULL AS order_id'},"
            "(p.photo LIKE 'zarinpal:%') AS online,u.name,u.username FROM payments p LEFT JOIN users u ON u.id=p.user_id "
            "WHERE p.status=? ORDER BY p.id DESC LIMIT 100", (st,))
    return {"ok": True, "items": rows(r)}


@router.get("/panel/api/payments/{pid}/photo")
def payment_photo(pid: int, request: Request):
    guard(request); x = b()
    p = x.q("SELECT photo FROM payments WHERE id=?", (pid,), True)
    fid = (p["photo"] if p else "") or ""
    if not fid or ":" in fid or fid == "miniapp": raise HTTPException(404, "تصویری برای این پرداخت نیست")
    try: data, mime = tgapi.download_file(fid)
    except Exception as e: raise HTTPException(502, f"دریافت تصویر ناموفق: {e}")
    return Response(data, media_type=mime, headers={"Cache-Control": "private, max-age=600"})


def _claim(x, pid):
    """Atomically move a pending payment to 'processing' so bot + panel never double-approve."""
    cur = x.CON.execute("UPDATE payments SET status='processing' WHERE id=? AND status='pending'", (pid,)); x.CON.commit()
    return cur.rowcount == 1


def _ref_share(x, payer_id, amount):
    payer = x.get_user(payer_id)
    if not payer or not payer["ref_by"]: return
    try: share = int(amount) * int(x.S("ref_percent") or 0) // 100
    except Exception: share = 0
    if share:
        x.ex("UPDATE users SET balance=balance+? WHERE id=?", (share, payer["ref_by"]))
        tgapi.safe_send(payer["ref_by"], f"🤝 {x.money(share)} تومان پاداش زیرمجموعه گرفتی!", parse_mode=None)


@router.post("/panel/api/payments/{pid}/approve")
async def payment_approve(pid: int, request: Request):
    guard(request, True); x = b()
    pay = x.q("SELECT * FROM payments WHERE id=?", (pid,), True)
    if not pay: raise HTTPException(404, "پرداخت پیدا نشد")
    if pay["status"] != "pending": raise HTTPException(409, "این پرداخت قبلاً بررسی شده")
    order_id = pay["order_id"] if "order_id" in pay.keys() else None
    if not _claim(x, pid): raise HTTPException(409, "این پرداخت همزمان در حال بررسی است")
    try:
        if not order_id:   # wallet top-up
            total = int(pay["amount"]) + int(pay["bonus"] or 0)
            x.ex("UPDATE users SET balance=balance+? WHERE id=?", (total, pay["user_id"]))
            x.ex("UPDATE payments SET status='ok' WHERE id=?", (pid,))
            await asyncio.to_thread(_ref_share, x, pay["user_id"], pay["amount"])
            await asyncio.to_thread(tgapi.safe_send, pay["user_id"], f"✅ {x.money(total)} تومان به کیف پولت اضافه شد.", None, None)
            audit("payment_ok", pid, total)
            return {"ok": True, "kind": "topup", "total": total}
        # card-to-card plan order
        order = x.q("SELECT * FROM card_orders WHERE id=? AND status='pending'", (order_id,), True)
        p = x.q("SELECT * FROM plans WHERE id=?", (order["plan_id"],), True) if order else None
        pn = x.q("SELECT * FROM panels WHERE id=? AND active=1", (order["panel_id"],), True) if order else None
        if not order or not p or not pn: raise HTTPException(409, "سفارش/پلن/پنل این رسید در دسترس نیست")
        if pn["ptype"] == "manual": raise HTTPException(409, "پنل دستی است؛ این رسید را از داخل ربات تأیید کن")
        uname = f"{x.USER_PREFIX}{order['user_id']}_{x.secrets.token_hex(2)}"
        res = await x.panel_create(pn, uname, p["gb"], p["days"])
        now = int(time.time())
        sid = x.ex("INSERT INTO services(user_id,plan_id,panel_id,username,link,sub,gb,days,price,created,expire,is_test) VALUES(?,?,?,?,?,?,?,?,?,?,?,0)",
                   (order["user_id"], p["id"], pn["id"], uname, res["link"], res["sub"], p["gb"], p["days"], order["amount"], now, now + p["days"] * 86400))
        x.ex("UPDATE payments SET status='ok' WHERE id=?", (pid,))
        x.ex("UPDATE card_orders SET status='ok',updated=? WHERE id=?", (now, order["id"]))
        try: x.trx_log(order["user_id"], "card_buy", sid, p["id"], pn["id"], p["gb"], p["days"], order["amount"])
        except Exception: pass
        link = res.get("sub") or res.get("link") or "-"
        await asyncio.to_thread(tgapi.safe_send, order["user_id"],
                                f"✅ <b>پرداخت تأیید و سرویس ساخته شد</b>\n👤 <code>{html.escape(uname)}</code>\n🟢 {p['gb']} گیگ | ⏳ {p['days']} روز\n\n🔗 لینک اتصال:\n<code>{html.escape(link)}</code>")
        audit("card_order_ok", pid, sid)
        return {"ok": True, "kind": "order", "service_id": sid}
    except HTTPException:
        x.ex("UPDATE payments SET status='pending' WHERE id=? AND status='processing'", (pid,)); raise
    except Exception as e:
        x.ex("UPDATE payments SET status='pending' WHERE id=? AND status='processing'", (pid,))
        log.exception("panel approve failed")
        raise HTTPException(502, f"تأیید ناموفق بود: {str(e)[:200]}")


@router.post("/panel/api/payments/{pid}/reapprove")
async def payment_reapprove(pid: int, request: Request):
    """Second look at a rejected receipt: reopen it and run the normal approve flow."""
    guard(request, True); x = b()
    pay = x.q("SELECT * FROM payments WHERE id=?", (pid,), True)
    if not pay: raise HTTPException(404, "پرداخت پیدا نشد")
    cur = x.CON.execute("UPDATE payments SET status='pending' WHERE id=? AND status IN ('rejected','error')", (pid,)); x.CON.commit()
    if cur.rowcount != 1: raise HTTPException(409, "فقط رسیدهای ردشده قابل بررسی دوباره‌اند")
    order_id = pay["order_id"] if "order_id" in pay.keys() else None
    if order_id: x.ex("UPDATE card_orders SET status='pending',updated=? WHERE id=?", (int(time.time()), order_id))
    try:
        res = await payment_approve(pid, request)
    except Exception:
        x.ex("UPDATE payments SET status=? WHERE id=? AND status='pending'", (pay["status"], pid))
        if order_id: x.ex("UPDATE card_orders SET status='rejected',updated=? WHERE id=?", (int(time.time()), order_id))
        raise
    audit("payment_reapprove", pid)
    return res


@router.post("/panel/api/payments/{pid}/reject")
def payment_reject(pid: int, request: Request):
    guard(request, True); x = b()
    pay = x.q("SELECT * FROM payments WHERE id=?", (pid,), True)
    if not pay: raise HTTPException(404, "پرداخت پیدا نشد")
    if not _claim(x, pid): raise HTTPException(409, "این پرداخت قبلاً بررسی شده")
    x.ex("UPDATE payments SET status='rejected' WHERE id=?", (pid,))
    order_id = pay["order_id"] if "order_id" in pay.keys() else None
    if order_id: x.ex("UPDATE card_orders SET status='rejected',updated=? WHERE id=?", (int(time.time()), order_id))
    tgapi.safe_send(pay["user_id"], "❌ رسید شما رد شد. با پشتیبانی در ارتباط باشید.", parse_mode=None); audit("payment_reject", pid)
    return {"ok": True}


# ---------- services ----------
@router.get("/panel/api/services")
def services(request: Request, q: str = "", status: str = "", offset: int = 0, limit: int = 50):
    guard(request); x = b(); args = []; where = ["s.status!='deleted'"]
    if status in ("active", "pending", "expired", "disabled", "limited"): where.append("s.status=?"); args.append(status)
    t = q.strip().lstrip("@")
    if t:
        if t.isdigit(): where.append("(s.user_id=? OR s.id=?)"); args += [int(t), int(t)]
        else: where.append("(s.username LIKE ? OR u.username LIKE ? OR u.name LIKE ?)"); args += [f"%{t}%"] * 3
    limit = max(1, min(int(limit or 50), 200)); offset = max(0, int(offset or 0))
    base = "FROM services s LEFT JOIN panels p ON p.id=s.panel_id LEFT JOIN users u ON u.id=s.user_id WHERE " + " AND ".join(where)
    total = (x.q("SELECT COUNT(*) c " + base, tuple(args), True) or {"c": 0})["c"]
    r = x.q("SELECT s.id,s.user_id,s.username,s.gb,s.days,s.price,s.created,s.expire,s.status,s.is_test,s.link,s.sub,"
            "p.name panel,p.ptype,u.name uname,u.username uuser,u.phone uphone " + base + " ORDER BY s.id DESC LIMIT ? OFFSET ?", tuple(args) + (limit, offset))
    return {"ok": True, "items": rows(r), "total": total, "offset": offset, "limit": limit}


async def _panel_set_active(x, pn, username, active):
    """Enable/disable one user on the real panel (Marzban, Pasarguard, Marzneshin, 3x-UI family)."""
    t = pn["ptype"]
    async with x._http(pn) as c:
        if t in ("marzban", "pasarguard"):
            h = await x._token(c, pn)
            r = await c.put(f"/api/user/{username}", json={"status": "active" if active else "disabled"}, headers=h)
            if r.status_code >= 400: raise Exception(f"HTTP {r.status_code}: {r.text[:200]}")
        elif t == "marzneshin":
            h = await x._token(c, pn)
            r = await c.post(f"/api/users/{username}/{'enable' if active else 'disable'}", headers=h)
            if r.status_code >= 400: raise Exception(f"HTTP {r.status_code}: {r.text[:200]}")
        elif t in getattr(x, "XUI_PREFIX", {}):
            await x._xlogin(c, pn)
            inb, inbound, client = await x._xui_find(c, t, pn, username)
            if not client: raise Exception("کلاینت روی پنل پیدا نشد")
            client["enable"] = bool(active)
            r = await c.post(f"{x.XUI_PREFIX[t]}/updateClient/{x._xui_cid(inbound, client)}",
                             data={"id": inb, "settings": json.dumps({"clients": [client]})})
            j = r.json()
            if not j.get("success"): raise Exception(j.get("msg") or "updateClient failed")
        elif t == "hiddify" and hasattr(x, "hiddify_set_active"):  # ➕ هیدیفای
            await x.hiddify_set_active(pn, username, active)
        else:
            raise Exception("نوع پنل پشتیبانی نمی‌شود")


@router.post("/panel/api/services/{sid}/toggle")
async def service_toggle(sid: int, request: Request):
    guard(request, True); x = b()
    s = x.q("SELECT * FROM services WHERE id=? AND status!='deleted'", (sid,), True)
    if not s: raise HTTPException(404, "سرویس پیدا نشد")
    if s["status"] == "pending": raise HTTPException(409, "این سرویس هنوز تحویل نشده")
    enable = s["status"] == "disabled"
    pn = x.q("SELECT * FROM panels WHERE id=?", (s["panel_id"],), True)
    if pn and pn["ptype"] != "manual":
        try: await _panel_set_active(x, pn, s["username"], enable)
        except Exception as e: raise HTTPException(502, f"تغییر وضعیت روی پنل ناموفق بود: {str(e)[:150]}")
    new = "active" if enable else "disabled"
    x.ex("UPDATE services SET status=? WHERE id=?", (new, sid)); audit("service_" + ("enable" if enable else "disable"), sid)
    tgapi.safe_send(s["user_id"], f"{'✅' if enable else '⛔️'} سرویس <code>{html.escape(s['username'])}</code> {'فعال' if enable else 'غیرفعال'} شد.")
    return {"ok": True, "status": new}


@router.post("/panel/api/services/{sid}/delete")
async def service_delete(sid: int, request: Request):
    guard(request, True); x = b()
    s = x.q("SELECT * FROM services WHERE id=? AND status!='deleted'", (sid,), True)
    if not s: raise HTTPException(404, "سرویس پیدا نشد")
    pn = x.q("SELECT * FROM panels WHERE id=?", (s["panel_id"],), True)
    if pn and pn["ptype"] != "manual" and s["status"] != "pending":
        fn = getattr(x, "panel_delete", None)
        if fn:
            try: await fn(pn, s["username"])
            except Exception as e: raise HTTPException(502, f"حذف از پنل ناموفق بود: {str(e)[:150]}")
    x.ex("UPDATE services SET status='deleted' WHERE id=?", (sid,)); audit("service_delete", sid)
    return {"ok": True}


# ---------- plans ----------
@router.get("/panel/api/plans")
def plans(request: Request):
    guard(request); return {"ok": True, "items": rows(b().q("SELECT * FROM plans ORDER BY months,gb,days"))}


class PlanReq(BaseModel):
    months: int
    gb: int
    days: int
    price: int


@router.post("/panel/api/plans")
def plan_add(req: PlanReq, request: Request):
    guard(request, True)
    if min(req.months, req.gb, req.days) <= 0 or req.price < 0: raise HTTPException(400, "مقادیر نامعتبر")
    pid = b().ex("INSERT INTO plans(months,gb,days,price) VALUES(?,?,?,?)", (req.months, req.gb, req.days, req.price)); audit("plan_add", pid)
    return {"ok": True, "id": pid}

class PlanBulkReq(BaseModel):
    months: int
    days: int
    items: list[dict]

@router.post("/panel/api/plans/bulk")
def plan_bulk(req: PlanBulkReq, request: Request):
    guard(request, True); x = b()
    if req.months <= 0 or req.days <= 0 or not req.items or len(req.items) > 50: raise HTTPException(400, "لیست پلن‌ها نامعتبر است")
    ids = []
    for item in req.items:
        gb, price = int(item.get("gb", 0)), int(item.get("price", -1))
        if gb <= 0 or price < 0: raise HTTPException(400, "حجم یا قیمت نامعتبر است")
        ids.append(x.ex("INSERT INTO plans(months,gb,days,price) VALUES(?,?,?,?)", (req.months, gb, req.days, price)))
    audit("plan_bulk_add", len(ids)); return {"ok": True, "ids": ids}


class PlanEdit(BaseModel):
    price: int | None = None
    gb: int | None = None
    days: int | None = None
    active: bool | None = None


@router.post("/panel/api/plans/{pid}")
def plan_edit(pid: int, req: PlanEdit, request: Request):
    guard(request, True); x = b()
    if not x.q("SELECT 1 FROM plans WHERE id=?", (pid,), True): raise HTTPException(404, "پلن پیدا نشد")
    if req.price is not None:
        if req.price < 0: raise HTTPException(400, "قیمت نامعتبر")
        x.ex("UPDATE plans SET price=? WHERE id=?", (req.price, pid))
    if req.gb is not None:
        if req.gb <= 0: raise HTTPException(400, "حجم نامعتبر")
        x.ex("UPDATE plans SET gb=? WHERE id=?", (req.gb, pid))
    if req.days is not None:
        if req.days <= 0: raise HTTPException(400, "مدت نامعتبر")
        x.ex("UPDATE plans SET days=? WHERE id=?", (req.days, pid))
    if req.active is not None: x.ex("UPDATE plans SET active=? WHERE id=?", (1 if req.active else 0, pid))
    audit("plan_edit", pid, req.model_dump_json()); return {"ok": True}


@router.post("/panel/api/plans/{pid}/delete")
def plan_delete(pid: int, request: Request):
    guard(request, True); b().ex("DELETE FROM plans WHERE id=?", (pid,)); audit("plan_delete", pid); return {"ok": True}


# ---------- panels ----------
@router.get("/panel/api/panels")
def panels(request: Request):
    guard(request); x = b()
    r = x.q("SELECT id,name,ptype,url,user,extra,active FROM panels ORDER BY id")
    cnt = {p["panel_id"]: p["c"] for p in x.q("SELECT panel_id, COUNT(*) c FROM services WHERE status='active' GROUP BY panel_id")}
    return {"ok": True, "items": [{**dict(p), "services": cnt.get(p["id"], 0)} for p in r]}


@router.post("/panel/api/panels/{pid}/toggle")
def panel_toggle(pid: int, request: Request):
    guard(request, True); b().ex("UPDATE panels SET active=1-active WHERE id=?", (pid,)); audit("panel_toggle", pid); return {"ok": True}


@router.post("/panel/api/panels/{pid}/test")
async def panel_test(pid: int, request: Request):
    guard(request, True); x = b()
    p = x.q("SELECT * FROM panels WHERE id=?", (pid,), True)
    if not p: raise HTTPException(404, "پنل پیدا نشد")
    try: ok, msg = await x.panel_test(p)
    except Exception as e: ok, msg = False, str(e)
    import re
    return {"ok": True, "success": bool(ok), "message": re.sub(r"<[^>]+>", "", msg or "")[:300]}


# ➕ ---------- panels: add / delete (همان دیتابیس ربات؛ فوراً در ربات هم دیده می‌شود) ----------
@router.get("/panel/api/panel-types")
def panel_types(request: Request):
    guard(request); x = b()
    hints = getattr(x, "EXTRA_HINT", {})
    return {"ok": True, "items": [{"id": t, "name": n, "hint": hints.get(t, "")} for t, n in x.PANEL_TYPES],
            "soon": list(getattr(x, "SOON_PANELS", []))}


class PanelAdd(BaseModel):
    name: str
    ptype: str
    url: str = ""
    user: str = ""
    password: str = ""
    extra: str = ""


@router.post("/panel/api/panels")
async def panel_add(req: PanelAdd, request: Request):
    guard(request, True); x = b()
    name, ptype = req.name.strip(), req.ptype.strip()
    if ptype not in {t for t, _ in x.PANEL_TYPES}: raise HTTPException(400, "نوع پنل نامعتبر است")
    if not name: raise HTTPException(400, "اسم پنل را وارد کن")
    url, user, pw, extra = req.url.strip().rstrip("/"), req.user.strip(), req.password, req.extra.strip()
    if extra == "-": extra = ""
    if ptype != "manual":
        if not url: raise HTTPException(400, "لینک پنل را وارد کن")
        if ptype != "hiddify" and (not user or not pw): raise HTTPException(400, "یوزرنیم و پسورد پنل را وارد کن")
    else:
        url = user = pw = extra = ""
    np = {"name": name, "ptype": ptype, "url": url, "user": user, "password": pw, "extra": extra}
    try: ok, msg = await x.panel_test(np)
    except Exception as e: ok, msg = False, str(e)
    pid = x.ex("INSERT INTO panels(name,ptype,url,user,password,extra) VALUES(?,?,?,?,?,?)",
               (name, ptype, url, user, pw, extra))
    audit("panel_add", pid, f"{ptype} ok={ok}")
    return {"ok": True, "id": pid, "success": bool(ok), "message": re.sub(r"<[^>]+>", "", msg or "")[:300]}


@router.post("/panel/api/panels/{pid}/delete")
def panel_delete(pid: int, request: Request):
    guard(request, True); x = b()
    p = x.q("SELECT * FROM panels WHERE id=?", (pid,), True)
    if not p: raise HTTPException(404, "پنل پیدا نشد")
    x.ex("DELETE FROM panels WHERE id=?", (pid,))   # همان کاری که دکمه «حذف پنل» داخل ربات انجام می‌دهد
    audit("panel_delete", pid, p["name"])
    return {"ok": True}


# ---------- per-user discounts (additive) ----------
@router.get("/panel/api/user-discounts")
def user_discounts(request: Request):
    guard(request); x = b()
    x.ex("CREATE TABLE IF NOT EXISTS user_discounts(user_id INTEGER PRIMARY KEY, percent INTEGER NOT NULL, active INTEGER DEFAULT 1, created INTEGER)")
    r = x.q("SELECT d.*,u.name,u.username FROM user_discounts d LEFT JOIN users u ON u.id=d.user_id ORDER BY d.created DESC")
    return {"ok": True, "items": rows(r)}

class UserDiscountReq(BaseModel):
    user_id: int
    percent: int

@router.post("/panel/api/user-discounts")
def user_discount_add(req: UserDiscountReq, request: Request):
    guard(request, True); x = b(); uid = int(req.user_id); percent = max(1, min(100, int(req.percent)))
    if not x.q("SELECT 1 FROM users WHERE id=?", (uid,), True): raise HTTPException(404, "کاربر پیدا نشد")
    x.ex("CREATE TABLE IF NOT EXISTS user_discounts(user_id INTEGER PRIMARY KEY, percent INTEGER NOT NULL, active INTEGER DEFAULT 1, created INTEGER)")
    x.ex("INSERT INTO user_discounts(user_id,percent,active,created) VALUES(?,?,1,?) ON CONFLICT(user_id) DO UPDATE SET percent=excluded.percent,active=1", (uid, percent, int(time.time())))
    audit("user_discount_add", uid, str(percent)); return {"ok": True}

@router.post("/panel/api/user-discounts/{uid}/delete")
def user_discount_delete(uid: int, request: Request):
    guard(request, True); x = b(); x.ex("CREATE TABLE IF NOT EXISTS user_discounts(user_id INTEGER PRIMARY KEY, percent INTEGER NOT NULL, active INTEGER DEFAULT 1, created INTEGER)")
    x.ex("DELETE FROM user_discounts WHERE user_id=?", (uid,)); audit("user_discount_delete", uid); return {"ok": True}

# ---------- discounts ----------
@router.get("/panel/api/discounts")
def discounts(request: Request):
    guard(request)
    if not has_table("discounts"): return {"ok": True, "items": []}
    return {"ok": True, "items": rows(b().q("SELECT * FROM discounts ORDER BY created DESC"))}


class DcReq(BaseModel):
    code: str
    percent: int
    max_uses: int = 0


@router.post("/panel/api/discounts")
def discount_add(req: DcReq, request: Request):
    guard(request, True); code = req.code.strip()[:40]
    if not code or not 1 <= req.percent <= 100 or req.max_uses < 0: raise HTTPException(400, "کد یا درصد نامعتبر")
    x = b()
    if x.q("SELECT 1 FROM discounts WHERE code=?", (code,), True): raise HTTPException(409, "این کد وجود دارد")
    x.ex("INSERT INTO discounts(code,percent,max_uses,created) VALUES(?,?,?,?)", (code, req.percent, req.max_uses, int(time.time()))); audit("discount_add", code)
    return {"ok": True}


@router.post("/panel/api/discounts/{code}/toggle")
def discount_toggle(code: str, request: Request):
    guard(request, True); b().ex("UPDATE discounts SET active=1-active WHERE code=?", (code,)); return {"ok": True}


@router.post("/panel/api/discounts/{code}/delete")
def discount_delete(code: str, request: Request):
    guard(request, True); b().ex("DELETE FROM discounts WHERE code=?", (code,)); audit("discount_delete", code); return {"ok": True}


# ---------- tickets ----------
@router.get("/panel/api/tickets")
def tickets(request: Request, status: str = "open"):
    guard(request)
    if not has_table("support_tickets"): return {"ok": True, "items": []}
    st = "closed" if status == "closed" else "open"
    r = b().q("SELECT t.*,u.name,u.username FROM support_tickets t LEFT JOIN users u ON u.id=t.user_id WHERE t.status=? ORDER BY t.updated DESC LIMIT 60", (st,))
    return {"ok": True, "items": rows(r)}


@router.get("/panel/api/tickets/{tid}")
def ticket_view(tid: int, request: Request):
    guard(request); x = b()
    t = x.q("SELECT * FROM support_tickets WHERE id=?", (tid,), True)
    if not t: raise HTTPException(404, "تیکت پیدا نشد")
    msgs = x.q("SELECT sender_id,body,created FROM support_messages WHERE ticket_id=? ORDER BY id ASC LIMIT 300", (tid,))
    return {"ok": True, "ticket": dict(t), "messages": [{"admin": int(m["sender_id"]) != int(t["user_id"]), "body": m["body"] or "", "created": m["created"]} for m in msgs]}


@router.post("/panel/api/tickets/{tid}/reply")
def ticket_reply(tid: int, req: MsgReq, request: Request):
    guard(request, True); x = b(); body = (req.text or "").strip()
    if not body: raise HTTPException(400, "متن خالی است")
    t = x.q("SELECT * FROM support_tickets WHERE id=? AND status='open'", (tid,), True)
    if not t: raise HTTPException(409, "تیکت بسته است")
    now = int(time.time()); sender = getattr(x, "MAIN_ADMIN_ID", 0) or 0
    x.ex("INSERT INTO support_messages(ticket_id,sender_id,body,created) VALUES(?,?,?,?)", (tid, sender, body, now))
    x.ex("UPDATE support_tickets SET updated=?,admin_id=? WHERE id=?", (now, sender, tid)); audit("ticket_reply", tid)
    kb = None
    try: kb = x.added_ticket_kb(tid, False)
    except Exception: pass
    tgapi.safe_send(t["user_id"], f"📩 <b>پاسخ پشتیبانی برای تیکت #{tid}</b>\n\n{html.escape(body)}", kb)
    return {"ok": True}


@router.post("/panel/api/tickets/{tid}/close")
def ticket_close(tid: int, request: Request):
    guard(request, True)
    b().ex("UPDATE support_tickets SET status='closed',updated=? WHERE id=?", (int(time.time()), tid)); audit("ticket_close", tid)
    return {"ok": True}


# ---------- bot appearance (تغییرات ظاهر) ----------
COLOR_KEYS = ("orig", "green", "red", "blue", "none")


def _norm(t):
    return re.sub(r"[\s\u200c\u200f\u200e]+", "", str(t or "").replace("ي", "ی").replace("ك", "ک")).lower()


def _guess_text(name, texts):
    n = _norm(name); best, score = "", 0
    for key, (title, _) in texts.items():
        tt = _norm(title)
        if not tt: continue
        sc = 3 if tt == n else 2 if (tt in n or n in tt) else 0
        if sc > score: best, score = key, sc
    return best


@router.get("/panel/api/appearance")
def appearance(request: Request):
    guard(request); x = b()
    groups = list(dict.fromkeys(getattr(x, "BTN_GROUPS", {}).values()))
    names = list(dict.fromkeys(getattr(x, "BTN_NAMES", [])))
    texts = getattr(x, "TEXTS", {})
    buttons = []
    for i, name in enumerate(names):
        g = name in groups
        buttons.append({"name": name, "group": g, "label": "" if g else (x.S("btnname:" + name) or ""),
                        "color": x.S("color:" + name) or "orig", "emoji": "" if g else (x.S("btnemoji:" + name) or ""),
                        "text": "" if g else _guess_text(name, texts)})
    tx = [{"key": k, "title": v[0], "default": v[1], "value": x.S("text:" + k) or v[1], "custom": bool(x.S("text:" + k))}
          for k, v in texts.items()]
    em = getattr(x, "EMOJI", {})
    emojis = [{"key": k, "fallback": v, "id": x.S("emoji:" + k) or "", "custom": x.S("emoji_fb:" + k) or ""} for k, v in em.items()]
    return {"ok": True, "buttons": buttons, "texts": tx, "emojis": emojis, "premium": x.S("premium_on") == "1"}

class EmojiReq(BaseModel):
    key: str
    emoji_id: str = ""
    fallback: str = ""

@router.post("/panel/api/appearance/emoji")
def appearance_emoji(req: EmojiReq, request: Request):
    guard(request, True); x = b(); em = getattr(x, "EMOJI", {})
    if req.key not in em: raise HTTPException(404, "ایموجی پیدا نشد")
    eid = re.sub(r"\D", "", (req.emoji_id or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")))[:20]
    if req.emoji_id.strip() and not re.fullmatch(r"[0-9]{15,20}", eid): raise HTTPException(400, "آیدی ایموجی باید ۱۵ تا ۲۰ رقم باشد")
    fb = (req.fallback or em[req.key] or "⭐️").strip()[:8]
    x.set_S("emoji:" + req.key, eid); x.set_S("emoji_fb:" + req.key, fb)
    audit("look_emoji", req.key, eid); return {"ok": True, "id": eid, "fallback": fb}


class BtnLookReq(BaseModel):
    name: str
    color: str | None = None
    label: str | None = None
    emoji: str | None = None


@router.post("/panel/api/appearance/button")
def appearance_button(req: BtnLookReq, request: Request):
    guard(request, True); x = b(); name = req.name
    groups = set(getattr(x, "BTN_GROUPS", {}).values())
    if name not in set(getattr(x, "BTN_NAMES", [])) | groups: raise HTTPException(404, "دکمه پیدا نشد")
    if req.color is not None:
        if req.color not in COLOR_KEYS: raise HTTPException(400, "رنگ نامعتبر")
        x.set_S("color:" + name, "" if req.color == "orig" else req.color)
    if req.label is not None:
        if name in groups: raise HTTPException(400, "نام گروه‌ها قابل تغییر نیست")
        lab = " ".join(req.label.split())[:60]
        x.set_S("btnname:" + name, "" if lab == name else lab)
    if req.emoji is not None:
        if name in groups: raise HTTPException(400, "برای گروه‌ها ایموجی جدا قابل تنظیم نیست")
        e = re.sub(r"\D", "", req.emoji.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")))[:40]
        if req.emoji.strip() and not e: raise HTTPException(400, "آیدی ایموجی پریمیوم باید عددی باشد")
        x.set_S("btnemoji:" + name, e)
    audit("look_button", name, req.model_dump_json(exclude_none=True)[:200])
    return {"ok": True}


class TextLookReq(BaseModel):
    key: str
    value: str = ""
    reset: bool = False


@router.post("/panel/api/appearance/text")
def appearance_text(req: TextLookReq, request: Request):
    guard(request, True); x = b(); texts = getattr(x, "TEXTS", {})
    if req.key not in texts: raise HTTPException(404, "متن پیدا نشد")
    v = "" if req.reset else req.value.strip()[:4000]
    if not req.reset and not v: raise HTTPException(400, "متن خالی است")
    x.set_S("text:" + req.key, v); audit("look_text", req.key)
    return {"ok": True, "value": v or texts[req.key][1]}


# ---------- settings ----------
HIDDEN_KEYS = {"extra_admins", "abk_last", "groups"}


@router.get("/panel/api/settings")
def settings(request: Request):
    guard(request); x = b(); titles = getattr(x, "SETTING_TITLES", {})
    items = [{"k": k, "title": titles.get(k, k), "v": x.S(k), "toggle": str(v) in ("0", "1") and k not in titles}
             for k, v in x.DEFAULT_SETTINGS.items() if k not in HIDDEN_KEYS]
    return {"ok": True, "items": items}


class SetReq(BaseModel):
    k: str
    v: str


@router.post("/panel/api/settings")
def setting_set(req: SetReq, request: Request):
    guard(request, True); x = b()
    if req.k not in x.DEFAULT_SETTINGS or req.k in HIDDEN_KEYS: raise HTTPException(400, "کلید نامعتبر")
    v = "" if req.v.strip() == "-" else req.v.strip()[:2000]
    x.set_S(req.k, v); audit("setting", req.k, v[:200]); return {"ok": True}


# ---------- transactions & audit ----------
@router.get("/panel/api/transactions")
def transactions(request: Request):
    guard(request)
    if not has_table("txlog"): return {"ok": True, "items": []}
    return {"ok": True, "items": rows(b().q("SELECT * FROM txlog ORDER BY id DESC LIMIT 150"))}


@router.get("/panel/api/audit")
def audit_log(request: Request):
    guard(request)
    if not has_table("audit_log"): return {"ok": True, "items": []}
    return {"ok": True, "items": rows(b().q("SELECT * FROM audit_log ORDER BY id DESC LIMIT 150"))}


# ---------- broadcast ----------
async def _broadcast(text, markup=None):
    x = b(); ids = [r["id"] for r in x.q("SELECT id FROM users WHERE banned=0")]
    _bc.update(running=True, sent=0, failed=0, total=len(ids))
    try:
        for uid in ids:
            ok = await asyncio.to_thread(tgapi.safe_send, uid, text, markup, None)
            _bc["sent" if ok else "failed"] += 1
            await asyncio.sleep(0.05)       # ~20 msg/s, under Telegram limits
    finally:
        _bc["running"] = False
    audit("broadcast", _bc["total"], f"sent={_bc['sent']} failed={_bc['failed']}")


@router.post("/panel/api/broadcast")
async def broadcast(req: MsgReq, request: Request):
    guard(request, True); text = (req.text or "").strip()
    if not text: raise HTTPException(400, "متن خالی است")
    if _bc["running"]: raise HTTPException(409, "یک پیام همگانی در حال ارسال است")
    label = (req.button_text or "").strip()[:64]
    start = re.sub(r"[^a-zA-Z0-9_\-]", "", (req.button_start or "start").strip())[:50] or "start"
    markup = None
    if label:
        username = os.getenv("BOT_USERNAME", "").strip().lstrip("@")
        if not username: raise HTTPException(400, "BOT_USERNAME برای دکمه استارت تنظیم نشده است")
        markup = {"inline_keyboard": [[{"text": "✅ " + label, "url": f"https://t.me/{username}?start={start}", "style": "success"}]]}
    asyncio.create_task(_broadcast(text[:4000], markup))
    return {"ok": True}


@router.get("/panel/api/broadcast")
def broadcast_status(request: Request):
    guard(request); return {"ok": True, **_bc}
