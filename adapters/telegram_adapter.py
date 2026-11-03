import os
import time
import asyncio
from pathlib import Path
from adapters.base import BasePlatformAdapter
from core.models import ProfileData

class TelegramDatingAdapter(BasePlatformAdapter):
    """
    Адаптер для Telegram-дейтинг ботов (например, @leomatchbot - ДайВинчик).
    Использует клиент Telethon под вашим аккаунтом.
    """
    def __init__(self, bot_handle: str = "@leomatchbot", download_dir: str = "./downloads"):
        self.bot_handle = bot_handle
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.api_id = os.getenv("TELEGRAM_API_ID")
        self.api_hash = os.getenv("TELEGRAM_API_HASH")
        self.phone = os.getenv("TELEGRAM_PHONE")
        self.client = None

    def connect(self):
        if not self.api_id or not self.api_hash:
            print("[TelegramAdapter] TELEGRAM_API_ID или TELEGRAM_API_HASH не настроены в .env.")
            return False
        
        try:
            from telethon import TelegramClient
            self.client = TelegramClient("dating_session", int(self.api_id), self.api_hash)
            self.client.start(phone=self.phone)
            print(f"[TelegramAdapter] Успешно подключен к Telegram для бота {self.bot_handle}")
            return True
        except Exception as e:
            print(f"[TelegramAdapter] Ошибка подключения: {e}")
            return False

    def fetch_next_profile(self) -> ProfileData:
        """
        В реальном цикле считывает последнее сообщение от @leomatchbot,
        скачивает фото в downloads/ и парсит текст.
        """
        # Заглушка/скелет для безопасного запуска
        print(f"[TelegramAdapter] Получение анкеты из {self.bot_handle}...")
        return ProfileData(
            platform="tg_leomatchbot",
            profile_id="tg_demo_101",
            name="Алина",
            age=22,
            city="Киев",
            bio="Люблю спонтанные поездки, кофе по вечерам и легких на подъем людей. Без духоты.",
            photo_paths=[],
            raw_text="Алина, 22, Киев - Люблю спонтанные поездки, кофе по вечерам и легких на подъем людей. Без духоты."
        )

    def like(self, profile: ProfileData):
        print(f"[TelegramAdapter] 👍 Ставим ЛАЙК (❤️) профилю {profile.name}...")
        time.sleep(1.5)

    def dislike(self, profile: ProfileData):
        print(f"[TelegramAdapter] 👎 Пропускаем (дизлайк) профиль {profile.name}...")
        time.sleep(1.2)
