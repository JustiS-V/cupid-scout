// Content Script: Cupid Scout HUD & Auto-Scout Runner

let isRunning = false;
let hudElement = null;

// Initialize HUD on page
function initHUD() {
  if (hudElement) return;

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
        ">▶ Запустить сканер</button>
        <button id="cs-single-btn" style="
          background: #2a2a38;
          border: 1px solid #444;
          color: #ccc;
          padding: 8px 10px;
          border-radius: 6px;
          cursor: pointer;
        ">🔍 Оценить 1</button>
      </div>
    </div>
  `;
  document.body.appendChild(hudElement);

  document.getElementById("cs-toggle-btn").addEventListener("click", toggleScout);
  document.getElementById("cs-single-btn").addEventListener("click", () => evaluateCurrentCard(false));
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

// Emulate Keyboard Swipe
function swipe(direction) {
  const key = direction === "right" ? "ArrowRight" : "ArrowLeft";
  const keyCode = direction === "right" ? 39 : 37;

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

// Auto init on load
if (document.readyState === "complete" || document.readyState === "interactive") {
  initHUD();
} else {
  window.addEventListener("DOMContentLoaded", initHUD);
}
