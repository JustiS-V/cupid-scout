import time
import random
from pathlib import Path
from adapters.browser_adapter import BrowserCDPAdapter
from core.scorer import ProfileScorer
from core.notifier import Notifier
from core.storage import StorageManager
from core.dossier import DossierGenerator
from core.quota_manager import QuotaManager

def run_auto_exhaustion(max_swipes: int = 150):
    """
    Запускает автоматический цикл свайпов и полностью вычерпывает все доступные лайки на сегодня,
    пока Tinder не покажет окно суточного лимита.
    """
    quota_mgr = QuotaManager()
    stats = quota_mgr.get_stats_last_24h("tinder_web")
    
    print("\n" + "="*75)
    print("🏹 CUPID SCOUT: АВТО-ИСЧЕРПАНИЕ ДНЕВНОГО ЛИМИТА TINDER")
    print("="*75)
    print(f"Статистика за последние 24ч: Лайков: {stats['likes_24h']} ❤️ | Скипов: {stats['skips_24h']} ⏭")
    
    if not stats["can_swipe"]:
        print(f"🛑 Сейчас действует кулдаун до {stats['cooldown_until']} (таймер: {stats['timer_string']}).")
        print("Свайпинг отложен до восстановления лимита.")
        return

    print("Подключение к браузеру Dolphin Anty (CDP: 9222)...")
    adapter = BrowserCDPAdapter(platform_name="tinder_web")
    if not adapter.connect():
        print("❌ Не удалось подключиться к браузеру.")
        return

    scorer = ProfileScorer()
    notifier = Notifier()
    storage = StorageManager()
    dossier_gen = DossierGenerator()

    swipes_done = 0
    likes_done = 0
    skips_done = 0

    print("\n🚀 Поехали! Свайпаем до исчерпания суточного лимита лайков...\n")

    for i in range(1, max_swipes + 1):
        # 1. Проверяем лимит перед каждой карточкой
        reached, timer_str = adapter.get_limit_details()
        if reached:
            print("\n🛑 ВНИМАНИЕ: Зафиксировано окно исчерпания суточного лимита Tinder!")
            quota_mgr.record_limit_hit("tinder_web", timer_string=timer_str)
            adapter.dismiss_limit_modal()
            break

        print(f"--- Анкета #{i} (Лайков в сессии: {likes_done}, Всего за 24ч: {stats['likes_24h'] + likes_done}) ---")
        try:
            profile = adapter.fetch_next_profile()
            eval_res = scorer.evaluate(profile)

            # Формируем досье
            dossier = dossier_gen.generate(profile)
            saved_id = storage.save_scan(profile, eval_res, dossier)

            print(f"👤 {profile.name}, {profile.age or '?'} | Внешность: {eval_res.attractiveness_score}/10 | FWB: {eval_res.casual_intent_score}/10")

            if eval_res.is_match:
                print("🔥 MATCH! Ставим Like ❤️")
                adapter.like(profile)
                likes_done += 1
                notifier.notify_match(profile, eval_res)
            else:
                print(f"⏭ Skip ({eval_res.reason[:45]}...)")
                adapter.dislike(profile)
                skips_done += 1

            swipes_done += 1

            # 2. Проверяем лимит сразу после лайка
            reached, timer_str = adapter.get_limit_details()
            if reached:
                print("\n🛑 ВНИМАНИЕ: Сразу после лайка появилось окно исчерпания суточного лимита!")
                quota_mgr.record_limit_hit("tinder_web", timer_string=timer_str)
                adapter.dismiss_limit_modal()
                break

            # Естественная пауза человека
            pause = random.uniform(2.2, 4.0)
            time.sleep(pause)

        except Exception as e:
            print(f"⚠️ Ошибка обработки анкеты: {e}")
            time.sleep(3.0)

    print("\n" + "="*75)
    print("🏁 СЕССИЯ АВТО-ИСЧЕРПАНИЯ ЗАВЕРШЕНА:")
    print("="*75)
    print(f"Обработано анкет в этой сессии: {swipes_done}")
    print(f"Поставлено лайков:              {likes_done} ❤️")
    print(f"Пропущено (дизлайков):          {skips_done} ⏭")
    print(f"Всего лайков за последние 24ч:  {stats['likes_24h'] + likes_done}")
    print("="*75 + "\n")

if __name__ == "__main__":
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 100
    run_auto_exhaustion(max_swipes=limit)
