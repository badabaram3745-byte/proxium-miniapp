import os
import threading
import uvicorn


def start_web():
    uvicorn.run(
        "miniapp.app:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
        log_level="info",
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    # Keep the bot and Mini App in one Railway service.
    web_thread = threading.Thread(target=start_web, name="miniapp-web", daemon=True)
    web_thread.start()
    import bot
    bot.main()
