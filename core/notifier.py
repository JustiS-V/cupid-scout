import os
import requests
from typing import Optional
from core.models import ProfileData, EvaluationResult

class Notifier:
    def __init__(self):
        self.bot_token = os.getenv("NOTIFICATION_BOT_TOKEN")
        self.chat_id = os.getenv("NOTIFICATION_CHAT_ID")

    def notify_match(self, profile: ProfileData, eval_result: EvaluationResult):
        message = (
            f"🔥 **HOT MATCH FOUND!** 🔥\n\n"
            f"👤 **{profile.name}**, {profile.age or 'возраст ?'} ({profile.city or 'город ?'})\n"
            f"📱 Платформа: `{profile.platform}`\n\n"
            f"⭐ Внешность: **{eval_result.attractiveness_score}/10**\n"
            f"🎯 Вайб / Интент: **{eval_result.casual_intent_score}/10** ({eval_result.vibe_type})\n\n"
            f"📝 **Био:**\n_{profile.bio or 'Пусто'}_\n\n"
            f"💡 **Вердикт:** {eval_result.reason}\n"
            f"💬 **Рекомендуемый оупенер:**\n`{eval_result.suggested_opener}`"
        )

        # Print to local console
        print("\n" + "="*50)
        print(message)
        print("="*50 + "\n")

        # Send via Telegram bot if configured
        if self.bot_token and self.chat_id:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            try:
                requests.post(url, json=payload, timeout=10)
                # If there are photos, send the first photo
                if profile.photo_paths and os.path.exists(profile.photo_paths[0]):
                    photo_url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"
                    with open(profile.photo_paths[0], "rb") as photo_file:
                        requests.post(photo_url, data={"chat_id": self.chat_id}, files={"photo": photo_file}, timeout=10)
            except Exception as e:
                print(f"[Notifier] Не удалось отправить в Telegram: {e}")
