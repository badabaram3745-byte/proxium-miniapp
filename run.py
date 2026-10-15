import asyncio
import os
import threading
import uvicorn


def start_web():
    # Do not let uvicorn install uvloop globally. bot.py expects a current loop.
    uvicorn.run(
        "miniapp.app:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
        log_level="info",
        loop="asyncio",
        proxy_headers=True,
        forwarded_allow_ips=os.getenv("FORWARDED_ALLOW_IPS", "127.0.0.1"),
    )


if __name__ == "__main__":
    web_thread = threading.Thread(target=start_web, name="miniapp-web", daemon=True)
    web_thread.start()

    # Python 3.12 + uvloop no longer creates a default event loop automatically.
    # bot.py calls get_event_loop() during startup, so create it explicitly.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    import bot
    bot.main()
