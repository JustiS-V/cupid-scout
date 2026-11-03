import os
import json
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from core.models import ProfileData, EvaluationResult

DATA_DIR = Path(__file__).parent.parent / "data"
SCREENSHOTS_DIR = DATA_DIR / "screenshots"
MATCHES_DIR = DATA_DIR / "matches"
DB_PATH = DATA_DIR / "dating.db"
JSONL_PATH = DATA_DIR / "scanned_profiles.jsonl"

class StorageManager:
    """
    Менеджер базы данных и архива профилей:
    - Сохраняет историю сканирований в SQLite и JSONL
    - Архивирует скриншоты в data/screenshots/
    - Сохраняет карточки одобренных девушек в data/matches/
    """
    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        MATCHES_DIR.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT,
                    platform TEXT,
                    name TEXT,
                    age INTEGER,
                    city TEXT,
                    bio TEXT,
                    raw_text TEXT,
                    screenshot_path TEXT,
                    attractiveness_score REAL,
                    casual_intent_score REAL,
                    vibe_type TEXT,
                    is_match INTEGER,
                    action TEXT,
                    reason TEXT,
                    suggested_opener TEXT,
                    dossier_json TEXT
                )
            """)
            conn.commit()

    def save_scan(
        self,
        profile: ProfileData,
        eval_result: EvaluationResult,
        dossier: Optional[Any] = None
    ) -> str:
        """Сохраняет профиль в SQLite, JSONL и архивирует скриншот"""
        timestamp_str = datetime.now().isoformat()
        profile_id = profile.profile_id or f"card_{int(datetime.now().timestamp())}"
        action = "liked" if eval_result.is_match else "skipped"

        # 1. Сохранение скриншота в архив
        final_screenshot_path = ""
        if profile.photo_paths and os.path.exists(profile.photo_paths[0]):
            src_path = Path(profile.photo_paths[0])
            dest_name = f"{profile_id}_{src_path.name}"
            dest_path = SCREENSHOTS_DIR / dest_name
            shutil.copy2(src_path, dest_path)
            final_screenshot_path = str(dest_path)

        dossier_data = dossier.model_dump() if dossier and hasattr(dossier, "model_dump") else {}

        # 2. Запись в SQLite
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO profiles (
                    id, timestamp, platform, name, age, city, bio, raw_text,
                    screenshot_path, attractiveness_score, casual_intent_score,
                    vibe_type, is_match, action, reason, suggested_opener, dossier_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                profile_id,
                timestamp_str,
                profile.platform,
                profile.name,
                profile.age,
                profile.city,
                profile.bio,
                profile.raw_text,
                final_screenshot_path,
                eval_result.attractiveness_score,
                eval_result.casual_intent_score,
                eval_result.vibe_type,
                1 if eval_result.is_match else 0,
                action,
                eval_result.reason,
                eval_result.suggested_opener,
                json.dumps(dossier_data, ensure_ascii=False)
            ))
            conn.commit()

        # 3. Дозапись в JSONL (для быстрого сбора датасетов и анализа)
        record = {
            "id": profile_id,
            "timestamp": timestamp_str,
            "platform": profile.platform,
            "name": profile.name,
            "age": profile.age,
            "bio": profile.bio,
            "screenshot_path": final_screenshot_path,
            "attractiveness_score": eval_result.attractiveness_score,
            "casual_intent_score": eval_result.casual_intent_score,
            "vibe_type": eval_result.vibe_type,
            "action": action,
            "reason": eval_result.reason,
            "suggested_opener": eval_result.suggested_opener,
            "dossier": dossier_data
        }
        with open(JSONL_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        # 4. Если девушка ОДОБРЕНА (Match / Like):
        if eval_result.is_match:
            match_file = MATCHES_DIR / f"{profile_id}_{profile.name or 'girl'}.md"
            with open(match_file, "w", encoding="utf-8") as f:
                f.write(f"""# 🔥 Досье мэтча: {profile.name}, {profile.age or '?'}
- **Дата добавления:** {timestamp_str}
- **Платформа:** {profile.platform}
- **Оценка внешности:** {eval_result.attractiveness_score}/10
- **FWB / Casual Score:** {eval_result.casual_intent_score}/10
- **Вайб:** {eval_result.vibe_type}
- **Скриншот:** `{final_screenshot_path}`

## 📝 Био:
{profile.bio or 'Пусто'}

## 💡 Вердикт нейросети:
{eval_result.reason}

## 💬 Рекомендуемый оупенер:
> {eval_result.suggested_opener}
""")
                if final_screenshot_path and os.path.exists(final_screenshot_path):
                    shutil.copy2(final_screenshot_path, MATCHES_DIR / f"{profile_id}.jpg")

        return profile_id

    def get_stats(self) -> Dict[str, Any]:
        """Статистика сканирований"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*), SUM(CASE WHEN action='liked' THEN 1 ELSE 0 END), AVG(attractiveness_score) FROM profiles")
            row = cursor.fetchone()
            total = row[0] or 0
            liked = row[1] or 0
            avg_score = round(row[2] or 0.0, 2)
            return {"total": total, "liked": liked, "skipped": total - liked, "avg_attractiveness": avg_score}
