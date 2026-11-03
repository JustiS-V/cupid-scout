import os
import io
import json
import base64
from pathlib import Path
from typing import Optional, List
from core.models import ProfileData, EvaluationResult
from core.vision_client import MediaNodeVisionClient, VisionError

SYSTEM_PROMPT = """
Ты — ассистент персонального вкуса и дейтинг-скаут.
Твоя цель: отбирать привлекательных девушек для кэжуал-знакомств, приятного флирта, ONS (one-night stand) или FWB (friends with benefits).

Пользователь ценит:
- Внешность: привлекательное лицо, естественность, ухоженность, фигура, женственность, открытый вайб.
- Цели: готовность к спонтанным встречам, легкость на подъем, отсутствие духоты и завышенных требований.

Стоп-факторы (Red Flags):
- Нет лица (мемы, коты, пейзажи, групповые фото 5 человек).
- Дикий фотошоп/маски, скрывающие внешность.
- В био: "Ищу мужа", "Никакого секса", "Для серьезных отношений", реклама инсты/тг @... (сбор подписчиков).

Верни СТРОГО валидный JSON:
{
  "has_real_person": true,
  "face_visible": true,
  "attractiveness_score": 8.5,
  "vibe_type": "casual_party",
  "casual_intent_score": 8.0,
  "is_match": true,
  "red_flags": [],
  "green_flags": ["симпатичная улыбка", "легкое био"],
  "reason": "Красивая девушка, ищет приятное времяпровождение без духоты.",
  "suggested_opener": "Оригинальный и легкий оупенер под детали ее фото или био"
}
"""

class ProfileScorer:
    """
    Универсальный оценщик анкет с переключателем провайдеров:
    - 'worker_lms' / 'local_lms': LM Studio (на воркере или на Mac)
    - 'gemini': Google Gemini 2.5 Flash
    - 'openai': OpenAI ChatGPT (GPT-4o / GPT-4o-mini)
    - 'ollama': локальный Ollama
    """
    def __init__(self, min_attractiveness: float = 7.0, min_intent: float = 6.0):
        self.min_attractiveness = min_attractiveness
        self.min_intent = min_intent
        self.provider = os.getenv("LLM_PROVIDER", "worker_lms").lower()
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.media_client = MediaNodeVisionClient()

    def _call_gemini(self, profile: ProfileData) -> EvaluationResult:
        import google.generativeai as genai
        genai.configure(api_key=self.gemini_key)
        model = genai.GenerativeModel("gemini-2.5-flash")

        user_prompt = f"{SYSTEM_PROMPT}\n\nАнкета: Имя {profile.name}, Возраст {profile.age}, Город {profile.city}\nБио: {profile.bio}"
        contents = [user_prompt]
        for path_str in profile.photo_paths:
            path = Path(path_str)
            if path.exists():
                with open(path, "rb") as f:
                    contents.append({"mime_type": "image/jpeg", "data": f.read()})

        resp = model.generate_content(contents)
        raw_text = resp.text.strip()
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_text:
            raw_text = raw_text.split("```")[1].split("```")[0].strip()
        data = json.loads(raw_text)
        data["reason"] = f"{data.get('reason', '')} (Провайдер: Gemini Flash)"
        return EvaluationResult(**data)

    def _call_openai(self, profile: ProfileData) -> EvaluationResult:
        from openai import OpenAI
        client = OpenAI(api_key=self.openai_key)
        
        user_content = [{"type": "text", "text": f"Имя: {profile.name}, Возраст: {profile.age}\nБио: {profile.bio}"}]
        for path_str in profile.photo_paths:
            path = Path(path_str)
            if path.exists():
                with open(path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                user_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        data = json.loads(resp.choices[0].message.content)
        data["reason"] = f"{data.get('reason', '')} (Провайдер: OpenAI)"
        return EvaluationResult(**data)

    def evaluate(self, profile: ProfileData) -> EvaluationResult:
        # 1. Провайдер Gemini
        if self.provider == "gemini" and self.gemini_key:
            try:
                return self._call_gemini(profile)
            except Exception as e:
                print(f"[Scorer] Ошибка вызова Gemini: {e}")

        # 2. Провайдер OpenAI (ChatGPT)
        if self.provider in ["openai", "chatgpt"] and self.openai_key:
            try:
                return self._call_openai(profile)
            except Exception as e:
                print(f"[Scorer] Ошибка вызова OpenAI: {e}")

        # 3. Провайдер по умолчанию: LM Studio (Воркер через туннель или локальный Mac)
        try:
            raw_eval = self.media_client.inspect_profile(
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
            print(f"[Scorer] LM Studio не ответил: {e}")

        # Fallback на случай отсутствия любого сервера
        return EvaluationResult(
            has_real_person=True,
            face_visible=True,
            attractiveness_score=7.8,
            vibe_type="casual_party",
            casual_intent_score=7.5,
            is_match=True,
            red_flags=[],
            green_flags=["Живые фото", "Вайбовое био"],
            reason="Тестовый режим (сервер недоступен)",
            suggested_opener="Привет! Классный вайб на фото, за спонтанный кофе сегодня?"
        )
