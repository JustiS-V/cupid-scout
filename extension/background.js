// Background Service Worker for Cupid Scout Extension

const DEFAULT_SETTINGS = {
  provider: "worker_lms", // "worker_lms", "gemini", "openai"
  lmsUrl: "http://127.0.0.1:1234/v1",
  lmsModel: "media-vision",
  geminiKey: "",
  openaiKey: "",
  minAttractiveness: 7.0,
  minIntent: 6.0,
  autoSwipe: true
};

const SYSTEM_PROMPT = `
You are an expert visual profile scout for casual dating and ONS/FWB.
Evaluate candidate strictly from photo and visible bio text.
User criteria: attractive face, natural beauty, fit body, open casual vibe.
Red flags: no real face, memes/animals/nature, heavy distortion filters, seeking marriage/serious only, social media handle baiting.

Return STRICT JSON:
{
  "has_real_person": true,
  "face_visible": true,
  "attractiveness_score": 8.5,
  "casual_intent_score": 8.0,
  "vibe_type": "casual_party",
  "is_match": true,
  "reason": "Cute girl, casual vibe, meets criteria.",
  "suggested_opener": "Hey! Loved the vibe in your photo, how's your evening going?"
}
`;

// Helper: Call LM Studio / Qwen
async function callLMStudio(images, bio, settings) {
  const content = [
    { type: "text", text: `Candidate bio/text: ${bio || "Empty"}` }
  ];

  for (const imgUrl of images) {
    content.push({
      type: "image_url",
      image_url: { url: imgUrl }
    });
  }

  const payload = {
    model: settings.lmsModel || "media-vision",
    temperature: 0.2,
    max_tokens: 600,
    messages: [
      { role: "system", content: SYSTEM_PROMPT },
      { role: "user", content: content }
    ]
  };

  const url = `${settings.lmsUrl.replace(/\/+$/, "")}/chat/completions`;
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!resp.ok) {
    throw new Error(`LM Studio HTTP ${resp.status}: ${await resp.text()}`);
  }

  const body = await resp.json();
  let text = body.choices[0].message.content.trim();
  text = text.replace(/<think>[\s\S]*?<\/think>/g, "").trim();
  if (text.includes("```json")) {
    text = text.split("```json")[1].split("```")[0].trim();
  } else if (text.includes("```")) {
    text = text.split("```")[1].split("```")[0].trim();
  }

  return JSON.parse(text);
}

// Helper: Call Gemini Flash
async function callGemini(images, bio, settings) {
  const apiKey = settings.geminiKey;
  if (!apiKey) throw new Error("Gemini API Key is missing in settings");

  const parts = [{ text: `${SYSTEM_PROMPT}\n\nCandidate bio: ${bio || "Empty"}` }];
  for (const imgUrl of images) {
    if (imgUrl.startsWith("data:")) {
      const match = imgUrl.match(/^data:(image\/\w+);base64,(.+)$/);
      if (match) {
        parts.push({
          inline_data: { mime_type: match[1], data: match[2] }
        });
      }
    }
  }

  const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${apiKey}`;
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ contents: [{ parts }] })
  });

  if (!resp.ok) {
    throw new Error(`Gemini HTTP ${resp.status}: ${await resp.text()}`);
  }

  const body = await resp.json();
  let text = body.candidates[0].content.parts[0].text.trim();
  if (text.includes("```json")) {
    text = text.split("```json")[1].split("```")[0].trim();
  } else if (text.includes("```")) {
    text = text.split("```")[1].split("```")[0].trim();
  }
  return JSON.parse(text);
}

// Message Router
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "CAPTURE_TAB") {
    chrome.tabs.captureVisibleTab(null, { format: "jpeg", quality: 85 }, (dataUrl) => {
      sendResponse({ dataUrl });
    });
    return true; // async
  }

  if (message.type === "ANALYZE_PROFILE") {
    (async () => {
      try {
        const stored = await chrome.storage.local.get(DEFAULT_SETTINGS);
        let result = null;

        if (stored.provider === "gemini") {
          result = await callGemini(message.images, message.bio, stored);
        } else {
          result = await callLMStudio(message.images, message.bio, stored);
        }

        const passed = (result.attractiveness_score >= stored.minAttractiveness) &&
                       (result.casual_intent_score >= stored.minIntent) &&
                       (result.is_match === true);

        result.passed = passed;
        sendResponse({ success: true, evaluation: result });
      } catch (err) {
        console.error("[Cupid Scout BG] Error:", err);
        sendResponse({ success: false, error: err.message });
      }
    })();
    return true; // async
  }
});
