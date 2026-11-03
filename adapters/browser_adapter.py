import os
import time
from pathlib import Path
from adapters.base import BasePlatformAdapter
from core.models import ProfileData

class BrowserCDPAdapter(BasePlatformAdapter):
    """
    Адаптер для Web-версий дейтингов (Tinder, Bumble, Mamba, Pure Web, Badoo).
    Подключается через Playwright к вашему залогиненному Google Chrome через порт 9222.
    
    Механика работы:
    1. Находит активную вкладку дейтинга в Chrome.
    2. Делает визуальный скриншот карточки анкеты (как видит человеческий глаз).
    3. Отправляет картинку в Qwen-VL на 12-ядерный воркер.
    4. Qwen-VL считывает с изображения фото, имя, возраст и текст био одновременно!
    5. Жмет стрелку вправо (Лайк) или влево (Дизлайк).
    """
    def __init__(self, cdp_port: int = 9222, platform_name: str = "tinder_web", save_dir: str = "./downloads"):
        self.cdp_port = cdp_port
        self.platform_name = platform_name
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.playwright = None
        self.browser = None
        self.page = None

    def connect(self) -> bool:
        try:
            from playwright.sync_api import sync_playwright
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.connect_over_cdp(f"http://localhost:{self.cdp_port}")
            default_context = self.browser.contexts[0]
            
            # Ищем целевую вкладку с дейтингом (исключая справку и внешние домены)
            target_keywords = ["tinder.com/app", "tinder.com", "badoo.com/encounters", "badoo.com", "bumble.com/app", "pure.app", "web.telegram.org", "boo.world", "okcupid.com"]
            exclude_keywords = ["help.", "support.", "blog.", "policy", "privacy", "terms", "feedback"]

            for p in default_context.pages:
                url = p.url.lower()
                if any(ex in url for ex in exclude_keywords):
                    continue
                if any(k in url for k in target_keywords):
                    self.page = p
                    break

            if not self.page:
                self.page = default_context.pages[0] if default_context.pages else default_context.new_page()

            print(f"[BrowserAdapter] ✅ Успешно подключен к Chrome! Активная страница: {self.page.url}")
            return True
        except Exception as e:
            print(f"[BrowserAdapter] ❌ Не удалось подключиться к Chrome на порту {self.cdp_port}: {e}")
            print("[BrowserAdapter] 💡 Запустите Chrome с ключом: /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222")
            return False

    def fetch_next_profile(self) -> ProfileData:
        """
        Делает скриншот текущей карточки профиля на экране.
        """
        timestamp = int(time.time())
        screenshot_path = self.save_dir / f"card_{timestamp}.jpg"
        
        print(f"[BrowserAdapter] 📸 Захват скриншота анкеты с экрана...")
        
        # Делаем скриншот центральной области или всей страницы
        try:
            self.page.screenshot(path=str(screenshot_path), quality=85, type="jpeg")
        except Exception as e:
            print(f"[BrowserAdapter] Ошибка создания скриншота: {e}")

        # Пытаемся также извлечь выделенный текст со страницы для подстраховки
        page_text = ""
        try:
            page_text = self.page.evaluate("() => document.body.innerText.slice(0, 1500)")
        except Exception:
            pass

        return ProfileData(
            platform=self.platform_name,
            profile_id=f"card_{timestamp}",
            name="Кандидатка",
            age=None,
            city=None,
            bio="Смотри скриншот карточки",
            photo_paths=[str(screenshot_path)] if screenshot_path.exists() else [],
            raw_text=page_text
        )

    def is_limit_reached(self) -> bool:
        """Проверяет, не вылезло ли всплывающее окно об исчерпании суточного лимита лайков"""
        if not self.page:
            return False
        try:
            text = self.page.evaluate("() => document.body.innerText.toLowerCase()")
            limit_markers = [
                "out of likes",
                "get tinder plus",
                "get tinder gold",
                "get tinder platinum",
                "закончились лайки",
                "лимит лайков",
                "у вас закончились лайки",
                "лайки закінчилися",
                "ви вичерпали ліміт",
                "get unlimited likes"
            ]
            for m in limit_markers:
                if m in text:
                    return True
        except Exception:
            pass
        return False

    def like(self, profile: ProfileData):
        """Лайк / свайп вправо с естественной паузой"""
        print(f"[BrowserAdapter] 💚 Свайп вправо (Лайк)...")
        if self.page:
            try:
                url = self.page.url.lower()
                if "telegram.org" in url:
                    # Попытка кликнуть кнопку с сердечком или цифрой 1 в Telegram Web
                    self.page.evaluate("""() => {
                        const btns = Array.from(document.querySelectorAll('button, .reply-markup-button, .btn-primary'));
                        const b = btns.find(x => x.innerText.includes('❤️') || x.innerText.includes('👍') || x.innerText.trim() === '1');
                        if (b) b.click();
                    }""")
                elif "badoo.com" in url:
                    btn = self.page.query_selector('[data-choice="yes"], .encounters-controls__button--like')
                    if btn: btn.click()
                    else: self.page.keyboard.press("ArrowRight")
                else:
                    self.page.keyboard.press("ArrowRight")
            except Exception as e:
                print(f"[BrowserAdapter] Ошибка нажатия Like: {e}")
        time.sleep(2.5)

    def dislike(self, profile: ProfileData):
        """Дизлайк / свайп влево с естественной паузой"""
        print(f"[BrowserAdapter] ❌ Свайп влево (Пропуск)...")
        if self.page:
            try:
                url = self.page.url.lower()
                if "telegram.org" in url:
                    self.page.evaluate("""() => {
                        const btns = Array.from(document.querySelectorAll('button, .reply-markup-button, .btn-primary'));
                        const b = btns.find(x => x.innerText.includes('👎') || x.innerText.includes('❌') || x.innerText.trim() === '2');
                        if (b) b.click();
                    }""")
                elif "badoo.com" in url:
                    btn = self.page.query_selector('[data-choice="no"], .encounters-controls__button--dislike')
                    if btn: btn.click()
                    else: self.page.keyboard.press("ArrowLeft")
                else:
                    self.page.keyboard.press("ArrowLeft")
            except Exception as e:
                print(f"[BrowserAdapter] Ошибка нажатия Pass: {e}")
        time.sleep(1.8)
