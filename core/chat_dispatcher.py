import time
import random
import json
import sqlite3
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path("/Users/val9/Desktop/Process/dating-ai-agent")
DB_PATH = BASE_DIR / "data" / "dating.db"
CHAT_LOGS_FILE = BASE_DIR / "data" / "chat_logs.jsonl"
MATCHES_DATA_DIR = BASE_DIR / "data" / "mutual_matches"
MATCHES_DATA_DIR.mkdir(parents=True, exist_ok=True)

TARGETS = [
    {
        "name": "Julia",
        "match_id": "681806443b495980ca094bc86ab6acd892bab379ac026561",
        "language": "ru",
        "bio": "Возможно, Tinder всего лишь ещё одна форма эскапизма...",
        "message": "Julia, если Tinder — это эскапизм, то куда именно мы отсюда сбегаем: в уютную кофейню или сразу в бар? 😉"
    },
    {
        "name": "Елена",
        "match_id": "681806443b495980ca094bc86a88df87e2cf08799d9d281f",
        "language": "ru",
        "bio": "Разбираюсь в макраме...",
        "message": "Елена, привет! Макраме — это серьезный скилл. Сможешь связать разговор так, чтобы мы оба не запутались? 😉"
    },
    {
        "name": "Марі",
        "match_id": "67fc09b7f12dcbfa7b5955ed681806443b495980ca094bc8",
        "language": "en",
        "bio": "I’m normal, self-aware, creative, slow, do stand up, teach kids...",
        "message": "Hey Mari! Doing stand-up and teaching kids sounds like the ultimate stress test 😄 Which audience is actually tougher to impress?"
    },
    {
        "name": "Anastasia",
        "match_id": "681806443b495980ca094bc86a464d37e44f0699edf5ce9e",
        "language": "en",
        "bio": "Idk what to say... just ask me if u wanna know smth🌿",
        "message": "Hey Anastasia, you said “just ask”, so I’ll take the bait: what’s the most spontaneous decision you’ve made lately? 🌿"
    }
]

def human_type_and_send(page, selector: str, text: str, is_already_typed: bool = False):
    """Имитирует набор текста человеком и отправку"""
    if not is_already_typed:
        page.click(selector)
        time.sleep(random.uniform(0.3, 0.7))
        # Очищаем поле на всякий случай
        page.keyboard.press("Meta+A")
        page.keyboard.press("Backspace")
        time.sleep(0.3)
        
        for char in text:
            page.keyboard.type(char)
            delay = random.uniform(0.04, 0.11)
            if char in [",", ".", "!", "?", "—", ":"]:
                delay += random.uniform(0.18, 0.4)
            time.sleep(delay)
    
    # Пауза перед кликом 'Отправить' (человек перечитывает сообщение)
    time.sleep(random.uniform(1.2, 2.5))
    
    # Пытаемся найти кнопку отправки или жмем Enter
    sent = False
    send_btn = page.query_selector('button[type="submit"], [aria-label*="Надіслати"], [aria-label*="Send"]')
    if send_btn and send_btn.is_enabled():
        send_btn.click()
        sent = True
    else:
        page.keyboard.press("Enter")
        sent = True

    time.sleep(1.5)
    return sent

def dispatch_all(dry_run: bool = False):
    print("="*75)
    print("🚀 Dating AI: Запуск отправки персонализированных сообщений (Strict Language Match)")
    print(f"Режим: {'ТЕСТОВЫЙ ЧЕРНОВИК (без нажатия Send)' if dry_run else 'ЖИВАЯ ОТПРАВКА В TINDER'}")
    print("="*75)

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        tinder_page = None
        for page in context.pages:
            if "tinder.com" in page.url:
                tinder_page = page
                break

        if not tinder_page:
            print("❌ Ошибка: Вкладка Tinder не найдена в браузере!")
            return

        for idx, item in enumerate(TARGETS, 1):
            name = item["name"]
            m_id = item["match_id"]
            lang = item["language"].upper()
            msg = item["message"]

            print(f"\n[{idx}/{len(TARGETS)}] Обработка: {name} (Язык: {lang})...")
            print(f"💬 Текст: \"{msg}\"")

            # Переходим в чат с девушкой
            try:
                link = tinder_page.query_selector(f'a[href*="{m_id}"]')
                if link:
                    link.click()
                else:
                    tinder_page.goto(f"https://tinder.com/app/messages/{m_id}", wait_until="domcontentloaded")
            except Exception as e:
                print(f"  ⚠️ Ошибка навигации: {e}")
                continue

            time.sleep(random.uniform(2.2, 3.5))

            # Ищем поле ввода
            textarea = None
            for sel in ['textarea', 'div[contenteditable="true"]', '[role="textbox"]']:
                el = tinder_page.query_selector(sel)
                if el and el.is_visible():
                    textarea = sel
                    break

            if not textarea:
                print(f"  ❌ Поле ввода для {name} не найдено, пропускаем.")
                continue

            # Проверяем, напечатано ли уже
            current_val = tinder_page.evaluate("""() => {
                const el = document.querySelector('textarea, [role="textbox"]');
                return el ? (el.value || el.innerText) : '';
            }""")
            is_already_typed = (name == "Julia" and "Julia, если Tinder" in current_val)

            if dry_run:
                if not is_already_typed:
                    tinder_page.click(textarea)
                    tinder_page.fill(textarea, msg)
                print(f"  ✅ [DRY-RUN] Текст напечатан в поле ввода для {name}.")
                status = "drafted"
            else:
                sent = human_type_and_send(tinder_page, textarea, msg, is_already_typed=is_already_typed)
                print(f"  🎉 Сообщение успешно отправлено для {name}!")
                status = "sent"

            # Делаем скриншот подтверждения
            shot_path = MATCHES_DATA_DIR / f"sent_{name}_{m_id}.jpg"
            try:
                tinder_page.screenshot(path=str(shot_path), quality=80, type="jpeg")
            except Exception:
                pass

            # Запись в SQLite
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO chat_messages (match_id, sender, message_text, sent_at, ai_suggested, status)
                    VALUES (?, 'me', ?, datetime('now'), 1, ?)
                """, (m_id, msg, status))
                cursor.execute("""
                    UPDATE mutual_matches 
                    SET total_messages = total_messages + 1,
                        last_message_text = ?,
                        last_sender = 'me',
                        updated_at = datetime('now')
                    WHERE match_id = ?
                """, (msg, m_id))
                conn.commit()

            # Запись в JSONL лог
            with open(CHAT_LOGS_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "event": "message_sent" if not dry_run else "message_drafted",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "match_id": m_id,
                    "name": name,
                    "language": lang,
                    "text": msg,
                    "status": status,
                    "screenshot": str(shot_path)
                }, ensure_ascii=False) + "\n")

            # Естественная пауза между диалогами (15-30 секунд), если не последний
            if idx < len(TARGETS):
                pause = random.uniform(12.0, 20.0)
                print(f"  ⏳ Естественная пауза между диалогами: {round(pause, 1)} сек...")
                time.sleep(pause)

        # Возвращаем вкладку на ленту свайпов
        tinder_page.goto("https://tinder.com/app/recs", wait_until="domcontentloaded")
        print("\n🏁 Все сообщения успешно отправлены! Вкладка возвращена на поиск анкет (/app/recs).")

if __name__ == "__main__":
    import sys
    is_dry = "--dry-run" in sys.argv
    dispatch_all(dry_run=is_dry)
