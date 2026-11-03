import os
import time
import json
import sqlite3
import urllib.request
from pathlib import Path
from typing import Dict, Any, List

BASE_DIR = Path("/Users/val9/Desktop/Process/dating-ai-agent")
DB_PATH = BASE_DIR / "data" / "dating.db"
CHAT_LOGS_FILE = BASE_DIR / "data" / "chat_logs.jsonl"
PROPOSALS_MD = BASE_DIR / "data" / "chat_proposals.md"
WORKER_API_URL = os.getenv("LM_STUDIO_URL", "http://127.0.0.1:1234/v1/chat/completions")

SYSTEM_PROMPT = """Ты — топовый харизматичный Wingman и дейт-ассистент.
Твоя задача — составить идеальное первое сообщение (оупенер) девушке в Tinder на основе ее анкеты.

ПРАВИЛА:
1. НИКАКИХ шаблонных банальностей: никаких "Привет, как дела?", "Красивая улыбка", "Познакомимся?".
2. Цепляйся за конкретные детали из ее био, интересов или фото.
3. Стиль: легкий, уверенный, с легкой самоиронией или игривым вызовом, открывающий тему для диалога.
4. Цель общения: приятная встреча / кофе / бар / спонтанный вайб (casual/FWB без пошлости 'в лоб').
5. ЯЗЫК: Пиши строго на том языке, на котором заполнено ее био! (Если украинский — пиши на украинском; если русский — на русском; если английский/испанский — на нем).
6. Длина: 1-2 коротких предложения, завершающихся вопросом-крючком.

ФОРМАТ ОТВЕТА (строго JSON):
{
  "language": "ua/ru/en/es",
  "recommended_opener": "Твой лучший вариант сообщения",
  "playful_opener": "Более дерзкий/игривый альтернативный вариант",
  "casual_score": 8.5,
  "conversation_topics": ["тема 1", "тема 2"],
  "why": "Краткое объяснение логики захода"
}
"""

class ChatGenerator:
    def __init__(self, api_url: str = WORKER_API_URL):
        self.api_url = api_url

    def generate_opener(self, name: str, age: int, looking_for: str, bio: str) -> Dict[str, Any]:
        """Обращается к LLM на воркере для генерации персонализированных оупенеров"""
        user_prompt = f"""Девушка из Tinder:
- Имя: {name}
- Возраст: {age or 'не указан'}
- Что ищет в Tinder: {looking_for or 'не указано'}
- Текст ее профиля (Bio):
\"\"\"{bio or 'Био не заполнено, есть только фото'}\"\"\"

Сгенерируй JSON с оупенерами по инструкции."""

        payload = {
            "model": "media-vision",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }

        try:
            req = urllib.request.Request(
                self.api_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=80) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                content = res_data["choices"][0]["message"]["content"]
                
                # Извлекаем JSON
                start = content.find("{")
                end = content.rfind("}") + 1
                if start != -1 and end != 0:
                    return json.loads(content[start:end])
                else:
                    return {
                        "recommended_opener": content.strip(),
                        "playful_opener": "",
                        "casual_score": 7.0,
                        "conversation_topics": [],
                        "why": "Прямой ответ модели"
                    }
        except Exception as e:
            print(f"Ошибка LLM генератора ({e}), используем умный фоллбек...")
            # Эвристический фоллбек в зависимости от био
            if "музык" in bio.lower() or "music" in bio.lower() or "conciertos" in bio.lower():
                return {
                    "language": "es" if "conciertos" in bio.lower() else "ru",
                    "recommended_opener": "На какой концерт или фест сейчас больше всего хочешь попасть?",
                    "playful_opener": "Судя по профилю, у тебя отличный вкус на музыку — поделись треком недели?",
                    "casual_score": 7.5,
                    "conversation_topics": ["Музыка", "Концерты"],
                    "why": "Зацепка за музыкальные интересы"
                }
            return {
                "language": "ru",
                "recommended_opener": f"{name}, привет! Твой профиль сразу выделился. Чем обычно спасаешься от осенней рутины?",
                "playful_opener": f"{name}, у тебя вайб человека с интересными историями. Какое самое спонтанное решение было за последнее время?",
                "casual_score": 7.0,
                "conversation_topics": ["Спонтанность", "Город"],
                "why": "Базовый харизматичный заход"
            }

    def process_all_matches(self):
        """Проходит по всем mutual matches в БД и генерирует для них готовые сообщения"""
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM mutual_matches ORDER BY updated_at DESC")
            matches = cursor.fetchall()

        if not matches:
            print("В базе пока нет взаимных мэтчей. Запустите сначала scan_matches.py")
            return []

        proposals = []
        md_lines = ["# 💌 Каталог взаимных мэтчей и готовые оупенеры Tinder\n"]
        md_lines.append(f"> Сгенерировано: {time.strftime('%Y-%m-%d %H:%M:%S')} через 12-ядерный воркер LM Studio\n\n---\n")

        print(f"Генерация сообщений для {len(matches)} мэтчей...")
        for idx, m in enumerate(matches, 1):
            name = m["name"] or "Girl"
            age = m["age"]
            looking_for = m["looking_for"] or ""
            bio = m["bio"] or ""
            match_id = m["match_id"]

            print(f"[{idx}/{len(matches)}] Генерация для {name} ({age or '?'})...")
            plan = self.generate_opener(name, age, looking_for, bio)

            # Сохраняем в лог
            log_entry = {
                "event": "opener_generated",
                "match_id": match_id,
                "name": name,
                "age": age,
                "opener": plan.get("recommended_opener"),
                "playful": plan.get("playful_opener"),
                "topics": plan.get("conversation_topics"),
                "why": plan.get("why"),
                "score": plan.get("casual_score")
            }
            with open(CHAT_LOGS_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

            proposals.append(log_entry)

            # Формируем Markdown карточку
            md_lines.append(f"## {idx}. {name}, {age or '?'} лет")
            md_lines.append(f"- **Ищет:** `{looking_for or 'Не указано'}`")
            md_lines.append(f"- **Ссылка на диалог:** [Открыть чат в Tinder](https://tinder.com{m['profile_url'] if m['profile_url'].startswith('/') else '/' + m['profile_url']})")
            if m["screenshot_path"]:
                md_lines.append(f"- **Скриншот карточки:** `{m['screenshot_path']}`")
            md_lines.append(f"- **О себе:** *\"{bio}\"*\n")
            md_lines.append(f"### 💬 Варианты первого сообщения:")
            md_lines.append(f"1. **Основной оупенер (Рекомендуется):**\n   > `{plan.get('recommended_opener')}`")
            if plan.get("playful_opener"):
                md_lines.append(f"2. **Игривый / Дерзкий вариант:**\n   > `{plan.get('playful_opener')}`")
            md_lines.append(f"- **Оценка шансов на casual/FWB:** `{plan.get('casual_score', 7.0)}/10`")
            md_lines.append(f"- **Логика захода:** _{plan.get('why', '')}_\n")
            md_lines.append("---\n")

        with open(PROPOSALS_MD, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))

        print(f"\n🎉 Все оупенеры успешно сгенерированы и сохранены в:\n📄 {PROPOSALS_MD}")
        print(f"📝 Логи событий записаны в {CHAT_LOGS_FILE}")
        return proposals

if __name__ == "__main__":
    generator = ChatGenerator()
    generator.process_all_matches()
