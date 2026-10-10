# Proxium Mini App, Railway-ready

This is one clean root project. Do not deploy a nested copy.

## Railway
Set the service root to the repository root and redeploy with **Clear build cache** enabled once. Railway must install the root `requirements.txt`, then run `python -u run.py`.

Required variables: `BOT_TOKEN`, `ADMIN_IDS`. Recommended: `DB_PATH=/data/bot.db` with a Railway Volume mounted at `/data`.

The root app keeps the bot and Mini App in the same process. `/health` is served by FastAPI on Railway's `$PORT`.

The Mini App keeps the existing visual design and adds the real bot-backed catalog, panel selection, discounts, test account, usage, renew, QR and Telegram authentication.
