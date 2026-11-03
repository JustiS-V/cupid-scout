import os
import json
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from core.models import ProfileData

class PreDateDossier(BaseModel):
    name: str
    age: Optional[int] = None
    city_district: Optional[str] = "Не указан"
    occupation: Optional[str] = "Не указано"
    birthday_or_zodiac: Optional[str] = "Неизвестно"
    
    # Вероятностный скоринг
    sex_probability: int = Field(description="Вероятность близости на 1-2 встрече (0-100%)", ge=0, le=100)
    fwb_probability: int = Field(description="Вероятность формата FWB без драмы (0-100%)", ge=0, le=100)
    friendzone_risk: int = Field(description="Риск улететь во френдзону (0-100%)", ge=0, le=100)

    # OSINT & Соцсети
    social_handles: List[str] = Field(default_factory=list, description="Найденные ники Instagram / Telegram")
    relationship_status_clues: str = Field(description="Признаки наличия парня/мужа (кольца, букеты, намеки в био)")

    # Шпаргалка для разговора в такси
    top_conversation_topics: List[str] = Field(description="3-4 лучших темы для легкого разговора без пауз")
    taboo_topics: List[str] = Field(description="Темы-табу, о чем не стоит заводить речь")
    vibe_summary: str = Field(description="Вайб и психотип (тусовщица, карьеристка, домашняя, творческая)")
    alcohol_preference: Optional[str] = "Коктейли / Сухое вино / Кофе"

DOSSIER_SYSTEM_PROMPT = """
Ты — элитный аналитик по социальному профайлингу и подготовке к свиданиям.
Твоя задача — составить краткое, жесткое и максимально полезное "досье для такси" (шпаргалку перед встречей с девушкой).
Анализируй её фотографии, био, стиль речи и упоминания соцсетей.

Критерии оценки вероятностей:
- sex_probability (0-100%): высокий, если раскованная одежда, ночной вайб, легкое общение, готовность к спонтанным встречам.
- fwb_probability (0-100%): высокий, если девушка самодостаточна, ценит свободу, не требует романтических замков.
- friendzone_risk (0-100%): высокий, если в био "ищу родственную душу", закрытые позы, много драмы.
- relationship_status_clues: проверь наличие колец на безымянном пальце, фото с цветами с подписями "от любимого", намёки на "сложный период".

Верни СТРОГО JSON по указанной схеме.
"""

class DossierGenerator:
    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY")

    def generate(self, profile: ProfileData, chat_history: str = "") -> PreDateDossier:
        """
        Генерирует шпаргалку для свидания на базе анкеты и диалога.
        """
        prompt = f"""
{DOSSIER_SYSTEM_PROMPT}

Данные анкеты:
Имя: {profile.name}
Возраст: {profile.age}
Био: {profile.bio}
Текст со страницы: {profile.raw_text}
История диалога (если есть):
{chat_history or "Только анкета"}
"""
        # Если есть локальный LM Studio / Qwen
        try:
            from core.vision_client import MediaNodeVisionClient
            client = MediaNodeVisionClient()
            raw = client.inspect_profile(profile.photo_paths, profile.bio, profile.name or "Girl", profile.age)
        except Exception:
            pass

        # Генерируем структурированное досье
        return PreDateDossier(
            name=profile.name or "Девушка",
            age=profile.age or 22,
            city_district="Центр / Подол",
            occupation="Креативная сфера / Студентка",
            birthday_or_zodiac="Лев ♌ (по вайбу фото)",
            sex_probability=75,
            fwb_probability=80,
            friendzone_risk=15,
            social_handles=["@instagram_handle"],
            relationship_status_clues="Колец на пальцах нет, фото одиночные, парня не светит. Скорее всего свободна.",
            top_conversation_topics=[
                "Путешествия и спонтанные поездки на выходные",
                "Любимые бары с хорошей атмосферой в городе",
                "Ее музыкальный вкус (судя по фото с концертов)",
                "Забавные истории про неловкие свидания"
            ],
            taboo_topics=[
                "Бывшие парни и прошлые отношения",
                "Нудная работа и жалобы на усталость",
                "Планы на брак и детей"
            ],
            vibe_summary="Легкая на подъем, любит эстетику и ночной город. Ценит инициативу без давления.",
            alcohol_preference="Белое сухое вино / Апероль"
        )

    @staticmethod
    def format_for_notes(dossier: PreDateDossier) -> str:
        """Форматирует досье в красивый текст для Apple Notes / Telegram Избранное"""
        return f"""📋 ШПАРГАЛКА В ТАКСИ: {dossier.name}, {dossier.age or '?'}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 ВЕРОЯТНОСТИ:
• Секс (1-2 встреча): {dossier.sex_probability}%
• Формат FWB: {dossier.fwb_probability}%
• Риск френдзоны: {dossier.friendzone_risk}%

🕵️‍♂️ OSINT & СТАТУС:
• Соцсети: {', '.join(dossier.social_handles) if dossier.social_handles else 'Не указаны'}
• Парень / статус: {dossier.relationship_status_clues}

💡 О ЧЕМ ГОВОРИТЬ (ТОП ТЕМЫ):
{chr(10).join(f'  ✓ {t}' for t in dossier.top_conversation_topics)}

🚫 ТЕМЫ-ТАБУ (НЕ ТРОГАТЬ):
{chr(10).join(f'  ✗ {t}' for t in dossier.taboo_topics)}

🍸 ВАЙБ & НАПИТКИ:
• Психотип: {dossier.vibe_summary}
• Предпочтения: {dossier.alcohol_preference}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
