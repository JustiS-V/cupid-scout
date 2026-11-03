import os
import sys
import json
import time
from pathlib import Path
from dotenv import load_dotenv
import typer
from rich.console import Console
from rich.table import Table

load_dotenv()

from core.models import ProfileData
from core.scorer import ProfileScorer
from core.notifier import Notifier
from adapters.telegram_adapter import TelegramDatingAdapter
from adapters.browser_adapter import BrowserCDPAdapter

app = typer.Typer(help="AI Dating Agent & Profile Hunter")
console = Console()

@app.command()
def platforms():
    """Показать список поддерживаемых платформ для поиска анкет"""
    config_path = Path(__file__).parent / "platforms.json"
    if not config_path.exists():
        console.print("[red]Файл platforms.json не найден![/red]")
        return

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

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

@app.command()
def test_eval():
    """Тестовый прогон оценки анкеты через LLM/Vision"""
    console.print("[bold yellow]Запуск тестовой оценки демо-профиля...[/bold yellow]")
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
    console.print(f"[bold]Оценка внешности:[/bold] {result.attractiveness_score}/10")
    console.print(f"[bold]Оценка соответствия цели (FWB/Casual):[/bold] {result.casual_intent_score}/10")
    console.print(f"[bold]Вайб:[/bold] {result.vibe_type}")
    console.print(f"[bold]Вердикт:[/bold] {result.reason}")
    console.print(f"[bold]Оупенер:[/bold] {result.suggested_opener}")

    if result.is_match:
        notifier.notify_match(dummy_profile, result)

@app.command()
def scan(
    platform: str = typer.Option("tg_leomatchbot", help="ID платформы: tg_leomatchbot, tinder_web, bumble_web"),
    limit: int = typer.Option(5, help="Сколько анкет обработать в тестовом цикле")
):
    """Запустить сканирование и отбор анкет"""
    console.print(f"[bold green]Запуск агента на платформе:[/bold green] [cyan]{platform}[/cyan]")
    scorer = ProfileScorer()
    notifier = Notifier()

    if platform.startswith("tg_"):
        adapter = TelegramDatingAdapter()
    elif "web" in platform:
        adapter = BrowserCDPAdapter(platform_name=platform)
    else:
        console.print(f"[red]Неизвестный адаптер для платформы {platform}[/red]")
        return

    adapter.connect()

    for i in range(1, limit + 1):
        console.print(f"\n--- [bold cyan]Анкета #{i}/{limit}[/bold cyan] ---")
        profile = adapter.fetch_next_profile()
        eval_res = scorer.evaluate(profile)

        console.print(f"👤 {profile.name}, {profile.age} | Оценка: [bold yellow]{eval_res.attractiveness_score}/10[/bold yellow] | FWB Score: [bold green]{eval_res.casual_intent_score}/10[/bold green]")
        
        if eval_res.is_match:
            console.print("[bold green]🔥 MATCH! Ставим лайк и отправляем уведомление[/bold green]")
            adapter.like(profile)
            notifier.notify_match(profile, eval_res)
        else:
            console.print(f"[dim]Пропуск: {eval_res.reason}[/dim]")
            adapter.dislike(profile)

        time.sleep(2.0)

    console.print("\n[bold green]Сессия сканирования завершена![/bold green]")

if __name__ == "__main__":
    app()
