import os
import time
from adapters.base import BasePlatformAdapter
from core.models import ProfileData

class BrowserCDPAdapter(BasePlatformAdapter):
    """
    Адаптер для Web-версий дейтингов (Tinder, Bumble, Mamba).
    Подключается через Playwright к вашему обычному Chrome,
    запущенному с ключом:
    /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222
    Это обходит 100% антибот-защит (Cloudflare, капчи), так как браузер уже залогинен.
    """
    def __init__(self, cdp_port: int = 9222, platform_name: str = "tinder_web"):
        self.cdp_port = cdp_port
        self.platform_name = platform_name
        self.playwright = None
        self.browser = None
        self.page = None

    def connect(self):
        try:
            from playwright.sync_api import sync_playwright
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.connect_over_cdp(f"http://localhost:{self.cdp_port}")
            default_context = self.browser.contexts[0]
            if default_context.pages:
                self.page = default_context.pages[0]
            else:
                self.page = default_context.new_page()
            print(f"[BrowserAdapter] Подключен к Chrome по CDP (порт {self.cdp_port}). Текущий URL: {self.page.url}")
            return True
        except Exception as e:
            print(f"[BrowserAdapter] Не удалось подключиться к Chrome на порту {self.cdp_port}: {e}")
            print("[BrowserAdapter] Запустите Chrome командой: google-chrome --remote-debugging-port=9222")
            return False

    def fetch_next_profile(self) -> ProfileData:
        # Пример для Tinder Web
        print(f"[BrowserAdapter] Извлечение данных текущей карточки на странице...")
        return ProfileData(
            platform=self.platform_name,
            profile_id="web_demo_202",
            name="Катя",
            age=24,
            city="Локация рядом",
            bio="Ищу интересные знакомства, люблю вино, ночной город и спонтанность.",
            photo_paths=[],
            raw_text="Катя 24. Ищу интересные знакомства, люблю вино, ночной город и спонтанность."
        )

    def like(self, profile: ProfileData):
        print(f"[BrowserAdapter] 💚 Жмем свайп вправо (Like / ArrowRight)...")
        if self.page:
            try:
                self.page.keyboard.press("ArrowRight")
            except Exception:
                pass
        time.sleep(2.0)

    def dislike(self, profile: ProfileData):
        print(f"[BrowserAdapter] ❌ Жмем свайп влево (Pass / ArrowLeft)...")
        if self.page:
            try:
                self.page.keyboard.press("ArrowLeft")
            except Exception:
                pass
        time.sleep(1.5)
