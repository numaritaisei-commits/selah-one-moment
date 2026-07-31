"use strict";

const $ = (selector) => document.querySelector(selector);
const composer = $("#composer");
const draft = $("#draft");
const charCount = $("#char-count");
const pausePanel = $("#pause-panel");
const countdownView = $("#countdown-view");
const reflectionView = $("#reflection-view");
const errorView = $("#error-view");
const modeBadge = $("#mode-badge");
let timerId = null;
let sessionToken = "";
let busy = false;

function setHidden(element, hidden) {
  element.classList.toggle("hidden", hidden);
}

function updateCount() {
  charCount.textContent = `${draft.value.length} / 2000`;
}

function showComposer() {
  if (timerId !== null) window.clearInterval(timerId);
  timerId = null;
  setHidden(pausePanel, true);
  composer.classList.remove("dimmed");
  busy = false;
  $("#pause").disabled = false;
  draft.focus();
}

function showError() {
  setHidden(countdownView, true);
  setHidden(reflectionView, true);
  setHidden(errorView, false);
}

function safeText(selector, value) {
  $(selector).textContent = typeof value === "string" ? value : "";
}

function showReflection(result) {
  setHidden(countdownView, true);
  setHidden(errorView, true);
  setHidden(reflectionView, false);
  safeText("#reflection-question", result.reflection_question);
  safeText("#provider-note", result.notice);

  const passageCard = $("#passage-card");
  const offlineNotice = $("#offline-notice");
  const liveProof = $("#live-proof");
  if (result.mode === "live" && result.passage) {
    setHidden(passageCard, false);
    setHidden(offlineNotice, true);
    setHidden(liveProof, false);
    safeText("#passage-content", result.passage.content);
    safeText("#passage-reference", result.passage.reference);
    safeText(
      "#passage-version",
      `${result.passage.version_title} (${result.passage.version})`,
    );
    safeText("#passage-copyright", result.passage.copyright);
    const link = $("#passage-link");
    link.href = result.passage.youversion_url;
  } else {
    setHidden(passageCard, true);
    setHidden(offlineNotice, false);
    setHidden(liveProof, true);
    offlineNotice.textContent =
      "Offline preview intentionally shows no verse. Live mode displays only text and attribution returned by YouVersion.";
  }
}

async function requestReflection() {
  if (!sessionToken) throw new Error("missing local session");
  const intent = $("input[name='intent']:checked").value;
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 65000);
  try {
    const response = await fetch("/api/reflect", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Selah-Session": sessionToken },
      cache: "no-store",
      credentials: "omit",
      signal: controller.signal,
      body: JSON.stringify({ draft: draft.value, intent }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error("fail-open");
    showReflection(payload);
  } finally {
    window.clearTimeout(timeout);
  }
}

function beginPause() {
  composer.classList.add("dimmed");
  setHidden(pausePanel, false);
  setHidden(countdownView, false);
  setHidden(reflectionView, true);
  setHidden(errorView, true);
  let remaining = 8;
  $("#countdown").textContent = String(remaining);
  timerId = window.setInterval(async () => {
    remaining -= 1;
    $("#countdown").textContent = String(Math.max(remaining, 0));
    if (remaining > 0) return;
    window.clearInterval(timerId);
    timerId = null;
    try {
      await requestReflection();
    } catch (_) {
      showError();
    }
  }, 1000);
}

composer.addEventListener("submit", (event) => {
  event.preventDefault();
  if (busy || !draft.value.trim()) {
    draft.focus();
    return;
  }
  busy = true;
  $("#pause").disabled = true;
  beginPause();
});

draft.addEventListener("input", updateCount);
$("#skip").addEventListener("click", showComposer);
$("#post-now").addEventListener("click", showComposer);
$("#continue").addEventListener("click", showComposer);
$("#error-return").addEventListener("click", showComposer);
$("#edit").addEventListener("click", () => {
  showComposer();
  draft.select();
});

fetch("/api/status", { cache: "no-store", credentials: "omit" })
  .then((response) => response.json())
  .then((data) => {
    sessionToken = typeof data.session_token === "string" ? data.session_token : "";
    const live = data.mode === "live";
    modeBadge.textContent = live ? "LIVE · GLOO + YOUVERSION" : "OFFLINE PREVIEW";
    modeBadge.classList.toggle("live", live);
  })
  .catch(() => {
    modeBadge.textContent = "LOCAL DEMO";
  });

updateCount();
