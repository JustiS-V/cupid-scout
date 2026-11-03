import os
import sys
import json
import time
from pathlib import Path
import os
import sys
import json
import time
from pathlib import Path

# Optional load_dotenv
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from core.models import ProfileData
from core.scorer import ProfileScorer
from core.notifier import Notifier
from core.storage import StorageManager
from core.dossier import DossierGenerator
from adapters.telegram_adapter import TelegramDatingAdapter
from adapters.browser_adapter import BrowserCDPAdapter

def show_platforms():
    """Показать список поддерживаемых платформ для поиска анкет"""
    config_path = Path(__file__).parent / "platforms.json"
    if not config_path.exists():
        print("Файл platforms.json не найден!")
        return

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    try:
        from rich.console import Console
        from rich.table import Table
        console = Console()
        table = Table(title="🎯 Список площадок для поиска анкет", show_header=True, header_style="bold magenta")
        table.add_column("ID", style="dim", width=18)
        table.add_column("Платформа", style="bold cyan")
        table.add_column("Приоритет", style="yellow")
        table.add_column("Подходит под Casual/FWB", style="green")
        table.add_column("Риск бана", style="red")
        table.add_column("Стек / Метод", style="white")

        for p in data.get("platforms", []):
            table.add_row(
                p["id"],
                p["name"],
                p["priority"],
                p["casual_suitability"],
                p["ban_risk"],
                p["tech_stack"]
            )

        console.print(table)
        console.print("\n[bold green]Рекомендация под спор:[/bold green] Используйте [bold]tg_leomatchbot[/bold] для мгновенного старта или [bold]tinder_web[/bold] через Google Chrome с отладчиком.\n")
    except ImportError:
        # Fallback to plain text table
        print("\n" + "="*80)
        print("🎯 СПИСОК ПЛОЩАДОК ДЛЯ ПОИСКА АНКЕТ:")
        print("="*80)
        for p in data.get("platforms", []):
            print(f"• [{p['id']}] {p['name']} ({p['priority']})")
            print(f"  Casual/FWB: {p['casual_suitability']} | Риск бана: {p['ban_risk']}")
            print(f"  Стек: {p['tech_stack']}")
            print(f"  Инфо: {p.get('notes', '')}\n")
        print("="*80 + "\n")

def run_test_eval():
    """Тестовый прогон оценки анкеты через LLM/Vision"""
    print("Запуск тестовой оценки демо-профиля...")
    scorer = ProfileScorer()
    notifier = Notifier()

    dummy_profile = ProfileData(
        platform="demo",
        profile_id="demo_001",
        name="Диана",
        age=23,
        city="Центр",
        bio="Люблю вино, ночные поездки по городу и классную музыку. Без занудства, за легкий вайб.",
        photo_paths=[]
    )

    result = scorer.evaluate(dummy_profile)
    print(f"Оценка внешности: {result.attractiveness_score}/10")
    print(f"Оценка соответствия цели (FWB/Casual): {result.casual_intent_score}/10")
    print(f"Вайб: {result.vibe_type}")
    print(f"Вердикт: {result.reason}")
    print(f"Оупенер: {result.suggested_opener}")

    if result.is_match:
        notifier.notify_match(dummy_profile, result)

def run_scan(platform: str = "tg_leomatchbot", limit: int = 5):
    """Запустить сканирование и отбор анкет"""
    print(f"Запуск агента на платформе: {platform}")
    scorer = ProfileScorer()
    notifier = Notifier()
    storage = StorageManager()
    dossier_gen = DossierGenerator()

    if platform.startswith("tg_"):
        adapter = TelegramDatingAdapter()
    elif "web" in platform:
        adapter = BrowserCDPAdapter(platform_name=platform)
    else:
        print(f"Неизвестный адаптер для платформы {platform}")
        return

    adapter.connect()

    for i in range(1, limit + 1):
        # Проверяем, не исчерпан ли суточный лимит
        if hasattr(adapter, "is_limit_reached") and adapter.is_limit_reached():
            print("\n🛑 ВНИМАНИЕ: Tinder показал экран исчерпания суточного лимита бесплатных лайков!")
            print("Бот автоматически останавливает работу до обновления лимита.")
            break

        print(f"\n--- Анкета #{i}/{limit} ---")
        profile = adapter.fetch_next_profile()
        eval_res = scorer.evaluate(profile)

        # Формируем досье
        dossier = dossier_gen.generate(profile)

        # Сохраняем в базу данных и архив
        saved_id = storage.save_scan(profile, eval_res, dossier)
        print(f"💾 Анкета сохранена в базу (ID: {saved_id})")

        print(f"👤 {profile.name}, {profile.age} | Внешность: {eval_res.attractiveness_score}/10 | FWB Score: {eval_res.casual_intent_score}/10")
        
        if eval_res.is_match:
            print("🔥 MATCH! Ставим лайк и отправляем уведомление")
            adapter.like(profile)
            notifier.notify_match(profile, eval_res)
        else:
            print(f"Пропуск: {eval_res.reason}")
            adapter.dislike(profile)

        # Проверка лимита после лайка
        if hasattr(adapter, "is_limit_reached") and adapter.is_limit_reached():
            print("\n🛑 Tinder сообщил: бесплатные лайки на сегодня закончились!")
            break

        time.sleep(2.0)

    print("\nСессия сканирования завершена!")

def show_stats():
    """Показать общую статистику свайпов"""
    storage = StorageManager()
    stats = storage.get_stats()
    print("\n" + "="*50)
    print("📊 СТАТИСТИКА CUPID SCOUT:")
    print("="*50)
    print(f"Всего просмотрено анкет: {stats['total']}")
    print(f"Одобрено (лайки):         {stats['liked']} ❤️")
    print(f"Пропущено (дизлайки):     {stats['skipped']} ⏭")
    print(f"Средний балл красоты:     {stats['avg_attractiveness']}/10 ⭐")
    print("="*50 + "\n")

def show_history():
    """Показать последние сохраненные анкеты"""
    storage = StorageManager()
    import sqlite3
    from core.storage import DB_PATH
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, timestamp, name, age, attractiveness_score, casual_intent_score, action, reason FROM profiles ORDER BY timestamp DESC LIMIT 15")
        rows = cursor.fetchall()
        
    print("\n" + "="*90)
    print(f"{'ID':<18} | {'Имя/Возраст':<15} | {'Баллы':<12} | {'Действие':<10} | {'Вердикт'}")
    print("="*90)
    for r in rows:
        name_age = f"{r[2] or 'Девушка'}, {r[3] or '?'}"
        scores = f"{r[4]:.1f}/{r[5]:.1f}"
        act = "❤️ LIKE" if r[6] == "liked" else "⏭ PASS"
        reason = (r[7][:40] + "...") if r[7] and len(r[7]) > 40 else (r[7] or "")
        print(f"{r[0]:<18} | {name_age:<15} | {scores:<12} | {act:<10} | {reason}")
    print("="*90 + "\n")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Dating AI Agent")
    parser.add_argument("command", choices=["platforms", "test-eval", "scan", "stats", "history"], nargs="?", default="platforms")
    parser.add_argument("--platform", default="tg_leomatchbot", help="ID платформы")
    parser.add_argument("--limit", type=int, default=5, help="Количество анкет")
    args = parser.parse_args()

    if args.command == "platforms":
        show_platforms()
    elif args.command == "test-eval":
        run_test_eval()
    elif args.command == "scan":
        run_scan(platform=args.platform, limit=args.limit)
    elif args.command == "stats":
        show_stats()
    elif args.command == "history":
        show_history()
