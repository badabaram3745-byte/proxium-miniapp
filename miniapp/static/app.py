import hashlib, hmac, json, os, time
from pathlib import Path
from urllib.parse import parse_qsl
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).parent
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
app = FastAPI(title="Telegram Mini App")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

def validate_init_data(init_data: str):
    if not BOT_TOKEN or not init_data:
        raise HTTPException(401, "Telegram init data is required")
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received = pairs.pop("hash", "")
    if not received:
        raise HTTPException(401, "Invalid Telegram init data")
    auth_date = int(pairs.get("auth_date", "0"))
    if time.time() - auth_date > 86400:
        raise HTTPException(401, "Telegram init data expired")
    data_check = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise HTTPException(401, "Invalid Telegram signature")
    return json.loads(pairs.get("user", "{}"))

@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")

@app.get("/health")
def health():
    return {"ok": True, "service": "telegram-mini-app"}

@app.get("/api/me")
def me(x_telegram_init_data: str | None = Header(default=None)):
    user = validate_init_data(x_telegram_init_data or "")
    return {"ok": True, "user": user}
