import os
import time
import json
import sqlite3
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path("/Users/val9/Desktop/Process/dating-ai-agent")
MATCHES_DATA_DIR = BASE_DIR / "data" / "mutual_matches"
MATCHES_DATA_DIR.mkdir(parents=True, exist_ok=True)
CHAT_LOGS_FILE = BASE_DIR / "data" / "chat_logs.jsonl"
DB_PATH = BASE_DIR / "data" / "dating.db"

def init_chat_tables():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mutual_matches (
                match_id TEXT PRIMARY KEY,
                platform TEXT,
                name TEXT,
                age INTEGER,
                looking_for TEXT,
                bio TEXT,
                match_date TEXT,
                profile_url TEXT,
                screenshot_path TEXT,
                total_messages INTEGER DEFAULT 0,
                last_message_text TEXT,
                last_sender TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id TEXT,
                sender TEXT,
                message_text TEXT,
                sent_at TEXT,
                ai_suggested INTEGER DEFAULT 0,
                status TEXT
            )
        """)
        conn.commit()

def extract_match_profile(page, match_href):
    """Navigates to match link and extracts full profile and message history"""
    try:
        # Click on match in sidebar or navigate directly
        page.click(f'a[href="{match_href}"]')
    except Exception:
        page.goto(f"https://tinder.com{match_href}", wait_until="domcontentloaded")
    
    time.sleep(2.0)
    
    match_id = match_href.split("/")[-1]
    screenshot_path = MATCHES_DATA_DIR / f"match_{match_id}.jpg"
    
    try:
        page.screenshot(path=str(screenshot_path), quality=80, type="jpeg")
    except Exception as e:
        print(f"Screenshot error: {e}")

    # Extract all text, bio, details, messages from the DOM
    data = page.evaluate("""() => {
        const bodyText = document.body.innerText;
        
        // Find profile sidebar / details panel
        // Name and age usually rendered like 'Julia24' or in heading
        let name = '';
        let age = null;
        let lookingFor = '';
        let bio = '';
        let matchDate = '';
        
        // Search match date
        const dateMatch = bodyText.match(/Ти створив\/-ла пару з .*?!(.*?)\\n/i) || bodyText.match(/Ти став\/-ла парою.*?(\\d{2}\\.\\d{2}\\.\\d{4})/i);
        if (dateMatch) {
            matchDate = dateMatch[0].trim();
        }
        
        // Search looking for
        const lookingMatch = bodyText.match(/Я шукаю\\s*\\n[\\s\\S]*?\\n(.*?)\\n/i);
        if (lookingMatch) {
            lookingFor = lookingMatch[1].trim();
        }
        
        // Search bio
        const bioMatch = bodyText.match(/Про мене\\s*\\n([\\s\\S]*?)(?:\\n[А-ЯA-Z]|\\nШукаю|\\nСпільні|\\nІнтереси|$)/i);
        if (bioMatch) {
            bio = bioMatch[1].trim();
        }
        
        // Name & Age header (e.g. Julia24 or 'Julia 24')
        const headerEl = Array.from(document.querySelectorAll('h1, div')).find(el => {
            const t = el.innerText.trim();
            return /^[A-Za-zА-Яа-яЁёЇїІіЄєҐґ]{2,20}\\s*\\d{2}$/.test(t);
        });
        if (headerEl) {
            const raw = headerEl.innerText.trim();
            const m = raw.match(/^([A-Za-zА-Яа-яЁёЇїІіЄєҐґ]{2,20})\\s*(\\d{2})$/);
            if (m) {
                name = m[1];
                age = parseInt(m[2]);
            }
        }
        
        // Check message bubbles
        const messageElements = Array.from(document.querySelectorAll('[data-testid="message-text"], [role="listitem"], .messageListItem, .msgText, .text-message'));
        const messages = [];
        // Alternative: look for messages in chat container
        return {
            name,
            age,
            lookingFor,
            bio,
            matchDate,
            bodyText: bodyText.slice(0, 3000)
        };
    }""")

    return {
        "match_id": match_id,
        "match_href": match_href,
        "name": data.get("name") or "Girl",
        "age": data.get("age"),
        "looking_for": data.get("lookingFor") or "",
        "bio": data.get("bio") or "",
        "match_date": data.get("matchDate") or "",
        "screenshot_path": str(screenshot_path),
        "raw_snippet": data.get("bodyText", "")[:1000]
    }

def scan_all_matches():
    init_chat_tables()
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        tinder_page = [page for page in context.pages if "tinder.com" in page.url][0]

        # Пытаемся переключиться на вкладку 'Пари'
        try:
            tinder_page.evaluate("""() => {
                const tabs = Array.from(document.querySelectorAll('button[role="tab"]'));
                const matchesTab = tabs.find(t => t.innerText.includes('Пари') || t.innerText.includes('Matches'));
                if (matchesTab) matchesTab.click();
            }""")
            time.sleep(1.5)
        except Exception:
            pass

        # Get list of links (messages and matches)
        match_links = tinder_page.evaluate("""() => {
            const links = Array.from(document.querySelectorAll('a[href*="/app/messages/"], a[href*="/app/matches/"]')).map(a => a.getAttribute('href'));
            return links;
        }""")

        unique_links = list(dict.fromkeys(match_links))
        print(f"Найдено взаимных мэтчей: {len(unique_links)}")

        results = []
        for idx, href in enumerate(unique_links, 1):
            print(f"\n[{idx}/{len(unique_links)}] Анализ мэтча: {href} ...")
            info = extract_match_profile(tinder_page, href)
            results.append(info)
            print(f"  -> Имя: {info['name']}, Возраст: {info['age']}")
            print(f"  -> Шукає: {info['looking_for']}")
            print(f"  -> Био: {info['bio'][:60]}...")
            
            # Save into SQLite
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO mutual_matches (
                        match_id, platform, name, age, looking_for, bio,
                        match_date, profile_url, screenshot_path, total_messages,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """, (
                    info["match_id"],
                    "tinder_web",
                    info["name"],
                    info["age"],
                    info["looking_for"],
                    info["bio"],
                    info["match_date"],
                    f"https://tinder.com{href}",
                    info["screenshot_path"],
                    0
                ))
                conn.commit()
            
            # Log to JSONL
            with open(CHAT_LOGS_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "event": "match_discovered",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "match": info
                }, ensure_ascii=False) + "\n")
            
            time.sleep(1.5)

        # Return back to recs after inspection
        tinder_page.goto("https://tinder.com/app/recs", wait_until="domcontentloaded")
        print("\n✅ Сканирование всех мэтчей завершено! Страница возвращена на /app/recs")
        return results

if __name__ == "__main__":
    scan_all_matches()
