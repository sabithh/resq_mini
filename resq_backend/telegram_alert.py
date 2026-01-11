"""
telegram_alert.py

FINAL FIXED VERSION
- Correct callback format
- Buttons stay after "On the Way"
- Buttons removed only after "Rescued / False"
- Image ALWAYS sent
"""

import requests
import json
from datetime import datetime

# --------------------------------------------------
# TELEGRAM CONFIG
# --------------------------------------------------

BOT_TOKEN = "8492000668:AAFBC8eGDbnuK3GgpF1Jx8juk2kOGp_tCps"
CHAT_ID = "-5114857613"

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# --------------------------------------------------
# GRID → DEMO GPS LOCATION
# --------------------------------------------------

def grid_to_demo_location(grid):
    base_lat = 12.9716
    base_lon = 77.5946
    try:
        r, c = grid
        return round(base_lat + (r - 3) * 0.001, 6), round(base_lon + (c - 3) * 0.001, 6)
    except Exception:
        return base_lat, base_lon

# --------------------------------------------------
# SEND TELEGRAM ALERT
# --------------------------------------------------

def send_telegram_alert(victim: dict, image_path: str) -> bool:
    """
    Sends Telegram alert with:
    - Image
    - Inline buttons
    - CORRECT callback format
    """

    try:
        vid = int(victim.get("id", 0))
        grid = victim.get("grid", [0, 0])
        priority = victim.get("priority", "UNKNOWN")
        pose = victim.get("pose", "unknown")

        lat, lon = grid_to_demo_location(grid)
        map_link = f"https://www.google.com/maps?q={lat},{lon}"

        caption = (
            "🚨 *RESQ ALERT*\n\n"
            f"🆔 *Victim ID:* `{vid}`\n"
            f"⚠️ *Priority:* *{priority}*\n"
            f"🧍 *Pose:* `{pose}`\n"
            f"📍 *Grid:* `{grid}`\n"
            f"🗺️ [Open Location]({map_link})\n"
            f"🕒 *Time:* `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
        )

        # 🔥 IMPORTANT: ":" separator MUST match app.py
        keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "🚑 On the Way",
                        "callback_data": f"onway:{vid}:{grid[0]}:{grid[1]}"
                    },
                    {
                        "text": "✔️ Rescued",
                        "callback_data": f"rescued:{vid}:{grid[0]}:{grid[1]}"
                    }
                ],
                [
                    {
                        "text": "❗ False Alarm",
                        "callback_data": f"false:{vid}:{grid[0]}:{grid[1]}"
                    }
                ]
            ]
        }

        with open(image_path, "rb") as img:
            res = requests.post(
                f"{API}/sendPhoto",
                files={"photo": img},
                data={
                    "chat_id": CHAT_ID,
                    "caption": caption,
                    "parse_mode": "Markdown",
                    "reply_markup": json.dumps(keyboard)
                },
                timeout=10
            )

        if res.status_code != 200:
            print("[Telegram] SEND FAILED:", res.text)
            return False

        print(f"[Telegram] Alert sent | Victim {vid}")
        return True

    except Exception as e:
        print("[Telegram] ERROR:", e)
        return False
