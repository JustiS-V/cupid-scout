import json
import sqlite3
import datetime
from pathlib import Path
from typing import Dict, Any, Optional

BASE_DIR = Path("/Users/val9/Desktop/Process/dating-ai-agent")
DB_PATH = BASE_DIR / "data" / "dating.db"
QUOTA_STATUS_FILE = BASE_DIR / "data" / "quota_status.json"

class QuotaManager:
    """
    Управление суточными лимитами дейтинг-платформ:
    - Tinder Free: ~50-100 лайков в 24/12 часов (дизлайки БЕСКОНЕЧНЫ).
    - Badoo Free: ~50-80 лайков в сутки.
    - Bumble Free: ~40-50 лайков в сутки.
    - LeoMatchBot (Telegram): ~100 анкет в сутки.
    """
    def __init__(self):
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS platform_quotas (
                    platform TEXT PRIMARY KEY,
                    likes_today INTEGER DEFAULT 0,
                    skips_today INTEGER DEFAULT 0,
                    limit_reached INTEGER DEFAULT 0,
                    limit_hit_at TEXT,
                    cooldown_until TEXT,
                    timer_string TEXT,
                    last_updated TEXT
                )
            """)
            conn.commit()

    def get_stats_last_24h(self, platform: str = "tinder_web") -> Dict[str, Any]:
        """Возвращает статистику использования за последние 24 часа"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN action = 'liked' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN action = 'skipped' THEN 1 ELSE 0 END)
                FROM profiles
                WHERE platform = ? AND timestamp >= datetime('now', '-24 hours')
            """, (platform,))
            row = cursor.fetchone()
            likes = row[0] or 0
            skips = row[1] or 0

            cursor.execute("SELECT * FROM platform_quotas WHERE platform = ?", (platform,))
            q_row = cursor.fetchone()

        cooldown_until = None
        timer_str = None
        limit_reached = False
        if q_row:
            limit_reached = bool(q_row[3])
            cooldown_until = q_row[5]
            timer_str = q_row[6]

        can_swipe = True
        if limit_reached and cooldown_until:
            try:
                now = datetime.datetime.now()
                cd_time = datetime.datetime.fromisoformat(cooldown_until)
                if now < cd_time:
                    can_swipe = False
                else:
                    # Лимит сбросился
                    self.reset_limit(platform)
            except Exception:
                pass

        return {
            "platform": platform,
            "likes_24h": likes,
            "skips_24h": skips,
            "total_scanned_24h": likes + skips,
            "can_swipe": can_swipe,
            "limit_reached": limit_reached,
            "cooldown_until": cooldown_until,
            "timer_string": timer_str
        }

    def record_limit_hit(self, platform: str = "tinder_web", timer_string: Optional[str] = None):
        """Фиксирует исчерпание лимита и рассчитывает время восстановления"""
        now = datetime.datetime.now()
        # По умолчанию 12 часов, либо парсим таймер из модалки Tinder (e.g. 11:45:00)
        cooldown_hours = 12.0
        if timer_string:
            parts = timer_string.strip().split(":")
            if len(parts) == 3:
                try:
                    h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
                    cooldown_hours = h + m / 60.0 + s / 3600.0
                except Exception:
                    pass

        cooldown_until = (now + datetime.timedelta(hours=cooldown_hours)).isoformat()
        now_str = now.isoformat()

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO platform_quotas (
                    platform, limit_reached, limit_hit_at, cooldown_until, timer_string, last_updated
                ) VALUES (?, 1, ?, ?, ?, ?)
            """, (platform, now_str, cooldown_until, timer_string or f"{int(cooldown_hours)}:00:00", now_str))
            conn.commit()

        # Сохраняем JSON для быстрых виджетов
        data = {
            "platform": platform,
            "limit_hit_at": now_str,
            "cooldown_until": cooldown_until,
            "timer_string": timer_string,
            "can_swipe": False
        }
        with open(QUOTA_STATUS_FILE, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, indent=2, ensure_ascii=False))

        print(f"\n🛑 [QuotaManager] Лимит лайков на платформе {platform} исчерпан!")
        print(f"⏳ Таймер восстановления: {timer_string or f'{cooldown_hours} часов'}")
        print(f"⏰ Следующая доступная сессия: {cooldown_until}")

    def reset_limit(self, platform: str = "tinder_web"):
        """Сброс лимита после истечения таймера"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE platform_quotas 
                SET limit_reached = 0, cooldown_until = NULL, timer_string = NULL, last_updated = datetime('now')
                WHERE platform = ?
            """, (platform,))
            conn.commit()
        if QUOTA_STATUS_FILE.exists():
            try:
                QUOTA_STATUS_FILE.unlink()
            except Exception:
                pass

if __name__ == "__main__":
    qm = QuotaManager()
    stats = qm.get_stats_last_24h()
    print("Статистика лимитов за 24 часа:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))
