# 🏹 Dating AI Agent (Cupid Scout)

> Автономный агент для автоматического сбора, анализа внешности через Multimodal LLM (Gemini Flash Vision / GPT-4o) и отбора анкет для ONS/FWB/Casual знакомств.

---

## 📋 Поддерживаемые платформы (`platforms.json`)

| Платформа | Специфика | Метод автоматизации | Антифрод / Риск |
| :--- | :--- | :--- | :--- |
| **ДайВинчик (@leomatchbot)** | Telegram-бот с огромной базой | `Telethon` (Userbot) | **Низкий** (быстрый старт) |
| **Pure** | 100% целевая аудитория (секс/FWB/casual) | Android Emulator (Appium) | **Средний** (анонимные чаты) |
| **Tinder Web** | Массовая аудитория, много анкет | Playwright CDP к залогиненному Chrome | **Высокий** (обходится через CDP) |
| **Bumble Web** | Девушки пишут первыми | Playwright CDP | **Средний** |
| **Mamba Web** | Много прямого поиска без обязательств | Playwright / HTTP-сессии | **Низкий-средний** |
| **VK Знакомства** | Интеграция с профилями VK | Playwright / VK API | **Низкий** |

---

## 🚀 Быстрый старт

### 1. Установка зависимостей
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Настройка переменных окружения
Скопируйте конфиг и добавьте ключи:
```bash
cp .env.example .env
```
Минимум для работы Vision-модели:
- `GEMINI_API_KEY`: ваш бесплатный или платный ключ Google AI Studio.
- Опционально: `NOTIFICATION_BOT_TOKEN` и `NOTIFICATION_CHAT_ID` для получения уведомлений о топовых мэтчах в Telegram.

---

## 🛠 Использование CLI

### Посмотреть список площадок и аналитику:
```bash
python main.py platforms
```

### Тестовый прогон оценки анкеты через LLM:
```bash
python main.py test-eval
```

### Запуск сканера:
```bash
# Telegram ДайВинчик
python main.py scan --platform tg_leomatchbot --limit 10

# Tinder Web (требуется предварительно запущенный Chrome с портом 9222)
python main.py scan --platform tinder_web --limit 10
```

---

## 💡 Обход антибота для Web-дейтингов (Tinder / Bumble)

Чтобы Cloudflare не выдавал капчу и не блокировал браузер, запускайте ваш обычный Google Chrome через терминал с флагом отладки:

```bash
# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
```

Войдите в свой аккаунт руками, а скрипт подключится к уже открытой сессии через порт `9222` и будет автоматически анализировать профили и свайпать!
