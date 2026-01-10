"""
telegram_alert.py

Telegram alert helper for ResQ backend
- Sends victim image (annotated / cropped)
- Inline response buttons
- Demo GPS location link
"""

import requests
import json
from datetime import datetime

# --------------------------------------------------
# TELEGRAM CONFIG (HARD-CODED)
# --------------------------------------------------

BOT_TOKEN ="8492000668:AAFBC8eGDbnuK3GgpF1Jx8juk2kOGp_tCps"
CHAT_ID = "-5114857613"

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# --------------------------------------------------
# GRID → DEMO GPS LOCATION
# --------------------------------------------------

def grid_to_demo_location(grid):
    """
    Convert grid position to demo GPS coordinates.
    (Demo only – replace with real GPS later)
    """
    base_lat = 12.9716
    base_lon = 77.5946

    try:
        row, col = grid
        lat = base_lat + (row - 3) * 0.001
        lon = base_lon + (col - 3) * 0.001
        return round(lat, 6), round(lon, 6)
    except Exception:
        return base_lat, base_lon

# --------------------------------------------------
# SEND TELEGRAM ALERT (FIXED CALLBACK FORMAT)
# --------------------------------------------------

def send_telegram_alert(victim: dict, image_path: str) -> bool:
    """
    Sends Telegram alert with:
    - Victim image
    - Details
    - Inline buttons (WORKING)
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
            f"🗺️ [Open Location in Maps]({map_link})\n"
            f"🕒 *Time:* `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
        )

        # 🔥 CALLBACK DATA USES ":" (MATCHES app.py)
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
            response = requests.post(
                f"{API}/sendPhoto",
                data={
                    "chat_id": CHAT_ID,
                    "caption": caption,
                    "parse_mode": "Markdown",
                    "reply_markup": json.dumps(keyboard)
                },
                files={"photo": img},
                timeout=10
            )

        if response.status_code != 200:
            print("[Telegram] Failed to send:", response.text)
            return False

        print(f"[Telegram] Alert sent successfully | Victim ID {vid}")
        return True

    except Exception as e:
        print("[Telegram] Error:", e)
        return False
