import os
import json
import base64
from pathlib import Path
from typing import Optional
from core.models import ProfileData, EvaluationResult

SYSTEM_PROMPT = """
Ты — ассистент персонального вкуса и дейтинг-скаут.
Твоя цель: отбирать привлекательных девушек для кэжуал-знакомств, приятного флирта, ONS (one-night stand) или FWB (friends with benefits).

Пользователь ценит:
- Внешность: привлекательное лицо, естественность, ухоженность, фигура, женственность, открытый вайб.
- Цели: готовность к спонтанным встречам, легкость на подъем, отсутствие духоты и требований.

Стоп-факторы (Red Flags):
- Нет лица (мемы, коты, пейзажи, групповые фото 5 человек).
- Дикий фотошоп/маски из Снапчата, скрывающие внешность.
- В био: "Ищу мужа", "Никакого секса", "Для серьезных отношений", "Редко тут бываю, пиши в инст @..." (сбор подписчиков), коммерция/эскорт.

Верни СТРОГО валидный JSON соответствующий структуре:
{
  "has_real_person": true,
  "face_visible": true,
  "attractiveness_score": 8.5,
  "vibe_type": "casual_party",
  "casual_intent_score": 8.0,
  "is_match": true,
  "red_flags": [],
  "green_flags": ["симпатичная улыбка", "в био указано 'за спонтанный движ'"],
  "reason": "Красивая девушка, ищет приятное времяпровождение без духоты.",
  "suggested_opener": "Твой оригинальный и легкий оупенер под детали ее фото или био"
}
"""

from pathlib import Path
from typing import Optional
from core.models import ProfileData, EvaluationResult
from core.vision_client import MediaNodeVisionClient, VisionError

class ProfileScorer:
    """
    Оценщик анкет на базе локальной Vision-модели (LM Studio / Ollama),
    сохраняющий контракт проекта media_node.
    """
    def __init__(self, min_attractiveness: float = 7.0, min_intent: float = 6.0):
        self.min_attractiveness = min_attractiveness
        self.min_intent = min_intent
        self.client = MediaNodeVisionClient()
        self.gemini_key = os.getenv("GEMINI_API_KEY")

    def evaluate(self, profile: ProfileData) -> EvaluationResult:
        # Пробуем локальный сервер в стиле media_node
        try:
            raw_eval = self.client.inspect_profile(
                image_paths=profile.photo_paths,
                bio=profile.bio or profile.raw_text or "",
                name=profile.name or "Unknown",
                age=profile.age
            )

            attractiveness = float(raw_eval.get("attractiveness_score", 0.0))
            intent = float(raw_eval.get("casual_intent_score", 0.0))
            is_match = raw_eval.get("is_match", False) and (attractiveness >= self.min_attractiveness) and (intent >= self.min_intent)

            return EvaluationResult(
                has_real_person=raw_eval.get("has_real_person", True),
                face_visible=raw_eval.get("face_visible", True),
                attractiveness_score=attractiveness,
                vibe_type=raw_eval.get("vibe_type", "casual"),
                casual_intent_score=intent,
                is_match=is_match,
                red_flags=[],
                green_flags=[],
                reason=f"{raw_eval.get('reason', '')} (Модель: {raw_eval.get('model')}, {raw_eval.get('elapsed_seconds')}s)",
                suggested_opener=raw_eval.get("suggested_opener", "Привет! Классный вайб на фото, как проходит вечер?")
            )
        except Exception as e:
            print(f"[Scorer] Локальный Vision-клиент (media_node) не сработал: {e}")

        # Облачный fallback (Gemini) если задан ключ
        if self.gemini_key:
            try:
                return self._call_gemini(profile, f"Оцени анкету: {profile.name}, {profile.age}, {profile.bio}")
            except Exception as e:
                print(f"[Scorer] Ошибка вызова Gemini API: {e}")

        # Демо-заглушка для отладки
        return EvaluationResult(
            has_real_person=True,
            face_visible=True,
            attractiveness_score=7.8,
            vibe_type="casual_party",
            casual_intent_score=7.5,
            is_match=True,
            red_flags=[],
            green_flags=["Живые фото", "Вайбовое био"],
            reason="Тестовый режим (LM Studio сервер не запущен; запустите: lms server start)",
            suggested_opener="Привет! Классный вайб на фото, за спонтанный кофе сегодня?"
        )
