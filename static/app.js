/**
 * app.js – Scheme Saathi frontend
 * Plain vanilla JS, no framework, no build step.
 * Phase 24 Voice Upgrades & Phase 25 Household / Offline Handoff UI.
 */

"use strict";

// ============================================================
// CONSTANTS & STATE
// ============================================================
const API_BASE = "";
const MAX_RECORD_MS = 60_000;
const SILENCE_TIMEOUT_MS = 1500; // auto-stop recording after 1.5s silence
const POST_RESPONSE_SILENCE_MS = 8000; // gentle prompt after 8s silence
const CHAT_REQUEST_TIMEOUT_MS = 90_000;

const session = {
  id: null,
  language: "hi",
  pendingUploadIds: [],
  activeSchemeId: null,
  playbackRate: 1.0,
  lastSpokenText: "",
  currentAudio: null,
  gentlePromptPlayed: false,
  silenceTimer: null,
  micGranted: false,
};

// ============================================================
// UI ELEMENT REFERENCES
// ============================================================
const $ = (id) => document.getElementById(id);

const els = {
  chatMessages:         $("chat-messages"),
  textInput:            $("text-input"),
  sendBtn:              $("send-btn"),
  fileInput:            $("file-input"),
  micBtn:               $("mic-btn"),
  loadingOverlay:       $("loading-overlay"),
  checklistEmpty:       $("checklist-empty"),
  checklistList:        $("checklist-list"),
  docHelpCard:          $("doc-help-card"),
  docHelpContent:       $("doc-help-content"),
  formContent:          $("form-preview-content"),
  formActions:          $("form-actions"),
  confirmBtn:           $("confirm-btn"),
  noticesBar:           $("notices-bar"),
  safetyStrip:          $("safety-strip"),
  safetyStripText:      $("safety-strip-text"),
  memberChipsContainer: $("member-chips-container"),
  addMemberBtn:         $("add-member-btn"),
  rankedSchemesCard:    $("ranked-schemes-card"),
  rankedSchemesList:    $("ranked-schemes-list"),
  nextSchemeBtn:        $("next-scheme-btn"),
  btnHandoffPacket:     $("btn-handoff-packet"),
  btnGrievanceDraft:    $("btn-grievance-draft"),
};

const langBtns = document.querySelectorAll(".lang-btn");

// ============================================================
// LANGUAGE STRINGS
// ============================================================
const UI_STRINGS = {
  hi: {
    thinking: "सोच रहा हूँ…",
    timeoutErr: "जवाब आने में बहुत समय लगा। कृपया फिर से कोशिश करें।",
    uploadOk: "📎 दस्तावेज़ अपलोड हुआ",
    uploadErr: "⚠️ अपलोड नहीं हो सका",
    micStart: "सुन रहा हूँ…",
    micErr: "माइक नहीं मिला",
    networkErr: "नेटवर्क समस्या। फिर कोशिश करें।",
    noText: "कुछ बोलें या लिखें।",
    ttsErr: "ऑडियो नहीं बजा",
    gentlePrompt: "क्या आप सुन रहे हैं? आराम से बोलिए।",
    slowerNotice: "गति धीमी की गई",
    fasterNotice: "गति तेज़ की गई",
  },
  en: {
    thinking: "Thinking…",
    timeoutErr: "The response took too long. Please try again.",
    uploadOk: "📎 Document uploaded",
    uploadErr: "⚠️ Upload failed",
    micStart: "Listening…",
    micErr: "Microphone not found",
    networkErr: "Network error. Please try again.",
    noText: "Please say or type something.",
    ttsErr: "Could not play audio",
    gentlePrompt: "Are you there? Take your time.",
    slowerNotice: "Playback slowed down",
    fasterNotice: "Playback sped up",
  },
  mr: {
    thinking: "विचार करत आहे…",
    timeoutErr: "उत्तर यायला खूप वेळ लागला. कृपया पुन्हा प्रयत्न करा.",
    uploadOk: "📎 कागदपत्र अपलोड झाले",
    uploadErr: "⚠️ अपलोड अयशस्वी",
    micStart: "ऐकत आहे…",
    micErr: "मायक्रोफोन सापडला नाही",
    networkErr: "नेटवर्क त्रुटी. पुन्हा प्रयत्न करा.",
    noText: "काहीतरी बोला किंवा लिहा.",
    ttsErr: "ऑडिओ वाजला नाही",
    gentlePrompt: "तुम्ही ऐकत आहात का? शांतपणे बोला.",
    slowerNotice: "गती कमी केली",
    fasterNotice: "गती वाढवली",
  },
  ta: {
    thinking: "சிந்திக்கிறேன்…",
    timeoutErr: "பதில் வர அதிக நேரம் ஆகிறது. மீண்டும் முயற்சிக்கவும்.",
    uploadOk: "📎 ஆவணம் பதிவேற்றப்பட்டது",
    uploadErr: "⚠️ பதிவேற்றம் தோல்வியடைந்தது",
    micStart: "கேட்கிறேன்…",
    micErr: "மைக்ரோஃபோன் கிடைக்கவில்லை",
    networkErr: "நெட்வொர்க் பிழை. மீண்டும் முயற்சிக்கவும்.",
    noText: "ஏதாவது சொல்லுங்கள் அல்லது எழுதுங்கள்.",
    ttsErr: "ஆடியோ இயக்க முடியவில்லை",
    gentlePrompt: "கேட்கிறீர்களா? தயவுசெய்து பேசுங்கள்.",
    slowerNotice: "வேகம் குறைக்கப்பட்டது",
    fasterNotice: "வேகம் அதிகரிக்கப்பட்டது",
  },
};

function t(key) {
  return (UI_STRINGS[session.language] || UI_STRINGS.hi)[key] || "";
}

// ============================================================
// SESSION INITIALIZATION
// ============================================================
async function initSession(lang = "hi") {
  session.language = lang;
  updateLangButtons(lang);

  try {
    const res = await fetch(`${API_BASE}/api/session`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ language: lang, user_id: session.id }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    session.id = data.session_id;

    clearChat();
    appendBotBubble(data.greeting);
    await playTTS(data.greeting);

    // Refresh household members
    await fetchHousehold();
  } catch (err) {
    console.error("Init session error:", err);
    showToast(t("networkErr"));
  }
}

function updateLangButtons(lang) {
  langBtns.forEach((btn) => {
    const active = btn.dataset.lang === lang;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-pressed", String(active));
  });
}

langBtns.forEach((btn) => {
  btn.addEventListener("click", () => {
    const lang = btn.dataset.lang;
    if (lang !== session.language) {
      initSession(lang);
    }
  });
});

// ============================================================
// CHAT RENDERING
// ============================================================
function clearChat() {
  els.chatMessages.innerHTML = "";
}

function appendUserBubble(text) {
  const div = document.createElement("div");
  div.className = "chat-bubble user-bubble";
  div.textContent = text;
  els.chatMessages.appendChild(div);
  scrollToBottom();
}

function appendBotBubble(text) {
  const div = document.createElement("div");
  div.className = "chat-bubble bot-bubble";
  div.innerHTML = formatBotMessage(text);
  els.chatMessages.appendChild(div);
  scrollToBottom();
}

function formatBotMessage(text) {
  const escaped = escapeHtml(text);
  return escaped.replace(/(https?:\/\/[^\s।॥]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
}

function scrollToBottom() {
  els.chatMessages.scrollTop = els.chatMessages.scrollHeight;
}

let typingIndicatorEl = null;

function showTypingIndicator() {
  if (typingIndicatorEl) return;
  typingIndicatorEl = document.createElement("div");
  typingIndicatorEl.className = "chat-bubble bot-bubble typing-bubble";
  typingIndicatorEl.innerHTML = `<span class="dot"></span><span class="dot"></span><span class="dot"></span>`;
  els.chatMessages.appendChild(typingIndicatorEl);
  scrollToBottom();
}

function removeTypingIndicator() {
  if (typingIndicatorEl) {
    typingIndicatorEl.remove();
    typingIndicatorEl = null;
  }
}

function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ============================================================
// SENDING A MESSAGE
// ============================================================
async function sendMessage(text) {
  if (!text.trim()) {
    showToast(t("noText"));
    return;
  }

  // Clear any existing silence timer
  clearTimeout(session.silenceTimer);

  appendUserBubble(text);
  els.textInput.value = "";
  autoResizeInput();

  showTypingIndicator();
  setLoading(true);
  let controller = null;
  let timeoutId;

  try {
    if (typeof AbortController !== "undefined") {
      controller = new AbortController();
    }

    const timeout = new Promise((_, reject) => {
      timeoutId = setTimeout(() => {
        if (controller) controller.abort();
        const error = new Error("Chat request timed out");
        error.name = "TimeoutError";
        reject(error);
      }, CHAT_REQUEST_TIMEOUT_MS);
    });

    const requestOptions = {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: session.id,
        text: text.trim(),
        upload_ids: [...session.pendingUploadIds],
      }),
    };
    if (controller) requestOptions.signal = controller.signal;

    const res = await Promise.race([
      fetch(`${API_BASE}/api/chat`, requestOptions),
      timeout,
    ]);

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    session.pendingUploadIds = [];
    removeTypingIndicator();
    setLoading(false);

    // Render messages & TTS
    for (const msg of data.messages || []) {
      appendBotBubble(msg);
      await playTTS(msg);
    }

    // Update household members
    if (data.member) {
      renderMemberChips(data.member);
    }

    // Update checklist
    if (data.checklist) {
      renderChecklist(data.checklist);
    }

    // Update form preview
    if (data.form_preview) {
      renderFormPreview(data.form_preview);
    }

    // Show notices
    if (data.notices?.length) {
      showNotices(data.notices);
    }

    // Schedule gentle silence prompt once
    armSilenceTimer();

  } catch (err) {
    console.error("Chat error:", err);
    removeTypingIndicator();
    setLoading(false);
    appendBotBubble(
      err.name === "AbortError" || err.name === "TimeoutError"
        ? t("timeoutErr")
        : t("networkErr")
    );
  } finally {
    clearTimeout(timeoutId);
  }
}

function armSilenceTimer() {
  clearTimeout(session.silenceTimer);
  if (!session.gentlePromptPlayed) {
    session.silenceTimer = setTimeout(async () => {
      session.gentlePromptPlayed = true;
      const prompt = t("gentlePrompt");
      appendBotBubble(prompt);
      await playTTS(prompt);
    }, POST_RESPONSE_SILENCE_MS);
  }
}

function autoResizeInput() {
  const ta = els.textInput;
  ta.style.height = "auto";
  ta.style.height = `${Math.min(ta.scrollHeight, 140)}px`;
}

els.textInput.addEventListener("input", autoResizeInput);
els.textInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage(els.textInput.value);
  }
});

els.sendBtn.addEventListener("click", () => {
  sendMessage(els.textInput.value);
});

// ============================================================
// VOICE – STT & VOICE COMMANDS
// ============================================================
let mediaRecorder = null;
let audioChunks = [];
let recordTimer = null;
let silenceAudioContext = null;
let silenceAnalyser = null;
let silenceCheckInterval = null;

els.micBtn.addEventListener("click", toggleRecording);

async function toggleRecording() {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    stopRecording();
    return;
  }

  // If agent is speaking, cancel speech on mic tap
  stopTTS();

  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
    startRecording(stream);
  } catch (err) {
    console.error("Mic error:", err);
    showToast(t("micErr"));
  }
}

function startRecording(stream) {
  audioChunks = [];
  mediaRecorder = new MediaRecorder(stream, { mimeType: preferredMime() });

  mediaRecorder.addEventListener("dataavailable", (e) => {
    if (e.data.size > 0) audioChunks.push(e.data);
  });

  mediaRecorder.addEventListener("stop", async () => {
    stream.getTracks().forEach((track) => track.stop());
    clearInterval(silenceCheckInterval);
    if (silenceAudioContext) {
      silenceAudioContext.close().catch(() => {});
      silenceAudioContext = null;
    }
    const blob = new Blob(audioChunks, { type: preferredMime() });
    await processAudioInput(blob);
  });

  mediaRecorder.start(250);
  setMicState(true);

  // Setup silence detection for auto-stop
  setupSilenceAutoStop(stream);

  recordTimer = setTimeout(stopRecording, MAX_RECORD_MS);
}

function setupSilenceAutoStop(stream) {
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;

    silenceAudioContext = new AudioCtx();
    const source = silenceAudioContext.createMediaStreamSource(stream);
    silenceAnalyser = silenceAudioContext.createAnalyser();
    silenceAnalyser.fftSize = 256;
    source.connect(silenceAnalyser);

    const buffer = new Uint8Array(silenceAnalyser.frequencyBinCount);
    let speechDetected = false;
    let silenceStart = null;

    silenceCheckInterval = setInterval(() => {
      silenceAnalyser.getByteFrequencyData(buffer);
      let sum = 0;
      for (let i = 0; i < buffer.length; i++) sum += buffer[i];
      const avg = sum / buffer.length;

      if (avg > 15) {
        speechDetected = true;
        silenceStart = null;
      } else if (speechDetected) {
        if (!silenceStart) {
          silenceStart = Date.now();
        } else if (Date.now() - silenceStart > SILENCE_TIMEOUT_MS) {
          stopRecording();
        }
      }
    }, 100);
  } catch (e) {
    console.warn("Silence auto-stop unavailable:", e);
  }
}

function stopRecording() {
  clearTimeout(recordTimer);
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
  setMicState(false);
}

function setMicState(recording) {
  els.micBtn.classList.toggle("recording", recording);
  els.micBtn.setAttribute("aria-pressed", String(recording));
  els.micBtn.setAttribute("aria-label", recording ? t("micStart") : "बोलें – माइक दबाएँ");
  const label = els.micBtn.querySelector(".mic-label");
  if (label) label.textContent = recording ? "रोकें" : "बोलें";
}

function preferredMime() {
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/ogg"];
  return candidates.find((m) => MediaRecorder.isTypeSupported(m)) || "";
}

async function processAudioInput(audioBlob) {
  setLoading(true);
  try {
    const fd = new FormData();
    fd.append("file", audioBlob, "recording.webm");
    if (session.id) fd.append("session_id", session.id);
    fd.append("language", session.language);

    const res = await fetch(`${API_BASE}/api/stt`, {
      method: "POST",
      body: fd,
    });
    if (!res.ok) throw new Error(`STT HTTP ${res.status}`);
    const data = await res.json();
    setLoading(false);

    const text = data.text?.trim();
    if (!text) return;

    // Check voice command before LLM
    const handled = await handleVoiceCommand(text);
    if (!handled) {
      await sendMessage(text);
    }
  } catch (err) {
    console.error("STT error:", err);
    setLoading(false);
    showToast(t("networkErr"));
  }
}

async function handleVoiceCommand(text) {
  try {
    const res = await fetch(`${API_BASE}/api/voice_command`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, language: session.language }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    const cmd = data.command;

    if (!cmd) return false;

    if (cmd === "repeat") {
      if (session.lastSpokenText) {
        showToast("दोहरा रहा हूँ…");
        await playTTS(session.lastSpokenText);
      }
      return true;
    } else if (cmd === "slower") {
      session.playbackRate = Math.max(0.7, session.playbackRate - 0.15);
      showToast(`${t("slowerNotice")} (${session.playbackRate.toFixed(1)}x)`);
      return true;
    } else if (cmd === "faster") {
      session.playbackRate = Math.min(1.5, session.playbackRate + 0.15);
      showToast(`${t("fasterNotice")} (${session.playbackRate.toFixed(1)}x)`);
      return true;
    } else if (cmd === "stop") {
      stopTTS();
      showToast("रुक गया");
      return true;
    } else if (cmd === "wait") {
      stopTTS();
      showToast("इंतज़ार कर रहा हूँ…");
      return true;
    }
  } catch (e) {
    console.warn("Voice command error:", e);
  }
  return false;
}

// ============================================================
// TEXT-TO-SPEECH (WITH BARGE-IN)
// ============================================================
function stopTTS() {
  if (session.currentAudio) {
    session.currentAudio.pause();
    session.currentAudio = null;
  }
  if ("speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
}

async function playTTS(text) {
  if (!text || text.length > 500) return;

  stopTTS();
  session.lastSpokenText = text;

  try {
    const res = await fetch(`${API_BASE}/api/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, language: session.language }),
    });

    if (!res.ok) throw new Error("TTS failed");
    const blob = await res.blob();
    if (blob.size === 0) throw new Error("Empty audio blob");

    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    session.currentAudio = audio;
    audio.playbackRate = session.playbackRate;

    await Promise.race([
      new Promise((resolve) => {
        audio.addEventListener("ended", () => {
          URL.revokeObjectURL(url);
          session.currentAudio = null;
          resolve();
        });
        audio.addEventListener("error", () => {
          session.currentAudio = null;
          resolve();
        });
        audio.play().catch(() => resolve());
      }),
      new Promise((resolve) => setTimeout(resolve, 10000)),
    ]);
  } catch (_) {
    // Fallback: browser speechSynthesis
    if ("speechSynthesis" in window) {
      await Promise.race([
        new Promise((resolve) => {
          const utt = new SpeechSynthesisUtterance(text);
          utt.lang = langToLocale(session.language);
          utt.rate = session.playbackRate * 0.9;
          utt.onend = () => {
            resolve();
          };
          utt.onerror = () => {
            resolve();
          };
          window.speechSynthesis.speak(utt);
        }),
        new Promise((resolve) => setTimeout(resolve, 6000)),
      ]);
    }
  }
}

function langToLocale(lang) {
  return { hi: "hi-IN", en: "en-IN", mr: "mr-IN", ta: "ta-IN" }[lang] || "hi-IN";
}

// ============================================================
// HOUSEHOLD MEMBERS CHIPS
// ============================================================
async function fetchHousehold() {
  if (!session.id) return;
  try {
    const res = await fetch(`${API_BASE}/api/household?session_id=${session.id}`);
    if (res.ok) {
      const data = await res.json();
      renderMemberChips(data);
    }
  } catch (e) {
    console.warn("fetchHousehold failed:", e);
  }
}

function renderMemberChips(memberData) {
  if (!memberData?.members) return;
  els.memberChipsContainer.innerHTML = "";

  for (const m of memberData.members) {
    const btn = document.createElement("button");
    btn.className = `member-chip ${m.is_active ? "active" : ""}`;
    btn.dataset.memberId = m.member_id;
    btn.innerHTML = `
      <span class="chip-avatar">${m.relation === "self" ? "👤" : "👥"}</span>
      <span class="chip-name">${escapeHtml(m.display_name || m.relation)}</span>
    `;
    btn.addEventListener("click", () => switchMember(m.member_id));
    els.memberChipsContainer.appendChild(btn);
  }

  // Append "+ नया सदस्य" button
  const addBtn = document.createElement("button");
  addBtn.className = "member-chip add-chip";
  addBtn.innerHTML = `<span>➕ नया सदस्य</span>`;
  addBtn.addEventListener("click", promptAddMember);
  els.memberChipsContainer.appendChild(addBtn);
}

async function switchMember(memberId) {
  try {
    const res = await fetch(`${API_BASE}/api/household/switch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: session.id, member_id: memberId }),
    });
    if (res.ok) {
      const data = await res.json();
      showToast(data.message || "सदस्य बदल दिया गया");
      await fetchHousehold();
    }
  } catch (e) {
    console.error("switchMember failed:", e);
  }
}

async function promptAddMember() {
  const name = prompt("परिवार के नए सदस्य का नाम या रिश्ता (जैसे: पत्नी, माताजी):");
  if (!name || !name.trim()) return;

  try {
    const res = await fetch(`${API_BASE}/api/household/member`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: session.id,
        relationship: name.trim(),
        name: name.trim(),
      }),
    });
    if (res.ok) {
      const data = await res.json();
      showToast("नया सदस्य जोड़ा गया");
      if (data.consent_prompt) {
        appendBotBubble(data.consent_prompt);
        await playTTS(data.consent_prompt);
      }
      await fetchHousehold();
    }
  } catch (e) {
    console.error("promptAddMember error:", e);
  }
}

// ============================================================
// OFFLINE PACKET & GRIEVANCE BUTTONS
// ============================================================
els.btnHandoffPacket.addEventListener("click", async () => {
  try {
    const res = await fetch(`${API_BASE}/api/handoff/packet`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: session.id }),
    });
    if (!res.ok) throw new Error("Failed to get packet");
    const html = await res.text();
    const w = window.open("", "_blank");
    if (w) {
      w.document.write(html);
      w.document.close();
      w.print();
    }
  } catch (e) {
    showToast("सहायता पर्ची तैयार नहीं हो सकी");
  }
});

els.btnGrievanceDraft.addEventListener("click", async () => {
  try {
    const res = await fetch(`${API_BASE}/api/grievance/draft`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: session.id,
        scheme_id: session.activeSchemeId || "योजना",
        rejection_category: "name_mismatch",
      }),
    });
    if (!res.ok) throw new Error("Grievance failed");
    const data = await res.json();
    const w = window.open("", "_blank");
    if (w) {
      w.document.write(`<pre style="font-family:system-ui; white-space:pre-wrap; padding:30px;">${escapeHtml(data.letter || "")}</pre>`);
      w.document.close();
      w.print();
    }
  } catch (e) {
    showToast("शिकायत पत्र तैयार नहीं हो सका");
  }
});

// ============================================================
// CHECKLIST & PREVIEWS
// ============================================================
const STATUS_ICONS = {
  waiting:  "⏳",
  checking: "🔍",
  verified: "✅",
  problem:  "❌",
  missing:  "⚠️",
  rejected: "❌",
  provided: "✅",
};

function renderChecklist(checklist) {
  if (!checklist?.documents?.length) return;
  els.checklistEmpty?.remove();

  for (const doc of checklist.documents) {
    const id = doc.doc_id || doc.filename || Math.random().toString(36).slice(2);
    addOrUpdateChecklistItem(doc.doc_type || doc.filename || "दस्तावेज़", doc.status || "waiting", id);
  }
}

function addOrUpdateChecklistItem(label, status, id) {
  let li = els.checklistList.querySelector(`[data-id="${CSS.escape(id)}"]`);
  if (!li) {
    li = document.createElement("li");
    li.dataset.id = id;
    els.checklistList.appendChild(li);
  }
  li.className = `checklist-item ${status}`;
  li.innerHTML = `
    <span class="checklist-icon">${STATUS_ICONS[status] || "📄"}</span>
    <span>${escapeHtml(label)}</span>
  `;
}

function renderFormPreview(preview) {
  if (!preview) return;
  session.activeSchemeId = preview.scheme_id || session.activeSchemeId;
  const fields = preview.fields || [];

  let html = `<div class="form-fields">`;
  for (const f of fields) {
    const val = f.value !== undefined && f.value !== null && f.value !== "" ? f.value : "—";
    html += `
      <div class="form-field">
        <span class="form-field-label">${escapeHtml(f.label || f.key || "")}</span>
        <span class="form-field-value">${escapeHtml(String(val))}</span>
      </div>
    `;
  }
  html += `</div>`;
  els.formContent.innerHTML = html;
  els.formActions.hidden = false;
}

els.confirmBtn.addEventListener("click", async () => {
  if (!session.activeSchemeId) return;
  els.confirmBtn.disabled = true;
  try {
    const res = await fetch(`${API_BASE}/api/form/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: session.id,
        scheme_id: session.activeSchemeId,
        confirmed: true,
      }),
    });
    if (res.ok) {
      const data = await res.json();
      appendBotBubble(data.message || "✅ फ़ॉर्म की जानकारी सही मानी गई।");
      await playTTS(data.message || "फ़ॉर्म की जानकारी सही मानी गई।");
      els.formActions.hidden = true;
    }
  } finally {
    els.confirmBtn.disabled = false;
  }
});

function showNotices(notices) {
  if (!notices?.length) {
    els.noticesBar.hidden = true;
    return;
  }
  els.noticesBar.textContent = notices.join(" · ");
  els.noticesBar.hidden = false;
}

let toastContainer = null;
function showToast(msg, durationMs = 3500) {
  if (!toastContainer) {
    toastContainer = document.createElement("div");
    toastContainer.className = "toast-stack";
    document.body.appendChild(toastContainer);
  }
  const div = document.createElement("div");
  div.className = "toast";
  div.textContent = msg;
  toastContainer.appendChild(div);
  setTimeout(() => div.remove(), durationMs);
}

function setLoading(on) {
  if (on) {
    els.loadingOverlay.classList.add("active");
    els.loadingOverlay.removeAttribute("hidden");
    els.loadingOverlay.style.display = "flex";
  } else {
    els.loadingOverlay.classList.remove("active");
    els.loadingOverlay.setAttribute("hidden", "");
    els.loadingOverlay.style.display = "none";
  }
  els.sendBtn.disabled = on;
  els.micBtn.disabled = on;
}

(async function boot() {
  setLoading(false);
  await initSession();
})();
