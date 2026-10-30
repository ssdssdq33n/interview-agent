/* ═══════════════════════════════════════════════════════════════
   Interview Agent — Frontend (All Phases)
   WebSocket · dual brain · edge-TTS · STT · 3D avatar · code
   ═══════════════════════════════════════════════════════════════ */

"use strict";

// ── STATE ─────────────────────────────────────────────────────────────────────
const S = {
  sessionId:     null,
  ws:            null,
  wsConnected:   false,
  mode:          "interviewer",
  provider:      "ollama",
  language:      "vi",
  level:         "mid",
  ttsMode:       "edge",        // edge | browser | off
  avatarVoice:   true,
  avatar3d:      true,
  timerSeconds:  120,
  agentState:    "idle",
  streaming:     false,
  streamTarget:  null,
  streamRaw:     "",
  recording:     false,
  recognition:   null,
  pingTimer:     null,
  reconnectTimer: null,
  reconnectDelay: 2000,
  phase:         "introduction",
  started:       false,
  questionTimer: null,
  timerRemaining: 0,
  monacoEditor:  null,
  currentChallenge: null,
  audioContext:  null,
  audioQueue:    [],
  audioPlaying:  false,
};

// ── DOM ───────────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const D = {
  statusBadge:      $("status-badge"),
  statusText:       $("status-text"),
  messagesArea:     $("messages-area"),
  welcomeCard:      $("welcome-card"),
  msgInput:         $("msg-input"),
  btnSend:          $("btn-send"),
  btnMic:           $("btn-mic"),
  toolIndicator:    $("tool-indicator"),
  toolLabel:        $("tool-label"),
  avatarHead:       document.querySelector(".avatar-head"),
  avatarMouth:      $("avatar-mouth"),
  stateDots:        document.querySelector(".state-dots"),
  stateLabel:       $("state-label"),
  waveform:         $("waveform"),
  phaseBar:         $("phase-bar"),
  questionTimer:    $("question-timer"),
  timerLabel:       $("timer-label"),
  recordingOverlay: $("recording-overlay"),
  interimText:      $("interim-text"),
  settingsOverlay:  $("settings-overlay"),
  settingsPanel:    $("settings-panel"),
  historyPanel:     $("history-panel"),
  historyList:      $("history-list"),
  hintMode:         $("hint-mode"),
  hintProvider:     $("hint-provider"),
  hintLang:         $("hint-lang"),
  hintRag:          $("hint-rag"),
  ollamaDot:        $("ollama-dot"),
  claudeDot:        $("claude-dot"),
  codePanel:        $("code-panel"),
  codeTitle:        $("code-title"),
  codeDescription:  $("code-description"),
  codeOutput:       $("code-output"),
  avatarScene3d:    $("avatar-scene-3d"),
};

// ── I18N ──────────────────────────────────────────────────────────────────────
const T = {
  vi: {
    idle: "Sẵn sàng", thinking: "Đang suy nghĩ...", speaking: "Đang trả lời...", listening: "Đang nghe...",
    connecting: "Đang kết nối...", connected: "Đã kết nối", disconnected: "Mất kết nối",
    placeholder: "Nhập câu trả lời... (Enter gửi · Shift+Enter xuống dòng · Space = voice)",
    phaseLabels: { introduction:"Giới thiệu", background:"Nền tảng", technical:"Kỹ thuật", system_design:"System Design", behavioral:"Hành vi", qa:"Q&A" },
    modeLabel: { interviewer:"Chế độ: Interview", trainer:"Chế độ: Training" },
  },
  en: {
    idle: "Ready", thinking: "Thinking...", speaking: "Speaking...", listening: "Listening...",
    connecting: "Connecting...", connected: "Connected", disconnected: "Disconnected",
    placeholder: "Type your answer... (Enter to send · Shift+Enter newline · Space = voice)",
    phaseLabels: { introduction:"Intro", background:"Background", technical:"Technical", system_design:"System Design", behavioral:"Behavioral", qa:"Q&A" },
    modeLabel: { interviewer:"Mode: Interview", trainer:"Mode: Training" },
  },
};
const t = (k, sub) => { const T_ = T[S.language] || T.vi; return sub ? (T_[k]||{})[sub]||k : T_[k]||k; };

// ── MARKDOWN ──────────────────────────────────────────────────────────────────
function renderMD(text) {
  let h = text
    .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
    .replace(/```(\w*)\n([\s\S]*?)```/g, (_,l,c) => `<pre><code class="lang-${l}">${c.trim()}</code></pre>`)
    .replace(/`([^`\n]+)`/g, "<code>$1</code>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/^### (.+)$/gm,"<h4>$1</h4>")
    .replace(/^## (.+)$/gm, "<h3>$1</h3>")
    .replace(/^# (.+)$/gm,  "<h2>$1</h2>")
    .replace(/^&gt; (.+)$/gm, "<blockquote>$1</blockquote>")
    .replace(/^[-*] (.+)$/gm,"<li>$1</li>")
    .replace(/^\d+\. (.+)$/gm,"<li>$1</li>");
  h = h.replace(/(<li>[\s\S]*?<\/li>)/g, m => `<ul>${m}</ul>`);
  return h.replace(/\n\n/g,"<br><br>").replace(/\n/g,"<br>");
}

// ── WEBSOCKET ─────────────────────────────────────────────────────────────────
function wsConnect() {
  if (S.ws && S.ws.readyState < 2) return;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  S.ws = new WebSocket(`${proto}://${location.host}/ws/${S.sessionId}`);
  setStatus("connecting");

  S.ws.onopen = () => {
    S.ws.send(JSON.stringify({ mode: S.mode, language: S.language }));
    S.wsConnected = true;
    S.reconnectDelay = 2000;
    clearTimeout(S.reconnectTimer);
    startPing();
  };

  S.ws.onmessage = e => {
    try { handleWsEvent(JSON.parse(e.data)); } catch {}
  };

  S.ws.onclose = () => {
    S.wsConnected = false;
    setStatus("error");
    stopPing();
    if (S.agentState !== "idle") setAgentState("idle");
    S.reconnectTimer = setTimeout(() => {
      S.reconnectDelay = Math.min(S.reconnectDelay * 1.5, 15000);
      wsConnect();
    }, S.reconnectDelay);
  };

  S.ws.onerror = () => S.ws.close();
}

function wsSend(obj) {
  if (S.ws && S.ws.readyState === WebSocket.OPEN)
    S.ws.send(JSON.stringify(obj));
}

function startPing() { stopPing(); S.pingTimer = setInterval(() => wsSend({type:"ping"}), 25000); }
function stopPing()  { clearInterval(S.pingTimer); }

// ── WS EVENTS ─────────────────────────────────────────────────────────────────
function handleWsEvent(ev) {
  switch (ev.type) {
    case "connected":
      setStatus("ok");
      S.provider = ev.provider || S.provider;
      updateProviderDots(S.provider);
      D.hintProvider.textContent = S.provider === "claude" ? "Claude" : "Ollama";
      checkHealth();
      break;

    case "state":
      setAgentState(ev.value);
      if (ev.value === "speaking" && !S.streaming) {
        S.streamTarget = appendMessage("assistant", "");
        S.streaming = true; S.streamRaw = "";
      }
      break;

    case "token":
      if (!S.streaming || !S.streamTarget) {
        S.streamTarget = appendMessage("assistant", "");
        S.streaming = true; S.streamRaw = "";
      }
      S.streamRaw += ev.text || "";
      appendToken(S.streamTarget, ev.text || "");
      break;

    case "done":
      if (S.streaming) finalizeStream();
      setAgentState("idle");
      // TTS: play agent's response
      if (ev.content && S.avatarVoice && S.ttsMode !== "off") {
        speakText(ev.content);
      }
      break;

    case "tool":
      handleToolEvent(ev);
      break;

    case "error":
      appendSysMsg("⚠ " + (ev.message || "Lỗi"), "error");
      setAgentState("idle");
      if (S.streaming) finalizeStream();
      break;

    case "mode_changed":
      S.mode = ev.mode; syncModeUI();
      appendSysMsg(S.language==="vi"
        ? `Chuyển sang chế độ ${ev.mode==="trainer"?"Training":"Interview"}`
        : `Switched to ${ev.mode==="trainer"?"Training":"Interview"} mode`, "info");
      break;

    case "provider_changed":
      S.provider = ev.provider; updateProviderDots(ev.provider);
      D.hintProvider.textContent = ev.provider==="claude"?"Claude":"Ollama";
      break;

    case "language_changed":
      S.language = ev.language; syncLangUI();
      break;

    case "pong": break;
  }
}

// ── TOOL EVENTS ───────────────────────────────────────────────────────────────
function handleToolEvent(ev) {
  const names = {
    remember:"Lưu ghi chú...", recall:"Tìm bộ nhớ...",
    next_phase:"Chuyển giai đoạn...", end_session:"Kết thúc phiên...",
    score_answer:"Chấm điểm...", get_coding_challenge:"Lấy bài tập...",
  };
  if (ev.status === "running") {
    D.toolIndicator.classList.remove("hidden");
    D.toolLabel.textContent = names[ev.name] || `${ev.name}...`;
  } else {
    D.toolIndicator.classList.add("hidden");
    // Handle score result
    if (ev.name === "score_answer" && ev.result) {
      try {
        const r = JSON.parse(ev.result);
        if (r.score !== undefined) appendScoreCard(r.score, r.feedback, r.model_answer);
      } catch {}
    }
    // Handle coding challenge
    if (ev.name === "get_coding_challenge" && ev.result) {
      try {
        const ch = JSON.parse(ev.result);
        openCodeChallenge(ch);
      } catch {}
    }
    // Handle phase change
    if (ev.name === "next_phase" && ev.result) {
      const m = ev.result.match(/phase: (\w+)/);
      if (m) updatePhase(m[1]);
    }
    // Session ended -> show report
    if (ev.name === "end_session") {
      setTimeout(() => showReport(S.sessionId), 1200);
    }
  }
}

// ── AVATAR STATE ──────────────────────────────────────────────────────────────
function setAgentState(state) {
  S.agentState = state;
  if (D.avatarHead) D.avatarHead.classList.remove("listening");
  if (D.avatarMouth) D.avatarMouth.classList.remove("speaking");
  if (D.stateDots) D.stateDots.classList.remove("visible");
  if (D.waveform) D.waveform.classList.remove("visible");

  if (typeof window.Avatar3D !== "undefined") window.Avatar3D.setState(state);

  switch (state) {
    case "thinking":
      if (D.stateDots) D.stateDots.classList.add("visible");
      if (D.stateLabel) D.stateLabel.textContent = t("thinking");
      break;
    case "speaking":
      if (D.avatarMouth) D.avatarMouth.classList.add("speaking");
      if (D.waveform) D.waveform.classList.add("visible");
      if (D.stateLabel) D.stateLabel.textContent = t("speaking");
      break;
    case "listening":
      if (D.avatarHead) D.avatarHead.classList.add("listening");
      if (D.stateLabel) D.stateLabel.textContent = t("listening");
      break;
    default:
      if (D.stateLabel) D.stateLabel.textContent = t("idle");
  }
}

// ── STATUS ────────────────────────────────────────────────────────────────────
function setStatus(s) {
  D.statusBadge.className = "status-badge status-" + (s==="ok"?"ok":s==="error"?"error":"connecting");
  D.statusText.textContent = s==="ok"?t("connected"):s==="error"?t("disconnected"):t("connecting");
}

// ── MESSAGES ──────────────────────────────────────────────────────────────────
function hideWelcome() {
  if (D.welcomeCard) D.welcomeCard.style.display = "none";
  S.started = true;
}

function appendMessage(role, html) {
  hideWelcome();
  const wrap = document.createElement("div");
  wrap.className = `message ${role}`;
  const av = document.createElement("div");
  av.className = "msg-avatar";
  av.textContent = role === "assistant" ? "A" : "U";
  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";
  bubble.innerHTML = html;
  wrap.appendChild(av);
  wrap.appendChild(bubble);
  D.messagesArea.appendChild(wrap);
  scrollBottom();
  return bubble;
}

function appendToken(bubble, text) {
  const cursor = bubble.querySelector(".streaming-cursor");
  if (cursor) cursor.insertAdjacentText("beforebegin", text);
  else {
    bubble.appendChild(document.createTextNode(text));
    const c = document.createElement("span");
    c.className = "streaming-cursor";
    bubble.appendChild(c);
  }
  scrollBottom();
}

function finalizeStream() {
  if (!S.streaming || !S.streamTarget) return;
  const cursor = S.streamTarget.querySelector(".streaming-cursor");
  if (cursor) cursor.remove();
  S.streamTarget.innerHTML = renderMD(S.streamRaw);
  S.streamRaw = ""; S.streaming = false; S.streamTarget = null;
  scrollBottom();
}

function appendSysMsg(text, kind = "info") {
  hideWelcome();
  const el = document.createElement("div");
  el.className = `sys-msg ${kind}`;
  el.textContent = text;
  D.messagesArea.appendChild(el);
  scrollBottom();
}

function appendScoreCard(score, feedback, modelAnswer) {
  hideWelcome();
  const stars = "★".repeat(Math.round(score/2)) + "☆".repeat(5-Math.round(score/2));
  const cls = score>=8?"high":score>=6?"mid":"low";
  const div = document.createElement("div");
  div.className = `score-card ${cls}`;
  div.innerHTML = `
    <div class="score-stars">📊 <strong>${score.toFixed(1)}/10</strong> ${stars}</div>
    <div class="score-feedback">${feedback || ""}</div>
    ${modelAnswer ? `<div class="score-model"><strong>💡 Câu trả lời mẫu:</strong><br>${renderMD(modelAnswer)}</div>` : ""}
  `;
  D.messagesArea.appendChild(div);
  scrollBottom();
}

function scrollBottom() {
  requestAnimationFrame(() => { D.messagesArea.scrollTop = D.messagesArea.scrollHeight; });
}

// ── TOAST ───────────────────────────────────────────────────────────────────────
function toast(msg, kind = "info", ms = 3200) {
  const wrap = $("toast-wrap");
  if (!wrap) return;
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.textContent = msg;
  wrap.appendChild(el);
  setTimeout(() => {
    el.style.transition = "opacity .3s, transform .3s";
    el.style.opacity = "0"; el.style.transform = "translateY(10px)";
    setTimeout(() => el.remove(), 300);
  }, ms);
}

// ── TTS ───────────────────────────────────────────────────────────────────────
function cleanTextForTts(text) {
  return text
    .replace(/```[\s\S]*?```/g, "")
    .replace(/`[^`]+`/g, "")
    .replace(/[*_#>]/g, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/📊|★|☆|💡|📚|🎯/g, "")
    .replace(/\s+/g, " ").trim();
}

async function speakText(rawText) {
  if (S.ttsMode === "off" || !S.avatarVoice) return;
  const text = cleanTextForTts(rawText);
  if (!text) return;

  if (S.ttsMode === "edge") {
    try {
      const res = await fetch("/api/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, language: S.language }),
      });
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.onplay   = () => setAgentState("speaking");
      audio.onended  = () => { setAgentState("idle"); URL.revokeObjectURL(url); };
      audio.onerror  = () => { setAgentState("idle"); };
      await audio.play();
      return;
    } catch (e) {
      console.warn("[TTS] Edge TTS fallback to browser:", e.message);
    }
  }

  // Browser SpeechSynthesis fallback
  if (!window.speechSynthesis) return;
  const sentences = text.match(/[^.!?。！？]+[.!?。！？]*/g) || [text];
  for (const s of sentences) {
    await new Promise(resolve => {
      const utt = new SpeechSynthesisUtterance(s.trim());
      const voices = speechSynthesis.getVoices();
      const lang = S.language === "en" ? "en" : "vi";
      const voice = voices.find(v => v.lang.startsWith(lang === "vi" ? "vi" : "en-US"))
                 || voices.find(v => v.default);
      if (voice) utt.voice = voice;
      utt.lang = lang === "vi" ? "vi-VN" : "en-US";
      utt.rate = 0.95; utt.pitch = 0.9;
      utt.onstart = () => setAgentState("speaking");
      utt.onend   = resolve;
      utt.onerror = resolve;
      speechSynthesis.speak(utt);
    });
  }
  setAgentState("idle");
}

function stopTts() {
  if (window.speechSynthesis) speechSynthesis.cancel();
}

// ── STT ───────────────────────────────────────────────────────────────────────
function startRecording() {
  if (S.recording) return;
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    appendSysMsg(S.language==="vi"
      ? "Trình duyệt không hỗ trợ mic. Dùng Chrome/Edge."
      : "Browser doesn't support mic. Use Chrome/Edge.", "error");
    return;
  }
  stopTts();
  S.recording = true;
  D.recordingOverlay.classList.remove("hidden");
  D.btnMic.classList.add("recording");
  setAgentState("listening");

  const rec = new SR();
  rec.lang = S.language === "en" ? "en-US" : "vi-VN";
  rec.interimResults = true;
  rec.continuous = false;
  S.recognition = rec;

  rec.onresult = e => {
    const interim = Array.from(e.results).map(r => r[0].transcript).join("");
    if (D.interimText) D.interimText.textContent = interim;
    D.msgInput.value = interim;
    autoResize(D.msgInput);
    if (e.results[e.results.length-1].isFinal) {
      stopRecording();
      if (interim.trim()) sendText(interim);
    }
  };
  rec.onerror = () => stopRecording();
  rec.onend   = () => stopRecording();
  rec.start();
}

function stopRecording() {
  if (!S.recording) return;
  S.recording = false;
  D.recordingOverlay.classList.add("hidden");
  D.btnMic.classList.remove("recording");
  if (D.interimText) D.interimText.textContent = "";
  if (S.recognition) { try { S.recognition.stop(); } catch{} S.recognition = null; }
  if (S.agentState === "listening") setAgentState("idle");
}

// ── QUESTION TIMER ────────────────────────────────────────────────────────────
function startTimer(seconds) {
  stopTimer();
  if (!seconds) return;
  S.timerRemaining = seconds;
  D.questionTimer.classList.remove("hidden", "urgent");
  _tickTimer();
  S.questionTimer = setInterval(_tickTimer, 1000);
}

function _tickTimer() {
  if (!D.timerLabel) return;
  const m = Math.floor(S.timerRemaining / 60);
  const s = S.timerRemaining % 60;
  D.timerLabel.textContent = `${m}:${String(s).padStart(2,"0")}`;
  if (S.timerRemaining <= 30) D.questionTimer.classList.add("urgent");
  if (S.timerRemaining <= 0) { stopTimer(); appendSysMsg("⏰ Hết thời gian!", "error"); }
  S.timerRemaining--;
}

function stopTimer() {
  clearInterval(S.questionTimer);
  if (D.questionTimer) D.questionTimer.classList.add("hidden");
}

// ── PHASE BAR ──────────────────────────────────────────────────────────────────
const PHASES = ["introduction","background","technical","system_design","behavioral","qa"];

function updatePhase(phase) {
  if (!phase) return;
  S.phase = phase;
  const steps = D.phaseBar.querySelectorAll(".phase-step");
  const idx = PHASES.indexOf(phase);
  steps.forEach((s, i) => {
    s.classList.remove("active","done");
    if (i < idx) s.classList.add("done");
    else if (i === idx) { s.classList.add("active"); }
    const key = s.dataset.phase;
    const lbl = t("phaseLabels", key);
    if (lbl && lbl !== key) s.textContent = lbl;
  });
  // Start timer when entering technical phase
  if (phase === "technical" && S.timerSeconds > 0) startTimer(S.timerSeconds);
  else if (phase !== "technical") stopTimer();
}

// ── CODE CHALLENGE ────────────────────────────────────────────────────────────
function openCodeChallenge(challenge) {
  S.currentChallenge = challenge;
  if (D.codeTitle) D.codeTitle.textContent = challenge.title || "Bài tập coding";
  if (D.codeDescription) D.codeDescription.textContent = challenge.description || "";
  D.codePanel.classList.remove("hidden");
  D.codeOutput.classList.add("hidden");

  // Try Monaco Editor
  const starterCode = challenge.starter || "public class Main {\n    public static void main(String[] args) {\n        // your code here\n    }\n}";
  loadMonaco(starterCode);
}

function loadMonaco(code) {
  const container = $("monaco-container");
  if (!container) return;

  if (S.monacoEditor) {
    S.monacoEditor.setValue(code);
    return;
  }

  // Fallback: textarea if Monaco not available
  const initMonaco = () => {
    if (typeof require !== "undefined" && typeof window.monaco === "undefined") {
      require.config({ paths: { vs: "https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs" } });
      require(["vs/editor/editor.main"], () => {
        S.monacoEditor = window.monaco.editor.create(container, {
          value: code,
          language: "java",
          theme: "vs",
          fontSize: 13,
          fontFamily: "'JetBrains Mono', monospace",
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          automaticLayout: true,
          lineNumbers: "on",
          folding: true,
          wordWrap: "on",
        });
      });
    } else if (!window.monaco) {
      // Plain textarea fallback
      container.innerHTML = `<textarea id="code-textarea" style="width:100%;height:100%;font-family:JetBrains Mono,monospace;font-size:13px;padding:10px;border:none;outline:none;resize:none;background:#fff" spellcheck="false">${code.replace(/</g,"&lt;")}</textarea>`;
    }
  };

  // Load Monaco script if needed
  if (!document.getElementById("monaco-script")) {
    const s = document.createElement("script");
    s.id = "monaco-script";
    s.src = "https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs/loader.js";
    s.onload = initMonaco;
    document.head.appendChild(s);
  } else {
    initMonaco();
  }
}

function getEditorCode() {
  if (S.monacoEditor) return S.monacoEditor.getValue();
  const ta = $("code-textarea");
  return ta ? ta.value : "";
}

async function runCode() {
  const code = getEditorCode();
  const lang = $("code-lang")?.value || "java";
  if (!code.trim()) return;

  D.codeOutput.classList.remove("hidden", "error");
  D.codeOutput.textContent = "Đang chạy...";

  try {
    const res = await fetch("/api/code/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ language: lang, code }),
    });
    const data = await res.json();
    const out = data.stdout || "";
    const err = data.stderr || "";
    D.codeOutput.textContent = out || err || "(không có output)";
    if (!data.success) D.codeOutput.classList.add("error");
  } catch (e) {
    D.codeOutput.textContent = "Lỗi kết nối: " + e.message;
    D.codeOutput.classList.add("error");
  }
}

async function submitCode() {
  const code = getEditorCode();
  if (!code.trim() || !S.wsConnected) return;
  const challenge = S.currentChallenge;
  const msg = S.language === "vi"
    ? `Tôi đã hoàn thành bài tập "${challenge?.title}".\n\n\`\`\`java\n${code}\n\`\`\``
    : `I've completed the challenge "${challenge?.title}".\n\n\`\`\`java\n${code}\n\`\`\``;
  sendText(msg);
  D.codePanel.classList.add("hidden");
}

// ── SEND ──────────────────────────────────────────────────────────────────────
async function sendText(text) {
  text = text.trim();
  if (!text) return;
  if (!S.wsConnected || !S.sessionId) {
    await startSession(S.mode);
    await new Promise(r => setTimeout(r, 600));
  }
  appendMessage("user", renderMD(text));
  wsSend({ type: "message", text });
  D.msgInput.value = "";
  autoResize(D.msgInput);
  setAgentState("thinking");
  stopTimer();
}

// ── SESSION ───────────────────────────────────────────────────────────────────
async function createSession(mode) {
  try {
    const res = await fetch("/api/session/new", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode, level: S.level, language: S.language }),
    });
    return await res.json();
  } catch { return null; }
}

async function startSession(mode) {
  S.mode = mode; syncModeUI(); hideWelcome();
  const data = await createSession(mode);
  if (!data) { appendSysMsg("Không thể tạo phiên. Kiểm tra server.", "error"); return; }
  S.sessionId = data.session_id;
  S.language  = data.language || S.language;
  wsConnect();
  updatePhase("introduction");
  appendSysMsg(
    S.language==="vi"
      ? `🚀 Phiên mới · ${mode==="trainer"?"Trainer":"Interview"} · ${S.level}`
      : `🚀 Session started · ${mode==="trainer"?"Training":"Interview"} · ${S.level}`,
    "info"
  );
}

// New session — reset chat and state, show welcome again
function newSession() {
  try { if (S.ws) S.ws.close(); } catch {}
  clearTimeout(S.reconnectTimer);
  stopTimer(); stopTts();
  S.wsConnected = false; S.started = false; S.streaming = false; S.streamTarget = null;
  S.sessionId = (crypto?.randomUUID?.() || Math.random().toString(36).slice(2));
  // Clear messages, restore welcome card
  D.messagesArea.innerHTML = "";
  if (D.welcomeCard) { D.messagesArea.appendChild(D.welcomeCard); D.welcomeCard.style.display = ""; }
  D.codePanel?.classList.add("hidden");
  updatePhase("introduction");
  setAgentState("idle");
  checkHealth();
  toast(S.language === "vi" ? "Đã tạo phiên mới" : "New session ready", "info");
}

// Export transcript as a .txt file
function exportTranscript() {
  const lines = [];
  D.messagesArea.querySelectorAll(".message, .score-card, .sys-msg").forEach(el => {
    if (el.classList.contains("message")) {
      const who = el.classList.contains("user") ? "Bạn" : "Alex";
      const txt = el.querySelector(".msg-bubble")?.innerText?.trim();
      if (txt) lines.push(`${who}: ${txt}`);
    } else if (el.classList.contains("score-card")) {
      lines.push("— " + el.innerText.replace(/\n+/g, " ").trim());
    }
  });
  if (!lines.length) { toast("Chưa có nội dung để tải", "error"); return; }
  const header = `Interview Agent — Bản ghi phiên\nChế độ: ${S.mode} · Level: ${S.level} · ${new Date().toLocaleString()}\n${"=".repeat(50)}\n\n`;
  const blob = new Blob([header + lines.join("\n\n")], { type: "text/plain;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `interview_${new Date().toISOString().slice(0,10)}.txt`;
  a.click();
  URL.revokeObjectURL(a.href);
  toast("⬇ Đã tải bản ghi", "success");
}

// Ask the agent to wrap up and summarize
function finishInterview() {
  if (!S.wsConnected) {
    // No live session — still try to show whatever report exists
    if (S.sessionId) showReport(S.sessionId);
    else toast("Chưa có phiên nào", "error");
    return;
  }
  sendText(S.language === "vi"
    ? "Hãy kết thúc buổi phỏng vấn, chấm điểm tổng và đưa ra nhận xét tổng kết cho tôi."
    : "Please end the interview, give an overall score and a summary assessment.");
  toast(S.language === "vi" ? "Đang tổng kết..." : "Wrapping up...", "info");
}

// ── SESSION REPORT ───────────────────────────────────────────────────────────────
async function showReport(sessionId) {
  const overlay = $("report-overlay");
  const body = $("report-body");
  if (!overlay || !body || !sessionId) return;
  overlay.classList.remove("hidden");
  body.innerHTML = "<div class='empty-state'>Đang tạo báo cáo…</div>";
  try {
    const res = await fetch(`/api/session/${sessionId}/report`);
    if (!res.ok) throw new Error("no report");
    body.innerHTML = renderReport(await res.json());
  } catch {
    body.innerHTML = "<div class='empty-state'>Chưa đủ dữ liệu để tạo báo cáo. Hãy trả lời vài câu hỏi trước.</div>";
  }
}

function renderReport(r) {
  const vi = S.language === "vi";
  const sc = r.overall_score || 0;
  const ringColor = sc >= 8 ? "linear-gradient(135deg,#34D399,#10B981)"
                  : sc >= 6 ? "linear-gradient(135deg,#60A5FA,#2563EB)"
                            : "linear-gradient(135deg,#F87171,#EF4444)";
  const topicRow = t => {
    const pct = (t.avg_score / 10 * 100).toFixed(0);
    const col = t.avg_score >= 8 ? "var(--success)" : t.avg_score >= 6 ? "var(--primary)" : "var(--error)";
    return `<div class="report-topic"><div class="tp">${t.topic}</div>
      <div class="bar"><span style="width:${pct}%;background:${col}"></span></div>
      <div class="sc">${t.avg_score.toFixed(1)}</div></div>`;
  };
  const meta = [
    [vi?"Chế độ":"Mode", r.mode === "trainer" ? "Training" : "Interview"],
    [vi?"Level":"Level", r.level || "—"],
    [vi?"Số câu":"Questions", `${r.scored_questions}/${r.total_questions}`],
    [vi?"Thời lượng":"Duration", `${r.duration_min || 0} ${vi?"phút":"min"}`],
  ];
  let html = `
    <div class="report-hero">
      <div class="score-ring" style="background:${ringColor}">
        <div class="num">${sc.toFixed(1)}</div><div class="lbl">/ 10</div>
      </div>
      <div class="report-hero-meta">
        ${meta.map(([k,v]) => `<div class="report-stat"><div class="k">${k}</div><div class="v">${v}</div></div>`).join("")}
      </div>
    </div>`;
  if (r.topics && r.topics.length) {
    html += `<div class="report-section-title">${vi?"📊 Điểm theo chủ đề":"📊 Scores by topic"}</div>`;
    html += r.topics.map(topicRow).join("");
  }
  if (r.strengths?.length || r.weaknesses?.length) {
    html += `<div class="report-section-title">${vi?"🎯 Điểm mạnh & cần cải thiện":"🎯 Strengths & gaps"}</div><div class="chip-row">`;
    html += (r.strengths||[]).map(t => `<span class="chip good">✓ ${t.topic}</span>`).join("");
    html += (r.weaknesses||[]).map(t => `<span class="chip bad">△ ${t.topic}</span>`).join("");
    html += `</div>`;
  }
  if (r.recommendation) html += `<div class="report-rec">${r.recommendation}</div>`;
  if (!r.scored_questions) html = `<div class="empty-state">${vi?"Phiên này chưa có câu hỏi nào được chấm điểm.":"No scored questions in this session yet."}</div>`;
  return html;
}

function closeReport() { $("report-overlay")?.classList.add("hidden"); }

async function checkHealth() {
  try {
    const d = await (await fetch("/api/health")).json();
    D.ollamaDot.className = "provider-dot " + (d.ollama?.ok ? "online" : "offline");
    D.claudeDot.className = "provider-dot " + (d.claude?.ok ? "online" : "offline");
    // Update RAG hint — so chunk thuc te trong knowledge base
    if (D.hintRag) {
      D.hintRag.textContent = `RAG: ${d.rag_chunks || 0} chunks`;
    }
    // Server song -> badge "San sang" (chi khi chua trong phien WS)
    if (!S.wsConnected) {
      D.statusBadge.className = "status-badge status-ok";
      D.statusText.textContent = S.language === "vi" ? "Sẵn sàng" : "Ready";
    }
  } catch {
    setStatus("error");
  }
}

// ── HISTORY ───────────────────────────────────────────────────────────────────
async function loadHistory() {
  try {
    const d = await (await fetch("/api/sessions")).json();
    renderHistory(d.sessions || []);
  } catch { D.historyList.innerHTML = "<p style='color:var(--text-3)'>Không tải được.</p>"; }
}

function renderHistory(sessions) {
  if (!sessions.length) {
    D.historyList.innerHTML = "<div class='empty-state'><p>Chưa có phiên nào.</p></div>";
    return;
  }
  D.historyList.innerHTML = sessions.map(s => `
    <div style="border:1px solid var(--border);border-radius:6px;padding:10px;margin-bottom:8px;cursor:pointer"
         onclick="resumeSession('${s.id}')">
      <div style="font-weight:500;font-size:13px">${s.id.substring(0,8)}…</div>
      <div style="font-size:12px;color:var(--text-2);margin-top:3px">
        ${s.mode} · ${s.level||""} · <span style="color:${s.status==="completed"?"var(--success)":"var(--accent)"}">${s.status||""}</span>
        ${s.overall_score ? ` · 📊${s.overall_score.toFixed(1)}` : ""}
      </div>
      <div style="font-size:11px;color:var(--text-3);margin-top:2px">
        ${new Date(s.created).toLocaleString(S.language==="vi"?"vi-VN":"en-US")}
      </div>
    </div>`
  ).join("");
}

window.resumeSession = function(id) {
  S.sessionId = id;
  closeHistory();
  hideWelcome();
  wsConnect();
  appendSysMsg(`Đã nối lại phiên ${id.substring(0,8)}…`, "info");
};

// ── UI HELPERS ────────────────────────────────────────────────────────────────
function syncModeUI() {
  document.querySelectorAll("#mode-toggle .toggle-btn").forEach(b =>
    b.classList.toggle("active", b.dataset.mode === S.mode));
  if (D.hintMode) D.hintMode.textContent = t("modeLabel", S.mode);
}

function syncLangUI() {
  document.querySelectorAll("#lang-toggle .lang-btn").forEach(b =>
    b.classList.toggle("active", b.dataset.lang === S.language));
  if (D.hintLang) D.hintLang.textContent = S.language.toUpperCase();
  if (D.msgInput) D.msgInput.placeholder = t("placeholder");
  updatePhase(S.phase);
}

function syncProviderUI() {
  document.querySelectorAll("#provider-toggle .provider-btn").forEach(b =>
    b.classList.toggle("active", b.dataset.provider === S.provider));
}

function updateProviderDots(active) {
  D.ollamaDot.className = "provider-dot " + (active==="ollama"?"online":"offline");
  D.claudeDot.className = "provider-dot " + (active==="claude"?"online":"offline");
}

function openSettings()  { D.settingsOverlay.classList.remove("hidden"); D.settingsPanel.classList.remove("hidden"); }
function closeSettings() { D.settingsOverlay.classList.add("hidden"); D.settingsPanel.classList.add("hidden"); }
function openHistory()   { loadHistory(); D.historyPanel.classList.remove("hidden"); }
function closeHistory()  { D.historyPanel.classList.add("hidden"); }

function applySettings() {
  const prov = $("setting-provider")?.value;
  const lang = ($("setting-lang")?.value || "vi").split("-")[0];
  const lvl  = $("setting-level")?.value;
  const tts  = $("setting-tts")?.value;
  const voice = $("setting-avatar-voice")?.checked;
  const av3d  = $("setting-avatar-3d")?.checked;
  const timer = parseInt($("setting-timer")?.value || "120");

  if (lvl)  S.level = lvl;
  if (tts)  S.ttsMode = tts;
  if (voice !== undefined) S.avatarVoice = voice;
  if (av3d  !== undefined) S.avatar3d = av3d;
  if (!isNaN(timer)) S.timerSeconds = timer;

  if (lang && lang !== S.language) { S.language = lang; syncLangUI(); }
  if (prov && prov !== S.provider && S.wsConnected) {
    S.provider = prov;
    wsSend({ type: "switch_provider", provider: prov });
    syncProviderUI();
  }
}

function autoResize(ta) {
  ta.style.height = "auto";
  ta.style.height = Math.min(ta.scrollHeight, 120) + "px";
}

// ── BINDINGS ──────────────────────────────────────────────────────────────────
function bindAll() {
  // Input
  D.msgInput.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendText(D.msgInput.value);
    }
  });
  D.msgInput.addEventListener("input", () => autoResize(D.msgInput));
  D.btnSend.addEventListener("click", () => sendText(D.msgInput.value));
  D.btnMic.addEventListener("click", () => S.recording ? stopRecording() : startRecording());

  // Space = push to talk (when not in textarea)
  document.addEventListener("keydown", e => {
    if (e.code === "Space" && document.activeElement !== D.msgInput && !e.repeat) {
      e.preventDefault(); startRecording();
    }
  });
  document.addEventListener("keyup", e => {
    if (e.code === "Space" && S.recording && document.activeElement !== D.msgInput) {
      stopRecording();
    }
  });

  // Mode toggle
  $("mode-toggle").addEventListener("click", e => {
    const btn = e.target.closest(".toggle-btn"); if (!btn) return;
    const mode = btn.dataset.mode; if (mode === S.mode) return;
    S.mode = mode; syncModeUI();
    if (S.wsConnected) wsSend({ type: "switch_mode", mode });
  });

  // Provider toggle
  $("provider-toggle").addEventListener("click", e => {
    const btn = e.target.closest(".provider-btn"); if (!btn) return;
    const prov = btn.dataset.provider; if (prov === S.provider) return;
    S.provider = prov; syncProviderUI();
    if (S.wsConnected) wsSend({ type: "switch_provider", provider: prov });
  });

  // Language toggle
  $("lang-toggle").addEventListener("click", e => {
    const btn = e.target.closest(".lang-btn"); if (!btn) return;
    const lang = btn.dataset.lang; if (lang === S.language) return;
    S.language = lang; syncLangUI();
    if (S.wsConnected) wsSend({ type: "switch_language", language: lang });
  });

  // Welcome buttons
  $("btn-start-interview").addEventListener("click", () => startSession("interviewer"));
  $("btn-start-training").addEventListener("click",  () => startSession("trainer"));

  // Settings
  $("btn-settings").addEventListener("click", openSettings);
  $("btn-close-settings").addEventListener("click", () => { applySettings(); closeSettings(); });
  D.settingsOverlay.addEventListener("click", () => { applySettings(); closeSettings(); });
  ["setting-provider","setting-lang","setting-level","setting-tts"].forEach(id =>
    $(id)?.addEventListener("change", applySettings));
  $("setting-avatar-voice")?.addEventListener("change", applySettings);
  $("setting-avatar-3d")?.addEventListener("change", applySettings);

  // History
  $("btn-history").addEventListener("click", openHistory);
  $("btn-close-history").addEventListener("click", closeHistory);

  // Session controls
  $("btn-new-session")?.addEventListener("click", () => { newSession(); closeSettings(); });
  $("btn-export")?.addEventListener("click", exportTranscript);
  $("btn-finish")?.addEventListener("click", () => { finishInterview(); closeSettings(); });

  // Report modal
  $("btn-close-report")?.addEventListener("click", closeReport);
  $("btn-report-close")?.addEventListener("click", closeReport);
  $("btn-report-export")?.addEventListener("click", exportTranscript);
  $("report-overlay")?.addEventListener("click", e => { if (e.target.id === "report-overlay") closeReport(); });

  // Code panel
  $("btn-code")?.addEventListener("click", () => {
    if (D.codePanel.classList.contains("hidden")) {
      // Request challenge from server via WS message
      if (S.wsConnected) {
        sendText(S.language==="vi"
          ? "Cho tôi một bài tập coding Java phù hợp với level của tôi."
          : "Give me a Java coding challenge appropriate for my level.");
      } else {
        openCodeChallenge({
          title: "FizzBuzz",
          description: "Viết FizzBuzz từ 1 đến n trong Java.",
          starter: "public class Main {\n    public static void main(String[] args) {\n        // TODO\n    }\n}",
        });
      }
    } else {
      D.codePanel.classList.add("hidden");
    }
  });
  $("btn-close-code")?.addEventListener("click", () => D.codePanel.classList.add("hidden"));
  $("btn-run-code")?.addEventListener("click", runCode);
  $("btn-submit-code")?.addEventListener("click", submitCode);

  // Recording overlay cancel
  D.recordingOverlay.addEventListener("click", stopRecording);

  // Ingest trigger
  $("btn-ingest")?.addEventListener("click", async () => {
    const btn = $("btn-ingest");
    btn.disabled = true; btn.textContent = "⏳ Đang nạp...";
    try {
      await fetch("/api/ingest", { method: "POST", headers: {"Content-Type":"application/json"}, body: "{}" });
      btn.textContent = "✅ Đã bắt đầu nạp";
      toast("📚 Đang quét & nạp thư mục data/ ...", "info");
      if ($("ingest-status")) $("ingest-status").textContent = "Đang quét data/ — chờ vài giây rồi kiểm tra RAG chunks.";
      setTimeout(() => { btn.disabled=false; btn.textContent="📚 Quét & nạp thư mục data/"; checkHealth(); toast("✅ Hoàn tất nạp knowledge base", "success"); }, 4000);
    } catch {
      btn.textContent = "❌ Lỗi"; btn.disabled = false;
      toast("❌ Không nạp được knowledge base", "error");
    }
  });

  // Upload CV
  bindUpload("btn-upload-cv", "cv-file", "cv", "upload-status");
  // Upload knowledge doc
  bindUpload("btn-upload-kb", "kb-file", "knowledge", null);
}

// Gan su kien upload file (CV hoac tai lieu)
function bindUpload(btnId, inputId, kind, statusId) {
  const btn = $(btnId), input = $(inputId);
  if (!btn || !input) return;
  btn.addEventListener("click", () => input.click());
  input.addEventListener("change", async () => {
    const file = input.files && input.files[0];
    if (!file) return;
    const status = statusId ? $(statusId) : null;
    const origText = btn.textContent;
    btn.disabled = true;
    btn.textContent = `⏳ Đang tải ${file.name.slice(0, 20)}...`;
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`/api/upload?kind=${kind}`, { method: "POST", body: fd });
      const data = await res.json();
      if (res.ok && data.status === "ok") {
        btn.textContent = `✅ ${data.chunks} chunks`;
        if (status) status.textContent = `Đã nạp "${data.filename}" (${data.chunks} chunks).`;
        toast(`📄 Đã nạp "${data.filename}" → ${data.chunks} chunks`, "success");
        checkHealth();
      } else {
        btn.textContent = "❌ Lỗi tải lên";
        if (status) status.textContent = data.error || data.warning || "Lỗi không xác định.";
        toast(data.error || "Lỗi tải lên", "error");
      }
    } catch (e) {
      btn.textContent = "❌ Lỗi";
      if (status) status.textContent = String(e);
      toast("Lỗi tải lên: " + e.message, "error");
    } finally {
      input.value = "";
      setTimeout(() => { btn.disabled = false; btn.textContent = origText; }, 3500);
    }
  });
}

// ── INIT ──────────────────────────────────────────────────────────────────────
async function init() {
  const params = new URLSearchParams(location.search);
  if (params.get("mode"))  S.mode     = params.get("mode");
  if (params.get("lang"))  S.language = params.get("lang");
  if (params.get("level")) S.level    = params.get("level");

  // Pre-generate session ID (will be replaced on actual session creation)
  S.sessionId = (typeof crypto !== "undefined" && crypto.randomUUID)
    ? crypto.randomUUID() : Math.random().toString(36).slice(2);

  syncModeUI(); syncLangUI(); syncProviderUI();
  setAgentState("idle"); setStatus("connecting");
  autoResize(D.msgInput);
  bindAll();

  await checkHealth();

  // Preload voices for browser TTS
  if (window.speechSynthesis) {
    speechSynthesis.getVoices();
    speechSynthesis.addEventListener("voiceschanged", () => speechSynthesis.getVoices());
  }

  // Init 3D avatar
  if (S.avatar3d && window.Avatar3D && D.avatarScene3d) {
    setTimeout(() => Avatar3D.init("avatar-scene-3d"), 200);
  }
}

init();
