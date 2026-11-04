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
        console.print("\n[bold green]Рекомендация:[/bold green] Используйте [bold]tinder_web[/bold] через Google Chrome с отладчиком или [bold]badoo_web[/bold].\n")
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

def show_matches():
    """Показать список взаимных мэтчей из базы"""
    import sqlite3
    from core.storage import DB_PATH
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, age, looking_for, bio, profile_url FROM mutual_matches ORDER BY updated_at DESC")
        rows = cursor.fetchall()
        
    print("\n" + "="*95)
    print("🔥 ВЗАИМНЫЕ МЭТЧИ (TINDER / DATING):")
    print("="*95)
    print(f"{'Имя, Возраст':<18} | {'Что ищет':<25} | {'Био анкеты':<45}")
    print("="*95)
    for r in rows:
        name_age = f"{r[0] or 'Девушка'}, {r[1] or '?'}"
        looking = (r[2][:23] + "..") if r[2] and len(r[2]) > 23 else (r[2] or "Не указано")
        bio = (r[3][:42] + "..") if r[3] and len(r[3]) > 42 else (r[3] or "Пусто")
        print(f"{name_age:<18} | {looking:<25} | {bio:<45}")
    print("="*95 + "\n")

def run_chat():
    """Генерация и просмотр оупенеров/сообщений для мэтчей"""
    from core.chat_generator import ChatGenerator
    generator = ChatGenerator()
    generator.process_all_matches()

def show_analytics():
    """Показать аналитику поведения девушек в чатах"""
    from core.analytics import BehavioralAnalyticsManager, DB_PATH, ANALYTICS_REPORT_MD
    import sqlite3
    mgr = BehavioralAnalyticsManager()
    mgr.generate_full_report()
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT name, age, conversion_stage, her_avg_response_time_min, investment_ratio, questions_asked_by_her, behavior_archetype FROM behavioral_profiles ORDER BY her_messages_count DESC")
        rows = cursor.fetchall()

    print("\n" + "="*105)
    print("📊 ПОВЕДЕНЧЕСКАЯ АНАЛИТИКА ДИАЛОГОВ (CUPID SCOUT BEHAVIORAL INTEL):")
    print("="*105)
    print(f"{'Кандидатка':<18} | {'Статус':<14} | {'Время ответа':<14} | {'Вклад (IR)':<12} | {'Вопросы':<8} | {'Поведенческий Архетип'}")
    print("="*105)
    for r in rows:
        name_age = f"{r['name']}, {r['age'] or '?'}"
        rt = f"{r['her_avg_response_time_min']} мин" if r['her_avg_response_time_min'] is not None else "ожидание"
        ir = f"{r['investment_ratio']:.2f}x"
        print(f"{name_age:<18} | {r['conversion_stage']:<14} | {rt:<14} | {ir:<12} | {r['questions_asked_by_her']:<8} | {r['behavior_archetype']}")
    print("="*105)
    print(f"\n📄 Полный аналитический отчет сформирован: {ANALYTICS_REPORT_MD}\n")

def run_auto_swipe(limit: int = 100):
    """Свайпать до полного исчерпания суточного лимита Tinder"""
    from core.auto_swiper import run_auto_exhaustion
    run_auto_exhaustion(max_swipes=limit)

def run_autonomous_loop(limit: int = 50):
    """Автономный цикл: свайпаем, при взаимном мэтче сразу пишем первое сообщение"""
    from core.autonomous_match_swiper import AutonomousMatchSwiper
    agent = AutonomousMatchSwiper()
    agent.run(max_swipes=limit)

def show_social_funnel():
    """Показать воронку развития личных соцсетей (Instagram, Threads, TikTok, Telegram)"""
    from core.social_funnel import SocialFunnelManager, REPORT_PATH
    import sqlite3
    from core.social_funnel import DB_PATH

    mgr = SocialFunnelManager()
    mgr.scan_existing_profiles_for_leads()
    mgr.generate_full_report()

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM social_leads")
        total_leads = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM social_transitions")
        total_transitions = c.fetchone()[0]
        c.execute("SELECT * FROM social_leads ORDER BY id DESC LIMIT 10")
        leads = c.fetchall()

    print("\n" + "="*95)
    print("🚀 ВОРОНКА РАЗВИТИЯ СОЦСЕТЕЙ ЧЕРЕЗ ТИНДЕР (INSTAGRAM / THREADS / TIKTOK / TELEGRAM):")
    print("="*95)
    print(f"• Всего предложено переходов в соцсети: {total_transitions}")
    print(f"• Всего собрано контактов/лидов кандидаток: {total_leads}")
    print("="*95)
    print(f"{'Кандидатка':<18} | {'Сеть':<10} | {'Никнейм':<20} | {'Источник':<15} | {'Статус'}")
    print("="*95)
    if not leads:
        print("  Пока нет зафиксированных переходов. Агент начнет предлагать соцсети на Turn 2-3 диалога!")
    else:
        for l in leads:
            name_age = f"{l['candidate_name']}, {l['age'] or '?'}"
            print(f"{name_age:<18} | {l['network'].upper():<10} | {l['handle']:<20} | {l['source']:<15} | {l['status']}")
    print("="*95)
    print(f"\n📄 Полный интерактивный отчет с воронкой: {REPORT_PATH}\n")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Dating AI Agent")
    parser.add_argument("command", choices=["platforms", "test-eval", "scan", "stats", "history", "matches", "chat", "analytics", "auto-swipe", "loop", "social"], nargs="?", default="platforms")
    parser.add_argument("--platform", default="tinder_web", help="ID платформы")
    parser.add_argument("--limit", type=int, default=50, help="Количество анкет")
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
    elif args.command == "matches":
        show_matches()
    elif args.command == "chat":
        run_chat()
    elif args.command == "analytics":
        show_analytics()
    elif args.command == "auto-swipe":
        run_auto_swipe(limit=args.limit)
    elif args.command == "loop":
        run_autonomous_loop(limit=args.limit)
    elif args.command == "social":
        show_social_funnel()
