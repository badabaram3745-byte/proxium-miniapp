# Small Telegram Bot API helper for the web side (no new dependencies).
import json, logging, os, secrets, urllib.error, urllib.request

log = logging.getLogger("nayi-tgapi")


def _token():
    return os.getenv("BOT_TOKEN", "")


def _markup(markup):
    if markup is None: return None
    if hasattr(markup, "to_dict"):
        try: return markup.to_dict()
        except Exception: return None
    return markup


def call(method, data=None, timeout=15):
    """Blocking JSON call. Returns result or raises RuntimeError."""
    tok = _token()
    if not tok: raise RuntimeError("BOT_TOKEN is empty")
    data = dict(data or {})
    if "reply_markup" in data:
        mk = _markup(data["reply_markup"])
        if mk is None: data.pop("reply_markup")
        else: data["reply_markup"] = mk
    req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/{method}", data=json.dumps(data).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: j = json.loads(r.read())
    except urllib.error.HTTPError as e:
        try: j = json.loads(e.read())
        except Exception: raise RuntimeError(f"telegram http {e.code}")
    if not j.get("ok"): raise RuntimeError(str(j.get("description") or j)[:200])
    return j.get("result")


def send_photo_bytes(chat_id, content: bytes, filename="receipt.jpg", mime="image/jpeg", caption="", reply_markup=None, parse_mode=None, timeout=30):
    """Multipart upload of an image. Returns Telegram Message dict."""
    tok = _token()
    if not tok: raise RuntimeError("BOT_TOKEN is empty")
    boundary = "----nayi" + secrets.token_hex(12)
    fields = {"chat_id": str(chat_id), "caption": caption[:1000]}
    if parse_mode: fields["parse_mode"] = parse_mode
    mk = _markup(reply_markup)
    if mk is not None: fields["reply_markup"] = json.dumps(mk)
    body = bytearray()
    for k, v in fields.items():
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n".encode() + str(v).encode("utf-8") + b"\r\n"
    body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"{filename}\"\r\n"
             f"Content-Type: {mime}\r\n\r\n").encode() + content + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendPhoto", data=bytes(body),
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: j = json.loads(r.read())
    except urllib.error.HTTPError as e:
        try: j = json.loads(e.read())
        except Exception: raise RuntimeError(f"telegram http {e.code}")
    if not j.get("ok"): raise RuntimeError(str(j.get("description") or j)[:200])
    return j["result"]


def send_message(chat_id, text, reply_markup=None, parse_mode="HTML"):
    data = {"chat_id": chat_id, "text": text[:4000], "disable_web_page_preview": True}
    if parse_mode: data["parse_mode"] = parse_mode
    if reply_markup is not None: data["reply_markup"] = reply_markup
    try: return call("sendMessage", data)
    except RuntimeError as e:
        if parse_mode and "parse" in str(e).lower():   # bad HTML -> retry as plain text
            data.pop("parse_mode", None); return call("sendMessage", data)
        raise


def safe_send(chat_id, text, reply_markup=None, parse_mode="HTML"):
    try: send_message(chat_id, text, reply_markup, parse_mode); return True
    except Exception as e: log.warning("send to %s failed: %s", chat_id, e); return False


def download_file(file_id, limit=10 * 1024 * 1024):
    """Returns (bytes, mime) for a Telegram file_id."""
    info = call("getFile", {"file_id": file_id})
    path = info.get("file_path") or ""
    if not path: raise RuntimeError("file not available")
    with urllib.request.urlopen(f"https://api.telegram.org/file/bot{_token()}/{path}", timeout=30) as r:
        data = r.read(limit + 1)
    if len(data) > limit: raise RuntimeError("file too large")
    low = path.lower()
    mime = "image/png" if low.endswith(".png") else "image/webp" if low.endswith(".webp") else "application/pdf" if low.endswith(".pdf") else "image/jpeg"
    return data, mime
