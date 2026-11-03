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

    if platform.startswith("tg_"):
        adapter = TelegramDatingAdapter()
    elif "web" in platform:
        adapter = BrowserCDPAdapter(platform_name=platform)
    else:
        print(f"Неизвестный адаптер для платформы {platform}")
        return

    adapter.connect()

    for i in range(1, limit + 1):
        print(f"\n--- Анкета #{i}/{limit} ---")
        profile = adapter.fetch_next_profile()
        eval_res = scorer.evaluate(profile)

        print(f"👤 {profile.name}, {profile.age} | Внешность: {eval_res.attractiveness_score}/10 | FWB Score: {eval_res.casual_intent_score}/10")
        
        if eval_res.is_match:
            print("🔥 MATCH! Ставим лайк и отправляем уведомление")
            adapter.like(profile)
            notifier.notify_match(profile, eval_res)
        else:
            print(f"Пропуск: {eval_res.reason}")
            adapter.dislike(profile)

        time.sleep(1.5)

    print("\nСессия сканирования завершена!")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Dating AI Agent")
    parser.add_argument("command", choices=["platforms", "test-eval", "scan"], nargs="?", default="platforms")
    parser.add_argument("--platform", default="tg_leomatchbot", help="ID платформы")
    parser.add_argument("--limit", type=int, default=5, help="Количество анкет")
    args = parser.parse_args()

    if args.command == "platforms":
        show_platforms()
    elif args.command == "test-eval":
        run_test_eval()
    elif args.command == "scan":
        run_scan(platform=args.platform, limit=args.limit)
