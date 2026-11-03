import os
import time
import json
import sqlite3
import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright
from core.analytics import BehavioralAnalyticsManager

BASE_DIR = Path("/Users/val9/Desktop/Process/dating-ai-agent")
DB_PATH = BASE_DIR / "data" / "dating.db"
BEHAVIOR_LOGS_FILE = BASE_DIR / "data" / "behavioral_events.jsonl"

class ChatObserver:
    """
    Модуль фонового мониторинга ответов девушек:
    1. Периодически инспектирует открытый чат в Dolphin Anty.
    2. Если обнаружено новое сообщение от девушки:
       - Измеряет время ответа (с момента отправки нашего оупенера)
       - Фиксирует длину, эмоциональность, вопросы
       - Обновляет поведенческий профиль в SQLite
       - Отправляет уведомление и сохраняет скриншот диалога
    """
    def __init__(self, cdp_port: int = 9222):
        self.cdp_port = cdp_port
        self.analytics = BehavioralAnalyticsManager()

    def check_incoming_replies(self) -> List[Dict[str, Any]]:
        """Однократная проверка диалогов на наличие новых ответов"""
        events = []
        with sync_playwright() as p:
            try:
                browser = p.chromium.connect_over_cdp(f"http://localhost:{self.cdp_port}")
                context = browser.contexts[0]
                tinder_page = None
                for page in context.pages:
                    if "tinder.com" in page.url:
                        tinder_page = page
                        break

                if not tinder_page:
                    print("[ChatObserver] Вкладка Tinder не найдена.")
                    return []

                # Получаем активные цели из БД
                with sqlite3.connect(DB_PATH) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("SELECT match_id, name FROM mutual_matches WHERE status = 'active'")
                    active_targets = cursor.fetchall()

                for target in active_targets:
                    m_id = target["match_id"]
                    name = target["name"]
                    
                    # Проверяем, есть ли превью непрочитанного или нового сообщения в сайдбаре
                    # В Tinder новые сообщения помечаются синей точкой или текстом последнего сообщения
                    chat_url = f"/app/messages/{m_id}"
                    
                    # Проверяем текст диалога
                    has_reply = tinder_page.evaluate("""(matchId) => {
                        const link = document.querySelector(`a[href*="${matchId}"]`);
                        if (!link) return null;
                        const text = link.innerText;
                        // Проверяем наличие синей точки (unread indicator) или текста превью
                        const hasUnreadDot = !!link.querySelector('.unread, [aria-label*="unread"], [class*="unread"]');
                        return { text, hasUnreadDot };
                    }""", m_id)

                    # Если есть признак активности или принудительно открываем для проверки
                    # Проверяем последнее сообщение в БД
                    with sqlite3.connect(DB_PATH) as conn:
                        c = conn.cursor()
                        c.execute("SELECT sender, message_text FROM chat_analytics WHERE match_id = ? ORDER BY id DESC LIMIT 1", (m_id,))
                        last_record = c.fetchone()

                    # Открываем диалог для чтения
                    try:
                        tinder_page.goto(f"https://tinder.com{chat_url}", wait_until="domcontentloaded")
                        time.sleep(2.0)
                    except Exception:
                        continue

                    # Считываем все сообщения в чате
                    messages_data = tinder_page.evaluate("""() => {
                        const msgs = [];
                        // Селекторы пузырьков сообщений в Tinder
                        const bubbles = document.querySelectorAll('[role="listitem"], .messageListItem, [data-testid="message-text"]');
                        bubbles.forEach(b => {
                            const text = b.innerText.trim();
                            if (!text) return;
                            // Определяем автора: исходящие обычно имеют класс 'sent' / синий/серый фон или flex-end
                            const isMe = b.classList.contains('messageListItem--sent') || 
                                         b.classList.contains('sent') || 
                                         window.getComputedStyle(b).justifyContent === 'flex-end' ||
                                         b.closest('[class*="sent"], [class*="outgoing"]') !== null;
                            msgs.push({
                                text: text,
                                sender: isMe ? 'me' : 'her'
                            });
                        });
                        return msgs;
                    }""")

                    # Проверяем, есть ли сообщения от 'her'
                    her_msgs = [m for m in messages_data if m["sender"] == "her"]
                    if her_msgs:
                        latest_her_msg = her_msgs[-1]["text"]
                        
                        # Проверяем, не записано ли оно уже
                        with sqlite3.connect(DB_PATH) as conn:
                            c = conn.cursor()
                            c.execute("SELECT id FROM chat_analytics WHERE match_id = ? AND sender = 'her' AND message_text = ?", (m_id, latest_her_msg))
                            already_logged = c.fetchone()

                        if not already_logged:
                            print(f"\n🎉 [ChatObserver] ОБНАРУЖЕН НОВЫЙ ОТВЕТ от {name}!")
                            print(f"💬 Текст ответа: \"{latest_her_msg}\"")
                            
                            # Записываем в аналитику
                            record = self.analytics.record_message(
                                match_id=m_id,
                                sender="her",
                                message_text=latest_her_msg,
                                notes="Автоматически зафиксировано наблюдателем"
                            )
                            events.append(record)

                            # Сохраняем скриншот чата
                            shot_path = BASE_DIR / "data" / "mutual_matches" / f"reply_{name}_{int(time.time())}.jpg"
                            tinder_page.screenshot(path=str(shot_path), quality=85)
                            print(f"📸 Скриншот ответа сохранен: {shot_path}")

                # Возвращаемся в /app/recs
                tinder_page.goto("https://tinder.com/app/recs", wait_until="domcontentloaded")

            except Exception as e:
                print(f"[ChatObserver] Ошибка мониторинга: {e}")

        # Обновляем сводный отчет
        self.analytics.generate_full_report()
        return events

    def run_daemon(self, interval_seconds: int = 180):
        """Фоновый цикл проверки раз в N секунд"""
        print(f"🕵️ Запуск фонового ChatObserver (интервал проверки: {interval_seconds} сек)...")
        while True:
            try:
                print(f"[{time.strftime('%H:%M:%S')}] Проверка входящих ответов...")
                self.check_incoming_replies()
            except Exception as e:
                print(f"Ошибка в цикле наблюдателя: {e}")
            time.sleep(interval_seconds)

if __name__ == "__main__":
    import sys
    observer = ChatObserver()
    if "--daemon" in sys.argv:
        observer.run_daemon()
    else:
        res = observer.check_incoming_replies()
        print(f"\nПроверка завершена. Новых ответов зафиксировано: {len(res)}")
