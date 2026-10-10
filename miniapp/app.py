import base64, hashlib, hmac, html, io, json, os, time
from pathlib import Path
from urllib.parse import parse_qsl
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).parent
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
app = FastAPI(title="NAYI Mini App")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

class BuyRequest(BaseModel):
    plan_id: int
    panel_id: int | None = None

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

def user_services(b, uid):
    rows = b.q("SELECT * FROM services WHERE user_id=? AND status NOT IN ('deleted') ORDER BY id DESC", (uid,))
    return [{"id": r["id"], "name": r["username"], "gb": r["gb"], "days": r["days"], "expire": r["expire"], "status": r["status"], "link": r["link"] or "", "sub": r["sub"] or "", "qr": qr_data(r["link"] or r["sub"] or "")} for r in rows]

@app.get("/")
def index(): return FileResponse(ROOT / "static" / "index.html")
@app.get("/health")
def health(): return {"ok": True, "service": "nayi-mini-app"}

@app.get("/api/catalog")
def catalog(x_telegram_init_data: str | None = Header(default=None)):
    u = auth(x_telegram_init_data); b = bot_module(); uid = int(u["id"]); dbu = b.get_user(uid)
    plans = b.q("SELECT * FROM plans WHERE active=1 ORDER BY months, gb, days")
    panels = b.q("SELECT id,name,ptype FROM panels WHERE active=1 ORDER BY id")
    out = []
    for p in plans:
        price, _, _ = b.dc_price(uid, p["price"])
        out.append({"id": p["id"], "months": p["months"], "gb": p["gb"], "days": p["days"], "price": price})
    return {"ok": True, "balance": int(dbu["balance"] or 0), "plans": out, "panels": [dict(x) for x in panels], "services": user_services(b, uid)}

@app.get("/api/profile")
def profile(x_telegram_init_data: str | None = Header(default=None)):
    u = auth(x_telegram_init_data); b = bot_module(); dbu = b.get_user(int(u["id"]))
    return {"ok": True, "id": u["id"], "name": dbu["name"] or u.get("first_name", ""), "username": dbu["username"] or u.get("username", ""), "phone": dbu["phone"] or "", "balance": dbu["balance"], "services": len(user_services(b, int(u["id"]))) }

@app.post("/api/buy")
async def buy(req: BuyRequest, x_telegram_init_data: str | None = Header(default=None)):
    u = auth(x_telegram_init_data); b = bot_module(); uid = int(u["id"])
    p = b.q("SELECT * FROM plans WHERE id=? AND active=1", (req.plan_id,), True)
    if not p: raise HTTPException(404, "Plan not found")
    pn = b.q("SELECT * FROM panels WHERE id=? AND active=1", (req.panel_id,), True) if req.panel_id else b.q("SELECT * FROM panels WHERE active=1 ORDER BY id LIMIT 1", one=True)
    if not pn or pn["ptype"] == "manual": raise HTTPException(409, "پنل متصل نیست؛ خرید انجام نشد")
    price, _, code = b.dc_price(uid, p["price"]); dbu = b.get_user(uid)
    if int(dbu["balance"] or 0) < price: raise HTTPException(402, f"موجودی کافی نیست. موجودی: {b.money(dbu['balance'])}")
    b.ex("UPDATE users SET balance=balance-? WHERE id=? AND balance>=?", (price, uid, price))
    try:
        uname = f"{b.USER_PREFIX}{uid}_{b.secrets.token_hex(2)}"; res = await b.panel_create(pn, uname, p["gb"], p["days"]); now=int(time.time())
        sid = b.ex("INSERT INTO services(user_id,plan_id,panel_id,username,link,sub,gb,days,price,created,expire,is_test,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,0,'active')", (uid,p["id"],pn["id"],uname,res["link"],res["sub"],p["gb"],p["days"],price,now,now+p["days"]*86400))
        b.dc_use(uid, code); b.trx_log(uid,"buy",sid,p["id"],pn["id"],p["gb"],p["days"],price,p["price"]-price,code)
        return {"ok": True, "service": {"id": sid, "name": uname, "gb": p["gb"], "days": p["days"], "price": price, "link": res["link"], "sub": res["sub"], "qr": qr_data(res["link"] or res["sub"] or "")}, "balance": int(b.get_user(uid)["balance"])}
    except Exception as e:
        b.ex("UPDATE users SET balance=balance+? WHERE id=?", (price, uid)); raise HTTPException(502, "ساخت سرویس ناموفق بود؛ مبلغ برگشت خورد")
