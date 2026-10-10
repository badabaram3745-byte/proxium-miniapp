import os, threading
import uvicorn

def web():
    uvicorn.run("miniapp.app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8080")), log_level="info")

if __name__ == "__main__":
    threading.Thread(target=web, daemon=True).start()
    import bot
    bot.main()
