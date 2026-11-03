import json
import sqlite3
import time
from pathlib import Path

BASE_DIR = Path("/Users/val9/Desktop/Process/dating-ai-agent")
DB_PATH = BASE_DIR / "data" / "dating.db"
CHAT_LOGS_FILE = BASE_DIR / "data" / "chat_logs.jsonl"
PROPOSALS_MD = BASE_DIR / "data" / "chat_proposals.md"

PROFILES_DATA = [
    {
        "name": "Julia",
        "age": 24,
        "match_id": "681806443b495980ca094bc86ab6acd892bab379ac026561",
        "looking_for": "Нових друзів",
        "bio": "Возможно, Tinder всего лишь ещё одна форма эскапизма. Мы ведь все время от времени пытаемся сбежать от реальности...",
        "match_date": "1 день тому (Свежий)",
        "priority": "ТОП-1 (Идеально)",
        "casual_score": 8.5,
        "recommended_opener": "Julia, если Tinder — это эскапизм, то куда именно мы отсюда сбегаем: в уютную кофейню или сразу в бар? 😉",
        "playful_opener": "Привет! Твоя мысль про эскапизм зацепила. Вопрос только в том, удается ли тебе сбежать от реальности или реальность тебя всё-таки догоняет?",
        "why": "Свежий мэтч (вчера), умное био, отличный вайб для свидания в городе."
    },
    {
        "name": "Елена",
        "age": 35,
        "match_id": "681806443b495980ca094bc86a88df87e2cf08799d9d281f",
        "looking_for": "Несерйозні стосунки (чи ні…)",
        "bio": "Разбираюсь в макраме...",
        "match_date": "Взаимная пара",
        "priority": "ТОП-2 (Высокий шанс FWB)",
        "casual_score": 9.0,
        "recommended_opener": "Елена, привет! Макраме — это серьезный скилл. Сможешь связать разговор так, чтобы мы оба не запутались? 😉",
        "playful_opener": "Привет! Твой статус «несерьезные отношения (или нет…)» звучит как отличный повод спонтанно выбраться на бокал вина без лишних ожиданий.",
        "why": "Прямо указала несерьезные отношения, легкая самоирония в био."
    },
    {
        "name": "Марі",
        "age": 26,
        "match_id": "67fc09b7f12dcbfa7b5955ed681806443b495980ca094bc8",
        "looking_for": "Ще точно не знаю",
        "bio": "I’m normal, self-aware, creative, slow, do stand up, teach kids...",
        "match_date": "Взаимная пара",
        "priority": "ТОП-3 (Творческая / юмор)",
        "casual_score": 8.0,
        "recommended_opener": "Марі, привет! Стендап и преподавание детям — звучит как самый жесткий источник материала в мире 😄 Кто из них более требовательная публика?",
        "playful_opener": "Привет! «Normal, self-aware and do stand up» — звучит как оксюморон для комика) Какая лучшая шутка родилась у тебя на этой неделе?",
        "why": "Стендапер, творческая, обожает легкий интеллектуальный юмор."
    },
    {
        "name": "Anastasia",
        "age": 22,
        "match_id": "681806443b495980ca094bc86a464d37e44f0699edf5ce9e",
        "looking_for": "Нових друзів",
        "bio": "Idk what to say... just ask me if u wanna know smth🌿",
        "match_date": "Взаимная пара",
        "priority": "ТОП-4 (Открыта к общению)",
        "casual_score": 7.5,
        "recommended_opener": "Anastasia, ты написала «just ask», так что ловлю на слове: какое самое спонтанное решение ты принимала за последнее время? 🌿",
        "playful_opener": "Привет! Раз уж ты разрешила задавать вопросы: любимое место в городе, где можно скрыться от людей с чашкой кофе?",
        "why": "Короткое био с прямым призывом задавать вопросы."
    },
    {
        "name": "Jennifer",
        "age": 24,
        "match_id": "681806443b495980ca094bc86ad320dde99bce54bb945a14",
        "looking_for": "Ще точно не знаю",
        "bio": "Go conciertos, ferias, cine, expos, etc. Me gusta lo alt, la música clásica y el trashy pop.",
        "match_date": "1 тиждень тому",
        "priority": "Гео-далеко (12 000+ км, Перу)",
        "casual_score": 5.0,
        "recommended_opener": "¿Qué concierto o festival tienes más ganas de ver este mes?",
        "playful_opener": "¡Hola Jennifer! Tienes un gusto musical genial. ¿Cuál es tu canción favorita ahora mismo?",
        "why": "Испанский язык, находится далеко (Miraflores, 12600 км), только онлайн."
    },
    {
        "name": "Nikki",
        "age": 28,
        "match_id": "6796a2e3b6e1583d3dab2834681806443b495980ca094bc8",
        "looking_for": "Серйозні стосунки (чи ні…)",
        "bio": "Ищу погуляц + повайбить + шашлык-машлык... ❗ONS/FWB - BAN ❌30+,нормисы,маскулинные...",
        "match_date": "1 рік тому",
        "priority": "Низкий (Красные флаги, 1 год назад)",
        "casual_score": 3.0,
        "recommended_opener": "Привет! Как там цирк, набралась уже труппа или всё ещё в процессе? 🙂",
        "playful_opener": "Шашлык-машлык ещё актуален, или уровень треша в жизни уже превысил норму?)",
        "why": "Капс в био, запреты ONS/FWB, старый мэтч годичной давности."
    },
    {
        "name": "Саша",
        "age": 24,
        "match_id": "681806443b495980ca094bc868ab38b0aa9ff49ed6c0606d",
        "looking_for": "Нових друзів",
        "bio": "Looking for friends and fun (Одесса, транс-девушка)",
        "match_date": "1 рік тому",
        "priority": "Низкий (Одесса, 389 км, 1 год назад)",
        "casual_score": 4.0,
        "recommended_opener": "Привет! Как там Одесса дышит сейчас?)",
        "playful_opener": "Привет! Увидел D&D в интересах — за какой класс обычно играешь?",
        "why": "Другой город (389 км), старый мэтч."
    },
    {
        "name": "Maria",
        "age": 24,
        "match_id": "681806443b495980ca094bc869e296aa39c08300c9e4dfaf",
        "looking_for": "Довготривалі стосунки",
        "bio": "Stop feeding yourself that nonsense you’ve made up about me! I don’t go on dates. It’s just a job interview for sex...",
        "match_date": "1 тиждень тому",
        "priority": "Низкий (Токсичный фильтр в био)",
        "casual_score": 2.0,
        "recommended_opener": "Strong bio! Looks like bad Tinder dates did a number on your patience. Who hurt you so bad? 😄",
        "playful_opener": "«Job interview for sex» is a brutal description. What if it’s just two drinks and zero expectations?",
        "why": "Агрессивный манифест против свиданий в профиле."
    }
]

def save_proposals():
    md_lines = [
        "# 💌 Взаимные мэтчи Tinder и Готовые Оупенеры для Чата\n",
        f"> **Обновлено:** {time.strftime('%Y-%m-%d %H:%M:%S')} | **Всего мэтчей в базе:** {len(PROFILES_DATA)}\n",
        "Все оупенеры составлены с учетом психотипа, языка анкеты и цели быстрого выхода на свидание.\n\n---\n"
    ]

    for idx, p in enumerate(PROFILES_DATA, 1):
        # 1. Update SQLite
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE mutual_matches 
                SET updated_at = datetime('now')
                WHERE match_id = ?
            """, (p["match_id"],))
            conn.commit()

        # 2. Append to JSONL log
        with open(CHAT_LOGS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "event": "opener_ready",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "match_id": p["match_id"],
                "name": p["name"],
                "priority": p["priority"],
                "score": p["casual_score"],
                "recommended_opener": p["recommended_opener"],
                "playful_opener": p["playful_opener"]
            }, ensure_ascii=False) + "\n")

        # 3. MD card
        md_lines.append(f"## {idx}. {p['name']}, {p['age']} лет — **{p['priority']}**")
        md_lines.append(f"- **Ищет:** `{p['looking_for']}`")
        md_lines.append(f"- **Мэтч:** `{p['match_date']}`")
        md_lines.append(f"- **Шанс Casual/FWB:** `{p['casual_score']}/10` 🔥")
        md_lines.append(f"- **Прямая ссылка:** [Открыть диалог в Tinder](https://tinder.com/app/messages/{p['match_id']})")
        md_lines.append(f"- **О себе:** *\"{p['bio']}\"*\n")
        md_lines.append(f"### 💬 Готовые варианты для отправки:")
        md_lines.append(f"1. **Рекомендуемый оупенер:**\n   > `{p['recommended_opener']}`")
        md_lines.append(f"2. **Игривый / Альтернативный:**\n   > `{p['playful_opener']}`")
        md_lines.append(f"- **Анализ профиля:** _{p['why']}_\n")
        md_lines.append("---\n")

    with open(PROPOSALS_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print(f"✅ Готово! Сформировано досье на {len(PROFILES_DATA)} мэтчей.")
    print(f"📄 Файл: {PROPOSALS_MD}")

if __name__ == "__main__":
    save_proposals()
