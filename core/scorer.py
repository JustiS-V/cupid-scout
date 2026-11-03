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

class ProfileScorer:
    def __init__(self, min_attractiveness: float = 7.0, min_intent: float = 6.0):
        self.min_attractiveness = min_attractiveness
        self.min_intent = min_intent
        self.use_local_lms = os.getenv("USE_LOCAL_LM_STUDIO", "true").lower() in ["true", "1", "yes"]
        self.lms_base_url = os.getenv("LM_STUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
        self.lms_model = os.getenv("LM_STUDIO_MODEL", "default")
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")

    def _call_lm_studio(self, profile: ProfileData, prompt: str) -> EvaluationResult:
        """Вызов локального LM Studio через OpenAI-совместимый эндпоинт"""
        import requests
        headers = {"Content-Type": "application/json"}
        
        # Собираем мультимодальный контент
        messages_content = [{"type": "text", "text": prompt}]
        
        for path_str in profile.photo_paths:
            path = Path(path_str)
            if path.exists() and path.is_file():
                with open(path, "rb") as f:
                    b64_img = base64.b64encode(f.read()).decode("utf-8")
                mime = "image/jpeg" if path.suffix.lower() in [".jpg", ".jpeg"] else "image/png"
                messages_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64_img}"}
                })

        payload = {
            "model": self.lms_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": messages_content if len(messages_content) > 1 else prompt}
            ],
            "temperature": 0.4
        }

        resp = requests.post(f"{self.lms_base_url}/chat/completions", json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        raw_text = resp.json()["choices"][0]["message"]["content"].strip()
        
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_text:
            raw_text = raw_text.split("```")[1].split("```")[0].strip()

        data = json.loads(raw_text)
        res = EvaluationResult(**data)
        if res.attractiveness_score < self.min_attractiveness or res.casual_intent_score < self.min_intent:
            res.is_match = False
        return res

    def _call_gemini(self, profile: ProfileData, prompt: str) -> EvaluationResult:
        import google.generativeai as genai
        genai.configure(api_key=self.gemini_key)
        model = genai.GenerativeModel("gemini-2.5-flash")

        contents = [prompt]
        for path_str in profile.photo_paths:
            path = Path(path_str)
            if path.exists() and path.is_file():
                with open(path, "rb") as f:
                    image_bytes = f.read()
                mime = "image/jpeg" if path.suffix.lower() in [".jpg", ".jpeg"] else "image/png"
                contents.append({"mime_type": mime, "data": image_bytes})

        response = model.generate_content(contents)
        raw_text = response.text.strip()
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_text:
            raw_text = raw_text.split("```")[1].split("```")[0].strip()

        data = json.loads(raw_text)
        res = EvaluationResult(**data)
        # Apply strict threshold check
        if res.attractiveness_score < self.min_attractiveness or res.casual_intent_score < self.min_intent:
            res.is_match = False
        return res

    def evaluate(self, profile: ProfileData) -> EvaluationResult:
        user_prompt = f"""
{SYSTEM_PROMPT}

Данные анкеты:
Имя: {profile.name}
Возраст: {profile.age}
Город: {profile.city}
Текст био: {profile.bio}
Дополнительный текст: {profile.raw_text}
Количество фото: {len(profile.photo_paths)}
"""
        if self.use_local_lms:
            try:
                return self._call_lm_studio(profile, user_prompt)
            except Exception as e:
                print(f"[Scorer] Локальный LM Studio ({self.lms_base_url}) не ответил: {e}")

        if self.gemini_key:
            try:
                return self._call_gemini(profile, user_prompt)
            except Exception as e:
                print(f"[Scorer] Ошибка вызова Gemini API: {e}")

        # Fallback dummy for testing without API keys
        return EvaluationResult(
            has_real_person=True,
            face_visible=True,
            attractiveness_score=7.5,
            vibe_type="casual",
            casual_intent_score=7.0,
            is_match=True,
            red_flags=[],
            green_flags=["Тестовый профиль"],
            reason="Тестовый режим (укажите GEMINI_API_KEY в .env для реального VLM-анализа)",
            suggested_opener="Привет! Классный вайб на фото, за спонтанный кофе сегодня?"
        )
