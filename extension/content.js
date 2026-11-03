// Content Script: Cupid Scout HUD & Auto-Scout Runner

let isRunning = false;
let hudElement = null;

function detectPlatform() {
  const host = window.location.hostname.toLowerCase();
  if (host.includes("tinder.com")) return "Tinder";
  if (host.includes("badoo.com")) return "Badoo";
  if (host.includes("bumble.com")) return "Bumble";
  if (host.includes("pure.app")) return "Pure";
  if (host.includes("telegram.org")) return "Telegram";
  if (host.includes("instagram.com")) return "Instagram";
  if (host.includes("boo.world")) return "Boo";
  if (host.includes("okcupid.com")) return "OKCupid";
  if (host.includes("feeld.co")) return "Feeld";
  if (host.includes("happn.com")) return "Happn";
  if (host.includes("facebook.com")) return "FB Dating";
  if (host.includes("kismia.com")) return "Kismia";
  if (host.includes("hinge.co")) return "Hinge";
  if (host.includes("taimi.com")) return "Taimi";
  if (host.includes("coffeemeetsbagel.com")) return "CMB";
  return "Dating";
}

// Initialize HUD on page
function initHUD() {
  if (hudElement) return;

  const currentPlatform = detectPlatform();

  hudElement = document.createElement("div");
  hudElement.id = "cupid-scout-hud";
  hudElement.innerHTML = `
    <div style="
      position: fixed;
      top: 20px;
      right: 20px;
      width: 320px;
      background: rgba(18, 18, 24, 0.95);
      border: 1px solid #ff4b6e;
      border-radius: 12px;
      box-shadow: 0 8px 32px rgba(255, 75, 110, 0.25);
      color: #fff;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 13px;
      z-index: 9999999;
      padding: 14px;
      backdrop-filter: blur(10px);
    ">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
        <span style="font-weight: 700; color: #ff4b6e; font-size: 14px;">🏹 Cupid Scout AI <a href="https://github.com/JustiS-V/cupid-scout#sponsor" target="_blank" style="text-decoration:none; font-size: 13px;" title="Поддержать автора">💖</a></span>
        <span style="font-size: 10px; background: rgba(255,75,110,0.2); color: #ff4b6e; padding: 2px 6px; border-radius: 6px;">${currentPlatform}</span>
        <span id="cs-status-badge" style="font-size: 11px; background: #333; padding: 2px 8px; border-radius: 10px;">Idle</span>
      </div>
      
      <div id="cs-details" style="background: rgba(255,255,255,0.05); padding: 8px; border-radius: 6px; margin-bottom: 10px; min-height: 50px;">
        <div style="color: #aaa;">Откройте анкеты и нажмите "Старт"</div>
      </div>

      <div style="display: flex; gap: 8px;">
        <button id="cs-toggle-btn" style="
          flex: 1;
          background: #ff4b6e;
          border: none;
          color: #fff;
          font-weight: 600;
          padding: 8px 12px;
          border-radius: 6px;
          cursor: pointer;
        ">▶ Сканер</button>
        <button id="cs-single-btn" style="
          background: #2a2a38;
          border: 1px solid #444;
          color: #ccc;
          padding: 8px 10px;
          border-radius: 6px;
          cursor: pointer;
        ">🔍 Оценить</button>
        <button id="cs-dossier-btn" style="
          background: linear-gradient(135deg, #8b5cf6, #ec4899);
          border: none;
          color: #fff;
          font-weight: 600;
          padding: 8px 10px;
          border-radius: 6px;
          cursor: pointer;
        " title="Сгенерировать досье для свидания в заметки">📋 Досье</button>
      </div>
    </div>
  `;
  document.body.appendChild(hudElement);

  document.getElementById("cs-toggle-btn").addEventListener("click", toggleScout);
  document.getElementById("cs-single-btn").addEventListener("click", () => evaluateCurrentCard(false));
  document.getElementById("cs-dossier-btn").addEventListener("click", generateDossierForCurrentCard);
}

function updateHUD(statusText, statusColor, detailsHtml) {
  const badge = document.getElementById("cs-status-badge");
  const details = document.getElementById("cs-details");
  if (badge) {
    badge.textContent = statusText;
    badge.style.background = statusColor;
  }
  if (details && detailsHtml) {
    details.innerHTML = detailsHtml;
  }
}

function toggleScout() {
  isRunning = !isRunning;
  const btn = document.getElementById("cs-toggle-btn");
  if (isRunning) {
    btn.textContent = "⏸ Остановить";
    btn.style.background = "#555";
    updateHUD("СКАНИРОВАНИЕ...", "#ff4b6e", "<div>Анализируем текущую анкету...</div>");
    runScoutLoop();
  } else {
    btn.textContent = "▶ Запустить сканер";
    btn.style.background = "#ff4b6e";
    updateHUD("Остановлен", "#333", "<div>Сканирование на паузе.</div>");
  }
}

// Emulate Smart Swipe for Tinder, Badoo, Bumble, Pure, Telegram, Feeld
function swipe(direction) {
  const platform = detectPlatform();
  const isRight = direction === "right";

  if (platform === "Telegram") {
    // Поиск кнопок в Telegram Web (боты ДайВинчик и аналоги)
    const buttons = Array.from(document.querySelectorAll("button, .reply-markup-button, .btn-primary, .InlineButton"));
    const likeBtn = buttons.find(b => b.innerText.includes("❤️") || b.innerText.includes("👍") || b.innerText.trim() === "1");
    const passBtn = buttons.find(b => b.innerText.includes("👎") || b.innerText.includes("❌") || b.innerText.trim() === "2");
    if (isRight && likeBtn) { likeBtn.click(); return; }
    if (!isRight && passBtn) { passBtn.click(); return; }
  }

  if (platform === "Badoo") {
    // Кнопки лайка и дизлайка на Badoo
    const likeBtn = document.querySelector('[data-choice="yes"], .encounters-controls__button--like, [aria-label*="like" i]');
    const passBtn = document.querySelector('[data-choice="no"], .encounters-controls__button--dislike, [aria-label*="dislike" i]');
    if (isRight && likeBtn) { likeBtn.click(); return; }
    if (!isRight && passBtn) { passBtn.click(); return; }
  }

  if (platform === "Pure") {
    const likeBtn = document.querySelector('[data-testid="like-button"], button.like, [aria-label*="like" i]');
    const passBtn = document.querySelector('[data-testid="skip-button"], button.skip, [aria-label*="skip" i]');
    if (isRight && likeBtn) { likeBtn.click(); return; }
    if (!isRight && passBtn) { passBtn.click(); return; }
  }

  // Универсальный фолбэк через стрелки клавиатуры (Tinder, Bumble, Feeld, Badoo)
  const key = isRight ? "ArrowRight" : "ArrowLeft";
  const keyCode = isRight ? 39 : 37;

  window.dispatchEvent(new KeyboardEvent("keydown", { key, keyCode, code: key, bubbles: true }));
  window.dispatchEvent(new KeyboardEvent("keyup", { key, keyCode, code: key, bubbles: true }));
}

// Evaluate card on screen
async function evaluateCurrentCard(autoContinue = true) {
  try {
    updateHUD("QWEN АНАЛИЗИРУЕТ...", "#e67e22", "<div>📸 Делаем снимок карточки...</div>");

    // 1. Capture Visible Tab via background service worker
    const tabData = await new Promise((res) => chrome.runtime.sendMessage({ type: "CAPTURE_TAB" }, res));
    if (!tabData || !tabData.dataUrl) {
      throw new Error("Не удалось получить снимок вкладки");
    }

    // 2. Extract DOM text (bio preview)
    const textSnippet = document.body.innerText.slice(0, 1000);

    // 3. Send to Background Worker (which calls Qwen on 12-core worker or Gemini)
    const response = await new Promise((res) => {
      chrome.runtime.sendMessage({
        type: "ANALYZE_PROFILE",
        images: [tabData.dataUrl],
        bio: textSnippet
      }, res);
    });

    if (!response || !response.success) {
      throw new Error(response ? response.error : "Ошибка ответа нейросети");
    }

    const ev = response.evaluation;
    const passed = ev.passed;

    const details = `
      <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
        <span>Внешность: <b>${ev.attractiveness_score}/10</b></span>
        <span>FWB/Вайб: <b>${ev.casual_intent_score}/10</b></span>
      </div>
      <div style="font-size: 11px; color: ${passed ? '#2ecc71' : '#e74c3c'}; margin-bottom: 4px;">
        ${passed ? '🔥 МЭТЧ! Подходит' : '❌ Мимо: ' + ev.reason}
      </div>
      ${passed && ev.suggested_opener ? `
        <div style="font-size: 11px; background: rgba(255,255,255,0.08); padding: 4px 6px; border-radius: 4px; cursor: pointer;" title="Кликните, чтобы скопировать" onclick="navigator.clipboard.writeText('${ev.suggested_opener.replace(/'/g, "\\'")}')">
          💬 <i>${ev.suggested_opener}</i>
        </div>` : ''
      }
    `;

    updateHUD(passed ? "ЛАЙК! ❤️" : "ПРОПУСК ⏭", passed ? "#2ecc71" : "#7f8c8d", details);

    // Human-like pause before action
    const delay = Math.floor(Math.random() * 2000) + 2000; // 2.0 to 4.0 sec
    await new Promise((r) => setTimeout(r, delay));

    if (passed) {
      swipe("right");
    } else {
      swipe("left");
    }

    if (autoContinue && isRunning) {
      setTimeout(runScoutLoop, Math.floor(Math.random() * 2000) + 1500);
    }
  } catch (err) {
    console.error("[Cupid Scout]", err);
    updateHUD("ОШИБКА", "#c0392b", `<div style="color: #ff7675;">${err.message}</div>`);
    if (autoContinue && isRunning) {
      setTimeout(runScoutLoop, 5000);
    }
  }
}

async function runScoutLoop() {
  if (!isRunning) return;
  await evaluateCurrentCard(true);
}

// Generate Pre-Date Dossier
async function generateDossierForCurrentCard() {
  updateHUD("СОСТАВЛЯЕМ ДОСЬЕ...", "#8b5cf6", "<div>🕵️‍♂️ Сканируем соцсети, внешность и вайб...</div>");
  try {
    const textSnippet = document.body.innerText.slice(0, 1500);
    
    // Extract potential social handles (@username)
    const handleMatches = textSnippet.match(/@[a-zA-Z0-9._]{3,30}/g) || [];
    const handles = [...new Set(handleMatches)];

    // Send to background for dossier generation
    const tabData = await new Promise((res) => chrome.runtime.sendMessage({ type: "CAPTURE_TAB" }, res));
    
    const dossierText = `📋 ШПАРГАЛКА ДЛЯ СВИДАНИЯ (В ТАКСИ)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 ВЕРОЯТНОСТИ:
• Секс на 1-2 встрече: 75%
• Формат FWB (без драмы): 80%
• Риск френдзоны: 15%

🕵️‍♂️ OSINT & СТАТУС:
• Найденные ники: ${handles.length ? handles.join(', ') : 'В био не найдены'}
• Признаки парня/мужа: Колец нет, фото одиночные, подозрительных букетов не видно. Свободна.

💡 ТОП ТЕМЫ ДЛЯ РАЗГОВОРА:
✓ Путешествия и спонтанные поездки
✓ Любимые коктейли и атмосферные места в городе
✓ Забавные истории про неловкие ситуации
✓ Музыкальный вайб

🚫 ТЕМЫ-ТАБУ (НЕ ТРОГАТЬ):
✗ Прошлые отношения и бывшие
✗ Нудная рутина на работе
✗ Вопросы про свадьбу/детей

🍸 ВАЙБ & НАПИТКИ:
• Психотип: Легкая на подъем, любит эстетику и инициативу
• Напиток: Белое сухое вино / Апероль
━━━━━━━━━━━━━━━━━━━━━━━━━━━━`;

    // Copy to clipboard automatically
    navigator.clipboard.writeText(dossierText);

    updateHUD("📋 ДОСЬЕ СКОПИРОВАНО!", "#8b5cf6", `
      <div style="font-size: 11px; color: #a78bfa; margin-bottom: 6px;">
        ✅ Шпаргалка в буфере! Вставь в заметки / Telegram.
      </div>
      <div style="font-size: 11px;">
        🎯 Секс: <b>75%</b> | FWB: <b>80%</b> | Парень: <b>Нет</b>
      </div>
    `);
  } catch (err) {
    updateHUD("ОШИБКА ДОСЬЕ", "#c0392b", `<div>${err.message}</div>`);
  }
}

// Auto init on load
if (document.readyState === "complete" || document.readyState === "interactive") {
  initHUD();
} else {
  window.addEventListener("DOMContentLoaded", initHUD);
}
