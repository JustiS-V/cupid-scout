import time
import random
import sqlite3
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path("/Users/val9/Desktop/Process/dating-ai-agent")
DB_PATH = BASE_DIR / "data" / "dating.db"
CHAT_LOGS_FILE = BASE_DIR / "data" / "chat_logs.jsonl"

def human_type(page, selector: str, text: str):
    """Печатает текст с человеческими микро-задержками между клавишами"""
    page.click(selector)
    time.sleep(random.uniform(0.4, 0.8))
    
    for char in text:
        page.keyboard.type(char)
        # Случайная пауза между нажатиями (50 - 140 мс)
        delay = random.uniform(0.04, 0.12)
        # Иногда человек задумывается на знаках препинания
        if char in [",", ".", "!", "?", "—"]:
            delay += random.uniform(0.2, 0.45)
        time.sleep(delay)

def send_chat_message(match_id: str, message_text: str, auto_submit: bool = False) -> bool:
    """
    Отправляет или вставляет сообщение в чат Tinder.
    Если auto_submit=False — только вводит текст в поле ввода, оставляя клик за вами.
    Если auto_submit=True — нажимает Enter / кнопку 'Надіслати'.
    """
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        tinder_page = None
        for page in context.pages:
            if "tinder.com" in page.url:
                tinder_page = page
                break

        if not tinder_page:
            print("Ошибка: Вкладка Tinder не найдена в браузере!")
            return False

        # Открываем диалог
        target_href = f"/app/messages/{match_id}"
        print(f"Открытие диалога: {target_href} ...")
        
        try:
            link = tinder_page.query_selector(f'a[href*="{match_id}"]')
            if link:
                link.click()
            else:
                tinder_page.goto(f"https://tinder.com{target_href}", wait_until="domcontentloaded")
        except Exception as e:
            print(f"Ошибка перехода: {e}")
            return False

        time.sleep(2.0)

        # Ждем загрузки поля ввода
        try:
            tinder_page.wait_for_selector('textarea, [role="textbox"]', timeout=8000)
        except Exception:
            pass

        # Находим поле ввода
        input_selectors = [
            'textarea[placeholder*="повідомлення"]',
            'textarea[placeholder*="message"]',
            'textarea',
            'div[contenteditable="true"]',
            '[role="textbox"]',
            'form textarea',
            'input[type="text"]'
        ]

        active_selector = None
        for sel in input_selectors:
            el = tinder_page.query_selector(sel)
            if el and el.is_visible():
                active_selector = sel
                break

        if not active_selector:
            print("Не удалось найти поле ввода сообщения на странице чата!")
            return False

        print(f"Ввод сообщения в поле ({active_selector})...")
        human_type(tinder_page, active_selector, message_text)
        time.sleep(random.uniform(0.8, 1.5))

        status = "drafted"
        if auto_submit:
            print("Отправка сообщения (нажатие Enter)...")
            tinder_page.keyboard.press("Enter")
            status = "sent"
            time.sleep(1.0)
        else:
            print("Текст напечатан в поле ввода чата. Оставлен как черновик для проверки!")

        # Логирование в БД
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO chat_messages (match_id, sender, message_text, sent_at, ai_suggested, status)
                VALUES (?, 'me', ?, datetime('now'), 1, ?)
            """, (match_id, message_text, status))
            conn.commit()

        # Логирование в JSONL
        with open(CHAT_LOGS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "event": "message_action",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "match_id": match_id,
                "text": message_text,
                "status": status,
                "auto_submit": auto_submit
            }, ensure_ascii=False) + "\n")

        print("Логи сохранены в базу и JSONL.")
        return True

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Использование: python3 chat_sender.py <match_id> '<текст>' [--send]")
    else:
        m_id = sys.argv[1]
        msg = sys.argv[2]
        do_send = "--send" in sys.argv
        send_chat_message(m_id, msg, auto_submit=do_send)
