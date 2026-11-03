document.addEventListener("DOMContentLoaded", async () => {
  const providerSelect = document.getElementById("provider");
  const lmsConfig = document.getElementById("lms-config");
  const geminiConfig = document.getElementById("gemini-config");
  const openaiConfig = document.getElementById("openai-config");

  const lmsUrlInput = document.getElementById("lmsUrl");
  const lmsModelInput = document.getElementById("lmsModel");
  const geminiKeyInput = document.getElementById("geminiKey");
  const openaiKeyInput = document.getElementById("openaiKey");

  const minAttrSlider = document.getElementById("minAttractiveness");
  const minIntentSlider = document.getElementById("minIntent");
  const attrVal = document.getElementById("attr-val");
  const intentVal = document.getElementById("intent-val");

  const saveBtn = document.getElementById("saveBtn");
  const statusMsg = document.getElementById("statusMsg");

  // Load saved settings
  const data = await chrome.storage.local.get({
    provider: "worker_lms",
    lmsUrl: "http://127.0.0.1:1234/v1",
    lmsModel: "media-vision",
    geminiKey: "",
    openaiKey: "",
    minAttractiveness: 7.0,
    minIntent: 6.0
  });

  providerSelect.value = data.provider;
  lmsUrlInput.value = data.lmsUrl;
  lmsModelInput.value = data.lmsModel;
  geminiKeyInput.value = data.geminiKey;
  openaiKeyInput.value = data.openaiKey;

  minAttrSlider.value = data.minAttractiveness;
  attrVal.textContent = Number(data.minAttractiveness).toFixed(1);

  minIntentSlider.value = data.minIntent;
  intentVal.textContent = Number(data.minIntent).toFixed(1);

  function updateVisibility() {
    const val = providerSelect.value;
    lmsConfig.style.display = (val === "worker_lms" || val === "local_lms") ? "block" : "none";
    geminiConfig.style.display = (val === "gemini") ? "block" : "none";
    openaiConfig.style.display = (val === "openai") ? "block" : "none";
  }

  updateVisibility();
  providerSelect.addEventListener("change", updateVisibility);

  minAttrSlider.addEventListener("input", (e) => {
    attrVal.textContent = Number(e.target.value).toFixed(1);
  });

  minIntentSlider.addEventListener("input", (e) => {
    intentVal.textContent = Number(e.target.value).toFixed(1);
  });

  saveBtn.addEventListener("click", async () => {
    await chrome.storage.local.set({
      provider: providerSelect.value,
      lmsUrl: lmsUrlInput.value.trim(),
      lmsModel: lmsModelInput.value.trim(),
      geminiKey: geminiKeyInput.value.trim(),
      openaiKey: openaiKeyInput.value.trim(),
      minAttractiveness: parseFloat(minAttrSlider.value),
      minIntent: parseFloat(minIntentSlider.value)
    });

    statusMsg.textContent = "✅ Настройки сохранены!";
    setTimeout(() => { statusMsg.textContent = ""; }, 2000);
  });
});
