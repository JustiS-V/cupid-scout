import os
import re
import json
import sqlite3
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

BASE_DIR = Path("/Users/val9/Desktop/Process/dating-ai-agent")
DB_PATH = BASE_DIR / "data" / "dating.db"
CONFIG_PATH = BASE_DIR / "social_growth_config.json"
REPORT_PATH = BASE_DIR / "data" / "social_growth_report.md"

# Регулярные выражения для поиска ников и соцсетей в анкетах и чатах
HANDLE_PATTERNS = {
    "instagram": re.compile(
        r"(?:instagram\.com/|inst(?:a)?(?::|\s+)|ig(?::|\s+)|инст(?:а)?(?::|\s+))@?([a-zA-Z0-9_\.]{3,30})|@([a-zA-Z0-9_\.]{3,30})(?=\s*(?:инст|inst|ig))",
        re.I
    ),
    "telegram": re.compile(
        r"(?:t\.me/|tg(?::|\s+)|теле(?:га|грам)?(?::|\s+))@?([a-zA-Z0-9_]{4,32})|@([a-zA-Z0-9_]{4,32})(?=\s*(?:тг|tg|теле))",
        re.I
    ),
    "threads": re.compile(
        r"(?:threads\.net/@|тредс(?::|\s+)|threads(?::|\s+))@?([a-zA-Z0-9_\.]{3,30})",
        re.I
    ),
    "tiktok": re.compile(
        r"(?:tiktok\.com/@|тт(?::|\s+)|тикток(?::|\s+)|tt(?::|\s+))@?([a-zA-Z0-9_\.]{3,30})",
        re.I
    ),
    "generic_handle": re.compile(r"(?<!\w)@([a-zA-Z0-9_\.]{3,28})(?!\w)")
}

class SocialFunnelManager:
    """
    Модуль органического перелива аудитории и развития личных соцсетей
    (Instagram, Threads, TikTok, Telegram) через платформы знакомств.
    """
    def __init__(self):
        self.config = self._load_config()
        self._init_db()

    def _load_config(self) -> Dict[str, Any]:
        if not CONFIG_PATH.exists():
            return {}
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def _init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            # Таблица собранных соцсетей девушек (Leads)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS social_leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id TEXT,
                    candidate_name TEXT,
                    age INTEGER,
                    network TEXT,
                    handle TEXT,
                    profile_url TEXT,
                    source TEXT,
                    status TEXT DEFAULT 'discovered',
                    discovered_at TEXT,
                    notes TEXT
                )
            """)
            # Таблица попыток перевода в соцсети (Transitions)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS social_transitions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id TEXT,
                    candidate_name TEXT,
                    network TEXT,
                    offered_handle TEXT,
                    message_sent TEXT,
                    turn_number INTEGER,
                    status TEXT DEFAULT 'offered',
                    created_at TEXT
                )
            """)
            conn.commit()

    def extract_handles(self, text: str) -> List[Dict[str, str]]:
        """Извлекает ники и ссылки на соцсети из любого текста анкеты или сообщения"""
        if not text:
            return []
        
        found = []
        seen = set()

        for net, pattern in HANDLE_PATTERNS.items():
            if net == "generic_handle":
                continue
            for match in pattern.finditer(text):
                handle = match.group(1) or match.group(2) if match.lastindex and match.lastindex >= 2 else match.group(1)
                if handle and handle.lower() not in seen:
                    cleaned = handle.strip().lstrip("@")
                    seen.add(cleaned.lower())
                    url = self._format_profile_url(net, cleaned)
                    found.append({
                        "network": net,
                        "handle": f"@{cleaned}",
                        "profile_url": url
                    })

        # Если специфические не нашли, смотрим generic @username
        if not found:
            for match in HANDLE_PATTERNS["generic_handle"].finditer(text):
                raw_handle = match.group(1).strip()
                # Исключаем служебные слова
                if raw_handle.lower() not in ["gmail", "com", "tinder", "app", "instagram", "telegram"]:
                    seen.add(raw_handle.lower())
                    found.append({
                        "network": "instagram", # по умолчанию в тиндере @ обозначает инсту
                        "handle": f"@{raw_handle}",
                        "profile_url": f"https://instagram.com/{raw_handle}"
                    })

        return found

    def _format_profile_url(self, network: str, handle: str) -> str:
        clean = handle.lstrip("@")
        if network == "instagram":
            return f"https://instagram.com/{clean}"
        elif network == "telegram":
            return f"https://t.me/{clean}"
        elif network == "threads":
            return f"https://threads.net/@{clean}"
        elif network == "tiktok":
            return f"https://tiktok.com/@{clean}"
        return clean

    def record_lead(
        self,
        match_id: str,
        name: str,
        age: Optional[int],
        network: str,
        handle: str,
        source: str = "chat_message",
        notes: str = ""
    ) -> bool:
        """Сохраняет найденный контакт девушки в базу лидов"""
        url = self._format_profile_url(network, handle)
        now_str = datetime.datetime.now().isoformat()
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            # Проверяем уникальность
            cursor.execute("SELECT id FROM social_leads WHERE network = ? AND handle = ?", (network, handle))
            if cursor.fetchone():
                return False
            cursor.execute("""
                INSERT INTO social_leads (
                    match_id, candidate_name, age, network, handle, profile_url, source, status, discovered_at, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'discovered', ?, ?)
            """, (match_id, name, age, network, handle, url, source, now_str, notes))
            conn.commit()
        return True

    def scan_existing_profiles_for_leads(self) -> int:
        """Сканирует все сохраненные анкеты в базе и извлекает контакты"""
        added = 0
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, age, bio, raw_text FROM profiles")
            profiles = cursor.fetchall()

        for p in profiles:
            text = f"{p['bio'] or ''} {p['raw_text'] or ''}"
            leads = self.extract_handles(text)
            for item in leads:
                ok = self.record_lead(
                    match_id=p["id"],
                    name=p["name"] or "Аноним",
                    age=p["age"],
                    network=item["network"],
                    handle=item["handle"],
                    source="bio_scan",
                    notes="Извлечено из био анкеты"
                )
                if ok:
                    added += 1
        return added

    def should_offer_social_transfer(self, match_id: str, current_turn: int) -> bool:
        """
        Определяет, настал ли идеальный момент предложить перевести диалог в Instagram / Threads.
        Правило: переход предлагается на Turn 2-3 после первого теплого ответа девушки.
        """
        rules = self.config.get("funnel_rules", {})
        threshold = rules.get("transfer_turn_threshold", 2)
        if current_turn < threshold:
            return False

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            # Проверяем, не предлагали ли уже
            cursor.execute("SELECT id FROM social_transitions WHERE match_id = ?", (match_id,))
            if cursor.fetchone():
                return False
            # Проверяем, есть ли хоть одно сообщение от нее
            cursor.execute("SELECT id FROM chat_analytics WHERE match_id = ? AND sender = 'her'", (match_id,))
            has_her_reply = cursor.fetchone()
            return bool(has_her_reply)

    def generate_bridge_message(
        self,
        match_id: str,
        name: str,
        language: str = "ru",
        target_network: str = "instagram",
        custom_topic: str = ""
    ) -> str:
        """
        Генерирует естественное, харизматичное сообщение с предложением перейти в соцсеть.
        """
        profiles = self.config.get("user_profiles", {})
        net_info = profiles.get(target_network, {})
        my_handle = net_info.get("handle", "@val_shvedov")

        strategies = self.config.get("growth_strategies", {})
        key = f"{target_network}_funnel"
        funnel = strategies.get(key, {})
        templates = funnel.get("templates", {}).get(language) or funnel.get("templates", {}).get("ru", [])

        if templates:
            # Выбираем шаблон и форматируем
            tpl = templates[0]
            msg = tpl.format(handle=my_handle)
        else:
            # Fallback
            if language == "uk":
                msg = f"Слухай, у Тіндері сповіщення через раз приходять. Давай краще в інсті спишемось: {my_handle} 😉"
            elif language == "en":
                msg = f"Honestly Tinder notifications are super glitchy. Let's connect on Instagram instead: {my_handle} 😉"
            elif language == "es":
                msg = f"Las notificaciones de Tinder me fallan bastante. ¿Hablamos mejor por Instagram?: {my_handle} 😉"
            else:
                msg = f"Слушай, в Тиндере вечно уведомления через раз приходят. Давай лучше в инсте спишемся: {my_handle} 😉"

        # Записываем попытку перехода
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO social_transitions (
                    match_id, candidate_name, network, offered_handle, message_sent, turn_number, status, created_at
                ) VALUES (?, ?, ?, ?, ?, 2, 'offered', ?)
            """, (match_id, name, target_network, my_handle, msg, datetime.datetime.now().isoformat()))
            conn.commit()

        return msg

    def generate_full_report(self) -> str:
        """Формирует глубокий отчет по конверсии Tinder -> Личные соцсети"""
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Метрики
            cursor.execute("SELECT COUNT(*) FROM profiles WHERE is_match = 1")
            total_matches = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM social_transitions")
            total_transitions = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM social_leads")
            total_leads = cursor.fetchone()[0]

            cursor.execute("SELECT * FROM social_leads ORDER BY id DESC LIMIT 25")
            leads_rows = cursor.fetchall()

            cursor.execute("SELECT * FROM social_transitions ORDER BY id DESC LIMIT 10")
            trans_rows = cursor.fetchall()

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        report = f"""# 🚀 Воронка Развития Личных Соцсетей через Дейтинг-Платформы

> **Сформировано:** {now_str}  
> **Интеграция:** Tinder Web CDP ➔ Instagram / Threads / TikTok / Telegram

Модуль автоматизирует конверсию мэтчей из приложений знакомств в реальных подписчиков и лиды личных каналов.

---

## 📊 Ключевые показатели конверсии (Conversion Funnel):

```mermaid
flowchart LR
    A["🔥 Взаимные мэтчи ({total_matches})"] --> B["💬 Диалог & Раппорт"]
    B --> C["📲 Предложен переход ({total_transitions})"]
    C --> D["📸 Instagram / Threads / TG ({total_leads} лидов)"]
```

| Этап воронки | Количество | Доля / Конверсия | Описание |
| :--- | :---: | :---: | :--- |
| **1. Взаимные мэтчи** | `{total_matches}` | 100% | Одобренные профили и мэтчи |
| **2. В чате предложен соц-мост** | `{total_transitions}` | `{round(total_transitions / max(1, total_matches) * 100, 1)}%` | Оффер перейти в Instagram / Threads |
| **3. Собранные внешние соцсети** | `{total_leads}` | `{round(total_leads / max(1, total_matches) * 100, 1)}%` | Найденные ники из био и сообщений |

---

## 📇 Каталог собранных соцсетей кандидаток (Social Leads):

| Имя / Возраст | Соцсеть | Никнейм | Ссылка на профиль | Источник | Статус |
| :--- | :---: | :--- | :--- | :---: | :--- |
"""
        if not leads_rows:
            report += "| *Пока нет сохраненных лидов* | - | - | - | - | - |\n"
        else:
            for l in leads_rows:
                age_str = f", {l['age']}" if l['age'] else ""
                report += f"| **{l['candidate_name']}{age_str}** | `{l['network'].upper()}` | `{l['handle']}` | [{l['handle']}]({l['profile_url']}) | `{l['source']}` | `{l['status']}` |\n"

        report += """
---

## 💬 Последние предложения перехода в соцсети:

"""
        if not trans_rows:
            report += "_Предложений перехода в соцсети еще не отправлялось._\n"
        else:
            for t in trans_rows:
                report += f"- **{t['candidate_name']}** ➔ `{t['network']}` (`{t['offered_handle']}`) [{t['created_at'][:16]}]:\n"
                report += f"  > *«{t['message_sent']}»*\n"

        report += """
---

## 💡 Топовые хуки для био Tinder для пассивного притока подписчиков:
1. **Instagram Lifestyle:** `📸 inst: @val_shvedov (в Тиндере редко, здесь бываю каждый день)`
2. **Threads Curiosity:** `💭 Все факапы со свиданий и треш-истории пишу в Threads: @val_shvedov`
3. **TikTok Virality:** `🎬 Снимаю в TikTok то, о чем здесь боятся говорить: @val_shvedov`
"""

        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            f.write(report)

        return report

if __name__ == "__main__":
    mgr = SocialFunnelManager()
    found = mgr.scan_existing_profiles_for_leads()
    print(f"Сканирование завершено. Новых соц-лидов найдено: {found}")
    rep = mgr.generate_full_report()
    print(f"Отчет успешно сохранен в: {REPORT_PATH}")
    print("\nПревью отчета:")
    print(rep[:1000])
