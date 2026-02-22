"""
telegram_alert.py

ResQ – Telegram Alert Module
Updated: uses config.py for credentials, includes drone_id in callbacks.
"""

import requests
import json
from datetime import datetime

from config import BOT_TOKEN, CHAT_ID

API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def grid_to_demo_location(grid):
    base_lat = 12.9716
    base_lon = 77.5946
    try:
        r, c = grid
        return round(base_lat + (r - 3) * 0.001, 6), round(base_lon + (c - 3) * 0.001, 6)
    except Exception:
        return base_lat, base_lon


def send_telegram_alert(victim: dict, image_path: str, drone_id: str = "DRONE_1") -> bool:
    try:
        vid      = int(victim.get("id", 0))
        grid     = victim.get("grid", [0, 0])
        priority = victim.get("priority", "UNKNOWN")
        pose     = victim.get("pose", "unknown")

        lat, lon  = grid_to_demo_location(grid)
        map_link  = f"https://www.google.com/maps?q={lat},{lon}"

        caption = (
            "🚨 *RESQ ALERT*\n\n"
            f"🆔 *Victim ID:* `{vid}`\n"
            f"🚁 *Drone:* `{drone_id}`\n"
            f"⚠️ *Priority:* *{priority}*\n"
            f"🧍 *Pose:* `{pose}`\n"
            f"📍 *Grid:* `{grid}`\n"
            f"🗺️ [Open Location]({map_link})\n"
            f"🕒 *Time:* `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
        )

        # callback_data format: action:drone_id:victim_id:row:col
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "🚑 On the Way", "callback_data": f"onway:{drone_id}:{vid}:{grid[0]}:{grid[1]}"},
                    {"text": "✔️ Rescued",    "callback_data": f"rescued:{drone_id}:{vid}:{grid[0]}:{grid[1]}"}
                ],
                [
                    {"text": "❗ False Alarm", "callback_data": f"false:{drone_id}:{vid}:{grid[0]}:{grid[1]}"}
                ]
            ]
        }

        try:
            with open(image_path, "rb") as img:
                res = requests.post(
                    f"{API}/sendPhoto",
                    files={"photo": img},
                    data={
                        "chat_id":      CHAT_ID,
                        "caption":      caption,
                        "parse_mode":   "Markdown",
                        "reply_markup": json.dumps(keyboard)
                    },
                    timeout=10
                )

            if res.status_code != 200:
                print("[Telegram] SEND FAILED:", res.text)
                return False
        except requests.exceptions.RequestException as e:
            print(f"[Telegram] EXCEPTION (Network Offline?): {e}")
            return False

        print(f"[Telegram] Alert sent | {drone_id} Victim {vid}")
        return True

    except Exception as e:
        print("[Telegram] ERROR:", e)
        return False
