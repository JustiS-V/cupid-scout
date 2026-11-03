import time
import random
import re
import json
import sqlite3
from pathlib import Path
from playwright.sync_api import sync_playwright

from adapters.browser_adapter import BrowserCDPAdapter
from core.scorer import ProfileScorer
from core.notifier import Notifier
from core.storage import StorageManager
from core.dossier import DossierGenerator
from core.quota_manager import QuotaManager
from core.analytics import BehavioralAnalyticsManager

BASE_DIR = Path("/Users/val9/Desktop/Process/dating-ai-agent")
DB_PATH = BASE_DIR / "data" / "dating.db"
CHAT_LOGS_FILE = BASE_DIR / "data" / "chat_logs.jsonl"
MATCHES_DATA_DIR = BASE_DIR / "data" / "mutual_matches"
MATCHES_DATA_DIR.mkdir(parents=True, exist_ok=True)

class AutonomousMatchSwiper:
    """
    Автономный агент:
    1. Свайпает анкеты на /app/recs с умной фильтрацией.
    2. Если случается MATCH («Це пара!» / «It's a Match!»):
       - Мгновенно перехватывает всплывающее окно
       - Считывает имя, язык и фото девушки
       - Генерирует персональный оупенер на языке ее профиля
       - Отправляет первое сообщение прямо в окно мэтча
       - Закрывает модалку и возвращается к свайпам
    3. Пока ждет ответа — непрерывно свайпает дальше до исчерпания суточного лимита!
    """
    def __init__(self, cdp_port: int = 9222):
        self.cdp_port = cdp_port
        self.adapter = BrowserCDPAdapter(platform_name="tinder_web")
        self.scorer = ProfileScorer()
        self.notifier = Notifier()
        self.storage = StorageManager()
        self.dossier_gen = DossierGenerator()
        self.quota_mgr = QuotaManager()
        self.analytics = BehavioralAnalyticsManager()

    def check_and_handle_match_popup(self, page) -> bool:
        """Проверяет появление всплывающего окна взаимного мэтча («Це пара!») и сразу пишет ей"""
        try:
            text = page.evaluate("() => document.body.innerText.toLowerCase()")
            match_markers = ["це пара", "it's a match", "ви створили пару", "взаимная пара", "вы подошли"]
            
            is_match_popup = any(m in text for m in match_markers)
            if not is_match_popup:
                return False

            print("\n" + "🔥"*40)
            print("🎉 СВЕЖИЙ ВЗАИМНЫЙ МЭТЧ ЗАФИКСИРОВАН ПРЯМО НА ЭКРАНЕ!")
            print("🔥"*40)

            # Извлекаем имя из модалки
            girl_name = page.evaluate("""() => {
                const h = Array.from(document.querySelectorAll('h1, h2, h3, div')).find(el => {
                    const t = el.innerText.trim();
                    return t.includes('пару з ') || t.includes('matched with ');
                });
                if (h) {
                    const m = h.innerText.match(/(?:пару з|matched with)\\s+([A-Za-zА-Яа-яЁёЇїІіЄєҐґ]+)/i);
                    if (m) return m[1];
                }
                return 'Красотка';
            }""")

            # Определяем язык страницы/анкеты
            lang = "ua" if ("пару" in text or "надіслати" in text) else "ru"

            # Генерируем дерзкий, легкий оупенер в зависимости от языка
            if lang == "ua":
                opener = f"{girl_name}, привіт! Це взаємний мэтч 😉 Куди спершу тікаємо від осінньої рутини: на каву чи одразу на вино?"
            else:
                opener = f"{girl_name}, привет! Это взаимный мэтч 😉 Куда сперва сбегаем от рутины: на уютный кофе или сразу в бар?"

            print(f"💬 Отправка первого сообщения для {girl_name} (Язык: {lang.upper()}):")
            print(f"   > \"{opener}\"")

            # Ищем поле ввода внутри модалки мэтча
            input_sel = None
            for sel in ['textarea', 'input[type="text"]', '[role="textbox"]', 'form textarea']:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    input_sel = sel
                    break

            if input_sel:
                page.click(input_sel)
                time.sleep(0.4)
                # Человеческий набор
                for char in opener:
                    page.keyboard.type(char)
                    time.sleep(random.uniform(0.04, 0.10))
                time.sleep(1.0)
                
                # Кнопка отправить или Enter
                send_btn = page.query_selector('button:has-text("Надіслати"), button:has-text("Send"), button[type="submit"]')
                if send_btn and send_btn.is_visible():
                    send_btn.click()
                else:
                    page.keyboard.press("Enter")
                
                print(f"✅ Сообщение для {girl_name} успешно отправлено!")
                time.sleep(2.0)

            # Сохраняем скриншот мэтча
            shot_path = MATCHES_DATA_DIR / f"live_match_{girl_name}_{int(time.time())}.jpg"
            try:
                page.screenshot(path=str(shot_path), quality=85)
            except Exception:
                pass

            # Закрываем модалку / нажимаем 'Продовжити свайпати'
            page.evaluate("""() => {
                const btns = Array.from(document.querySelectorAll('button, div[role="button"]'));
                const cont = btns.find(b => {
                    const t = b.innerText.toLowerCase();
                    return t.includes('продовжити') || t.includes('keep swiping') || t.includes('позже') || t.includes('закрити') || b.getAttribute('aria-label') === 'Close';
                });
                if (cont) cont.click();
            }""")
            time.sleep(1.5)

            # Логируем событие
            with open(CHAT_LOGS_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "event": "live_match_messaged",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "name": girl_name,
                    "opener": opener,
                    "language": lang,
                    "screenshot": str(shot_path)
                }, ensure_ascii=False) + "\n")

            return True
        except Exception as e:
            print(f"Ошибка обработки всплывающего мэтча: {e}")
            return False

    def run(self, max_swipes: int = 100):
        print("="*75)
        print("🏹 CUPID SCOUT: АВТОНОМНЫЙ ЦИКЛ (МЭТЧИ $\\rightarrow$ СООБЩЕНИЯ $\\rightarrow$ СВАЙПЫ)")
        print("="*75)

        if not self.adapter.connect():
            print("❌ Не удалось подключиться к браузеру.")
            return

        page = self.adapter.page
        swipes_done = 0
        likes_done = 0
        skips_done = 0
        matches_found = 0

        # Убеждаемся, что мы на /app/recs
        if "/app/recs" not in page.url:
            page.goto("https://tinder.com/app/recs", wait_until="domcontentloaded")
            time.sleep(2.0)

        for i in range(1, max_swipes + 1):
            # 1. Проверяем модалку мэтча
            if self.check_and_handle_match_popup(page):
                matches_found += 1
                time.sleep(2.0)

            # 2. Проверяем лимит лайков
            reached, timer_str = self.adapter.get_limit_details()
            if reached:
                print("\n🛑 Tinder показал окно суточного лимита бесплатных лайков!")
                self.quota_mgr.record_limit_hit("tinder_web", timer_string=timer_str)
                self.adapter.dismiss_limit_modal()
                break

            print(f"\n--- Анкета #{i}/{max_swipes} (Лайков: {likes_done}, Мэтчей в сессии: {matches_found}) ---")
            
            try:
                profile = self.adapter.fetch_next_profile()
                eval_res = self.scorer.evaluate(profile)

                # Досье
                dossier = self.dossier_gen.generate(profile)
                self.storage.save_scan(profile, eval_res, dossier)

                print(f"👤 {profile.name}, {profile.age or '?'} | Оценка: {eval_res.attractiveness_score}/10 | FWB: {eval_res.casual_intent_score}/10")

                if eval_res.is_match:
                    print("🔥 MATCH-LIKE! Ставим Like ❤️")
                    self.adapter.like(profile)
                    likes_done += 1
                    
                    # Проверяем, не сработал ли взаимный мэтч прямо после лайка
                    time.sleep(1.5)
                    if self.check_and_handle_match_popup(page):
                        matches_found += 1
                else:
                    print(f"⏭ Skip ({eval_res.reason[:40]}...)")
                    self.adapter.dislike(profile)
                    skips_done += 1

                swipes_done += 1
                time.sleep(random.uniform(2.0, 3.8))

            except Exception as e:
                print(f"⚠️ Ошибка на шаге #{i}: {e}")
                time.sleep(2.5)

        print("\n" + "="*75)
        print("🏁 СЕССИЯ АВТОНОМНОГО ЦИКЛА ЗАВЕРШЕНА:")
        print("="*75)
        print(f"Обработано анкет:     {swipes_done}")
        print(f"Поставлено лайков:    {likes_done} ❤️")
        print(f"Пропущено (скипы):    {skips_done} ⏭")
        print(f"Взаимных пар поймано: {matches_found} 🔥 (сообщения отправлены сразу)")
        print("="*75 + "\n")

if __name__ == "__main__":
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 50
    agent = AutonomousMatchSwiper()
    agent.run(max_swipes=limit)
