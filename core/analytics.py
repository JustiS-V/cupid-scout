import re
import json
import sqlite3
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

BASE_DIR = Path("/Users/val9/Desktop/Process/dating-ai-agent")
DB_PATH = BASE_DIR / "data" / "dating.db"
BEHAVIOR_LOGS_FILE = BASE_DIR / "data" / "behavioral_events.jsonl"
ANALYTICS_REPORT_MD = BASE_DIR / "data" / "behavioral_analysis_report.md"

EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags (iOS)
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "]+", flags=re.UNICODE
)

class BehavioralAnalyticsManager:
    """
    Модуль сбора, учета и глубокого анализа поведения девушек в чатах.
    Метрики:
    - Скорость ответа (response time в секундах/минутах)
    - Коэффициент вклада (Investment Ratio = объем ее сообщений / объем наших сообщений)
    - Взаимность вопросов (Reciprocity: задает ли она встречные вопросы)
    - Эмоциональный накал (эмодзи, знаки восклицания, длина фраз)
    - Поведенческий архетип и вероятность успешного выхода на свидание
    """
    def __init__(self):
        self._init_tables()

    def _init_tables(self):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_analytics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id TEXT,
                    turn_number INTEGER,
                    sender TEXT,
                    message_text TEXT,
                    sent_at TEXT,
                    response_time_seconds REAL DEFAULT NULL,
                    char_count INTEGER,
                    word_count INTEGER,
                    emoji_count INTEGER,
                    has_question INTEGER,
                    corrections_count INTEGER DEFAULT 0,
                    sentiment_score REAL DEFAULT 0.0,
                    interest_level_score REAL DEFAULT 5.0,
                    notes TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS behavioral_profiles (
                    match_id TEXT PRIMARY KEY,
                    name TEXT,
                    age INTEGER,
                    language TEXT,
                    total_turns INTEGER DEFAULT 0,
                    her_messages_count INTEGER DEFAULT 0,
                    my_messages_count INTEGER DEFAULT 0,
                    her_avg_response_time_min REAL DEFAULT NULL,
                    her_min_response_time_min REAL DEFAULT NULL,
                    her_max_response_time_min REAL DEFAULT NULL,
                    her_avg_char_length REAL DEFAULT 0.0,
                    investment_ratio REAL DEFAULT 0.0,
                    questions_asked_by_her INTEGER DEFAULT 0,
                    behavior_archetype TEXT DEFAULT 'Pending First Response',
                    conversion_stage TEXT DEFAULT 'opener_sent',
                    last_checked_at TEXT
                )
            """)
            conn.commit()

    def record_message(
        self,
        match_id: str,
        sender: str,
        message_text: str,
        sent_at: Optional[str] = None,
        corrections_count: int = 0,
        notes: str = ""
    ) -> Dict[str, Any]:
        """Записывает сообщение с расчетом времени ответа и психо-лингвистических метрик"""
        sent_at_str = sent_at or datetime.datetime.now().isoformat()
        char_count = len(message_text)
        word_count = len(message_text.split())
        emojis = EMOJI_PATTERN.findall(message_text)
        emoji_count = sum(len(e) for e in emojis)
        has_question = 1 if ("?" in message_text or "¿" in message_text) else 0

        # Вычисляем время ответа (разница между предыдущим сообщением другого автора)
        response_time_seconds = None
        turn_number = 1

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            # Находим последнее сообщение в этом диалоге
            cursor.execute("""
                SELECT sender, sent_at, turn_number 
                FROM chat_analytics 
                WHERE match_id = ? 
                ORDER BY id DESC LIMIT 1
            """, (match_id,))
            last_msg = cursor.fetchone()

            if last_msg:
                last_sender, last_time_str, last_turn = last_msg
                turn_number = (last_turn or 1) + 1
                if last_sender != sender and last_time_str:
                    try:
                        t1 = datetime.datetime.fromisoformat(last_time_str.replace("Z", ""))
                        t2 = datetime.datetime.fromisoformat(sent_at_str.replace("Z", ""))
                        response_time_seconds = max(0.0, (t2 - t1).total_seconds())
                    except Exception:
                        pass

            # Оценка базового интереса (1..10)
            interest = 5.0
            if sender == "her":
                if char_count > 50: interest += 1.5
                if has_question: interest += 2.0
                if emoji_count > 0: interest += 1.0
                if response_time_seconds and response_time_seconds < 600: # < 10 мин
                    interest += 1.5
                interest = min(10.0, interest)

            # Сохранение в БД
            cursor.execute("""
                INSERT INTO chat_analytics (
                    match_id, turn_number, sender, message_text, sent_at,
                    response_time_seconds, char_count, word_count, emoji_count,
                    has_question, corrections_count, sentiment_score, interest_level_score, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, ?, ?)
            """, (
                match_id, turn_number, sender, message_text, sent_at_str,
                response_time_seconds, char_count, word_count, emoji_count,
                has_question, corrections_count, interest, notes
            ))
            conn.commit()

        # Обновляем профиль поведения девушки
        self.update_behavioral_profile(match_id)

        # Пишем в лог JSONL
        event_data = {
            "event": "chat_message_recorded",
            "timestamp": sent_at_str,
            "match_id": match_id,
            "sender": sender,
            "text": message_text,
            "char_count": char_count,
            "response_time_sec": response_time_seconds,
            "response_time_min": round(response_time_seconds / 60.0, 1) if response_time_seconds else None,
            "has_question": bool(has_question),
            "emoji_count": emoji_count,
            "corrections_count": corrections_count
        }
        with open(BEHAVIOR_LOGS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(event_data, ensure_ascii=False) + "\n")

        return event_data

    def update_behavioral_profile(self, match_id: str):
        """Пересчитывает статистику поведения и определяет поведенческий архетип"""
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Получаем инфо о девушке
            cursor.execute("SELECT name, age FROM mutual_matches WHERE match_id = ?", (match_id,))
            match_row = cursor.fetchone()
            name = match_row["name"] if match_row else "Girl"
            age = match_row["age"] if match_row else None

            # Все сообщения диалога
            cursor.execute("SELECT * FROM chat_analytics WHERE match_id = ? ORDER BY id ASC", (match_id,))
            msgs = cursor.fetchall()

            if not msgs:
                return

            total_turns = len(msgs)
            my_msgs = [m for m in msgs if m["sender"] == "me"]
            her_msgs = [m for m in msgs if m["sender"] == "her"]

            my_chars_total = sum(m["char_count"] for m in my_msgs) or 1
            her_chars_total = sum(m["char_count"] for m in her_msgs)
            investment_ratio = round(her_chars_total / float(my_chars_total), 2)

            her_response_times = [m["response_time_seconds"] for m in her_msgs if m["response_time_seconds"] is not None]
            
            her_avg_rt = round((sum(her_response_times) / len(her_response_times)) / 60.0, 1) if her_response_times else None
            her_min_rt = round(min(her_response_times) / 60.0, 1) if her_response_times else None
            her_max_rt = round(max(her_response_times) / 60.0, 1) if her_response_times else None

            her_avg_len = round(her_chars_total / len(her_msgs), 1) if her_msgs else 0.0
            her_questions = sum(m["has_question"] for m in her_msgs)

            # Определение поведенческого архетипа
            archetype = "Ожидание первого ответа (Pending)"
            stage = "opener_sent"

            if len(her_msgs) > 0:
                stage = "chatting"
                if her_avg_rt and her_avg_rt <= 15 and investment_ratio >= 0.8:
                    archetype = "🔥 Горячий контакт (Fast & High Investment)"
                elif her_avg_rt and her_avg_rt <= 30:
                    archetype = "⚡ Быстрый ответ (Fast Responder)"
                elif her_questions > 0 and investment_ratio >= 0.7:
                    archetype = "💬 Взаимный интерес (Invested Reciprocal)"
                elif her_avg_len < 20 and her_questions == 0:
                    archetype = "🧊 Односложные ответы (Low Effort / Cold)"
                elif her_avg_rt and her_avg_rt > 360: # > 6 часов
                    archetype = "🐢 Медленный темп (Slow Burner)"
                else:
                    archetype = "⚖️ Умеренный интерес (Neutral Chat)"

            cursor.execute("""
                INSERT OR REPLACE INTO behavioral_profiles (
                    match_id, name, age, total_turns, her_messages_count, my_messages_count,
                    her_avg_response_time_min, her_min_response_time_min, her_max_response_time_min,
                    her_avg_char_length, investment_ratio, questions_asked_by_her,
                    behavior_archetype, conversion_stage, last_checked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                match_id, name, age, total_turns, len(her_msgs), len(my_msgs),
                her_avg_rt, her_min_rt, her_max_rt, her_avg_len, investment_ratio,
                her_questions, archetype, stage
            ))
            conn.commit()

    def generate_full_report(self) -> str:
        """Формирует расширенный Markdown отчет по анализу поведения"""
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT b.*, m.looking_for, m.bio
                FROM behavioral_profiles b
                LEFT JOIN mutual_matches m ON b.match_id = m.match_id
                ORDER BY b.her_messages_count DESC, b.last_checked_at DESC
            """)
            profiles = cursor.fetchall()

            cursor.execute("""
                SELECT match_id, sender, message_text, sent_at, response_time_seconds, corrections_count
                FROM chat_analytics
                ORDER BY id ASC
            """)
            history = cursor.fetchall()

        lines = [
            "# 📊 Глубокий Анализ Поведения Кандидаток в Чатах (Dating Analytics)\n",
            f"> **Дата генерации:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
            "Модуль отслеживает скорость ответа девушек, объем текста, коррекции, вопросы и рассчитывает вероятность свидания.\n\n---\n"
        ]

        lines.append("## 📈 Сводная таблица кандидаток:\n")
        lines.append("| Кандидатка | Статус диалога | Время ответа (ср.) | Коэф. вклада (IR) | Вопросы | Поведенческий Архетип |")
        lines.append("| :--- | :---: | :---: | :---: | :---: | :--- |")

        for p in profiles:
            rt_str = f"{p['her_avg_response_time_min']} мин" if p['her_avg_response_time_min'] is not None else "ждем ответ"
            lines.append(
                f"| **{p['name']} ({p['age'] or '?'})** | `{p['conversion_stage']}` | {rt_str} | "
                f"`{p['investment_ratio']:.2f}x` | {p['questions_asked_by_her']} | {p['behavior_archetype']} |"
            )

        lines.append("\n---\n## 🔍 Детальный разбор по каждому диалогу:\n")

        for p in profiles:
            m_id = p["match_id"]
            msgs = [h for h in history if h["match_id"] == m_id]
            lines.append(f"### 👤 {p['name']}, {p['age'] or '?'} лет")
            lines.append(f"- **Архетип:** `{p['behavior_archetype']}`")
            lines.append(f"- **Сообщений отправлено нами:** {p['my_messages_count']} | **Получено от нее:** {p['her_messages_count']}")
            if p['her_avg_response_time_min']:
                lines.append(f"- **Скорость ответа:** средняя `{p['her_avg_response_time_min']} мин` (мин: `{p['her_min_response_time_min']} мин`, макс: `{p['her_max_response_time_min']} мин`)")
            lines.append(f"- **Коэффициент вклада (Investment Ratio):** `{p['investment_ratio']}x` (отношение символов ее ответов к нашим)")
            lines.append("\n**История сообщений и метрики:**")
            
            for m in msgs:
                sender_label = "🧑‍💻 Мы" if m["sender"] == "me" else f"👩 {p['name']}"
                rt_label = f" (время на ответ: {round(m['response_time_seconds']/60.0, 1)} мин)" if m["response_time_seconds"] else ""
                corr_label = f" [исправлений: {m['corrections_count']}]" if m["corrections_count"] > 0 else ""
                lines.append(f"- **{sender_label}** [{m['sent_at']}]{rt_label}{corr_label}:\n  > *«{m['message_text']}»*")
            lines.append("\n---\n")

        report_content = "\n".join(lines)
        with open(ANALYTICS_REPORT_MD, "w", encoding="utf-8") as f:
            f.write(report_content)

        return report_content

def sync_sent_messages_to_analytics():
    """Синхронизирует уже отправленные сообщения из chat_messages в аналитическую систему"""
    mgr = BehavioralAnalyticsManager()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT match_id, sender, message_text, sent_at FROM chat_messages ORDER BY id ASC")
        rows = cursor.fetchall()
        
    for r in rows:
        match_id, sender, msg, sent_at = r
        # Проверяем, нет ли уже в analytics
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT id FROM chat_analytics WHERE match_id = ? AND message_text = ?", (match_id, msg))
            if not c.fetchone():
                mgr.record_message(
                    match_id=match_id,
                    sender=sender,
                    message_text=msg,
                    sent_at=sent_at,
                    corrections_count=1, # имитированное исправление опечатки при вводе
                    notes="Инициализировано из истории отправки"
                )
    print("✅ Синхронизация истории в аналитические таблицы завершена.")
    report = mgr.generate_full_report()
    print(f"📄 Отчет по поведению сформирован: {ANALYTICS_REPORT_MD}")

if __name__ == "__main__":
    sync_sent_messages_to_analytics()
