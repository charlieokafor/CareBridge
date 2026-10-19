/* CareBridge web app: staff sign-in, Standard Consultation, Emergency, patient bedside screen,
   live audit view. One codebase for iPad, phone and laptop. */
'use strict';

// ---------------------------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------------------------
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const timeOf = (ms) => new Date(ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
const store = {
  get(k, d) { try { const v = localStorage.getItem('cb.' + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem('cb.' + k, JSON.stringify(v)); } catch { /* private mode */ } },
  del(k) { try { localStorage.removeItem('cb.' + k); } catch { /* ignore */ } },
};

const ICONS = {
  mic: '<path d="M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3z"/><path d="M19 11a7 7 0 0 1-14 0M12 18v3"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="2.5"/>',
  bolt: '<path d="M13 2 4 14h7l-1 8 9-12h-7l1-8z"/>',
  stethoscope: '<path d="M6 3H5v6a5 5 0 0 0 10 0V3h-1"/><path d="M10 14v1a5 5 0 0 0 10 0v-3"/><circle cx="20" cy="10" r="2"/>',
  bridge: '<path d="M2 17h20M4 17v-6M20 17v-6M2 11c4-5 16-5 20 0M8 17v-4.5M12 17v-5.5M16 17v-4.5"/>',
  lock: '<rect x="5" y="11" width="14" height="10" rx="2.5"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  unlock: '<rect x="5" y="11" width="14" height="10" rx="2.5"/><path d="M8 11V8a4 4 0 0 1 7.5-2"/>',
  chevR: '<path d="m9 6 6 6-6 6"/>',
  chevL: '<path d="m15 6-6 6 6 6"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  checkCircle: '<circle cx="12" cy="12" r="9"/><path d="m8 12.5 3 3 5-6"/>',
  warn: '<path d="M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
  hand: '<path d="M18 11V6a2 2 0 0 0-4 0v5M14 10V4a2 2 0 0 0-4 0v6M10 10.5V6a2 2 0 0 0-4 0v8"/><path d="M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.9-6-2.4l-3.6-3.6a2 2 0 0 1 2.8-2.8L7 15"/>',
  speaker: '<path d="M11 5 6 9H2v6h4l5 4V5z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M19 5a10 10 0 0 1 0 14"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  clipboard: '<rect x="5" y="4" width="14" height="17" rx="2.5"/><path d="M9 4.5V3h6v1.5M9 10h6M9 14h6M9 18h3"/>',
  video: '<rect x="2" y="6" width="14" height="12" rx="2.5"/><path d="m16 10 6-3v10l-6-3"/>',
  tablet: '<rect x="4" y="2.5" width="16" height="19" rx="2.5"/><path d="M11 18.5h2"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  refresh: '<path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/>',
  trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
  keyboard: '<rect x="2" y="6" width="20" height="12" rx="2.5"/><path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10"/>',
  doc: '<path d="M14 3H6v18h12V7z"/><path d="M14 3v4h4M9 13h6M9 17h6"/>',
  shield: '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/><path d="m9 12 2 2 4-4"/>',
  play: '<path d="M7 4v16l13-8z"/>',
  pause: '<rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/>',
  replay: '<path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/>',
  signout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5M21 12H9"/>',
  phone: '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z"/>',
  download: '<path d="M12 3v12M7 10l5 5 5-5M5 21h14"/>',
  waveform: '<path d="M3 12h2M7 8v8M11 4v16M15 7v10M19 10v4"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5h.01"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><circle cx="17" cy="9" r="2.5"/><path d="M16 14.2a5 5 0 0 1 5.5 4.8"/>',
  drop: '<path d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z"/>',
  question: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.7M12 17h.01"/>',
  toilet: '<path d="M7 3h6v6H7zM5 9h14v2a6 6 0 0 1-6 6h-2a6 6 0 0 1-6-6V9zM9 17l-1 4h8l-1-4"/>',
};
const icon = (n, cls = '') => `<svg class="i ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[n] || ''}</svg>`;
const fillIcon = (n) => icon(n, 'fill');

// ---------------------------------------------------------------------------------------------
// App state, settings, API
// ---------------------------------------------------------------------------------------------
const S = {
  token: store.get('token', null), user: store.get('user', null), cfg: null, health: null,
  settings: Object.assign({ scale: 1, contrast: false, theme: 'auto', voice: 'auto', rate: 0.95 }, store.get('settings', {})),
  cleanup: [],
};

function applySettings() {
  const r = document.documentElement;
  r.style.setProperty('--scale', S.settings.scale);
  r.dataset.contrast = S.settings.contrast ? 'high' : 'normal';
  if (S.settings.theme === 'auto') delete r.dataset.theme; else r.dataset.theme = S.settings.theme;
  store.set('settings', S.settings);
}
applySettings();

async function api(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  if (S.token) headers.Authorization = 'Bearer ' + S.token;
  let body = opts.body;
  if (body && !(body instanceof FormData)) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(body); }
  const res = await fetch(path, { method: opts.method || (body ? 'POST' : 'GET'), headers, body });
  if (res.status === 401 && path !== '/api/login') { signOut(); throw new Error('Please sign in again'); }
  if (opts.raw) return res;
  if (!res.ok) {
    let msg = res.statusText || 'Request failed';
    try { msg = (await res.json()).detail || msg; } catch { /* not json */ }
    throw new Error(typeof msg === 'string' ? msg : 'Request failed');
  }
  return res.status === 204 ? null : res.json();
}

async function ensureConfig() {
  if (S.cfg) return S.cfg;
  try { S.cfg = await api('/api/config'); store.set('cfg', S.cfg); }
  catch (e) { S.cfg = store.get('cfg', null); if (!S.cfg) throw e; }   // offline: use this device's copy
  return S.cfg;
}
async function refreshHealth() {
  try { S.health = await api('/api/health'); } catch { S.health = null; }
  return S.health;
}
const L = (code) => S.cfg?.languages?.[code] || { name: code, native: code, dir: 'ltr', bcp47: code };
const pui = (lang) => S.cfg?.patientUi?.[lang] || S.cfg?.patientUi?.uk || {};

function signOut() {
  S.token = null; S.user = null; S.cfg = null;
  store.del('token'); store.del('user');
  if (location.hash !== '#/login') location.hash = '#/login';
}

// ---------------------------------------------------------------------------------------------
// UI helpers: render, toast, sheets
// ---------------------------------------------------------------------------------------------
const appEl = () => $('#app');
function render(html) { appEl().innerHTML = html; window.scrollTo(0, 0); }
function on(sel, evt, fn, root = document) { $$(sel, root).forEach((el) => el.addEventListener(evt, fn)); }

let toastTimer;
function toast(msg, ms = 2600) {
  $('.toast')?.remove();
  const t = document.createElement('div');
  t.className = 'toast'; t.setAttribute('role', 'status'); t.textContent = msg;
  document.body.appendChild(t);
  clearTimeout(toastTimer); toastTimer = setTimeout(() => t.remove(), ms);
}

function openSheet(html, mount) {
  const bd = document.createElement('div');
  bd.className = 'sheet-backdrop';
  bd.innerHTML = `<div class="sheet" role="dialog" aria-modal="true"><div class="grabber"></div>${html}</div>`;
  document.body.appendChild(bd);
  const close = () => bd.remove();
  bd.addEventListener('click', (e) => { if (e.target === bd) close(); });
  on('[data-close]', 'click', close, bd);
  mount?.(bd, close);
  return close;
}

function navbar({ left = '', title = '', right = '' } = {}) {
  return `<header class="navbar"><div class="navbar-inner"><div class="left">${left}</div><div class="title">${title}</div><div class="right">${right}</div></div></header>`;
}

function tierBadge(tier) {
  if (tier === 'red') return `<span class="tier red">${icon('hand')} Interpreter</span>`;
  if (tier === 'amber') return `<span class="tier amber">${icon('warn')} Clinical</span>`;
  return `<span class="tier green">${icon('checkCircle')} Routine</span>`;
}
function meaningChip(m) {
  if (!m) return '';
  const cls = m.score >= 80 ? 'ok' : m.score >= 60 ? 'warn' : 'bad';
  return `<span class="chip ${cls}" title="Back-translation similarity">${icon(cls === 'ok' ? 'check' : 'warn')} ${esc(m.verdict)} · ${m.score}</span>`;
}
function checkChips(t) {
  const c = (t.checks || []).map((k) => `<span class="chip ${k.ok ? 'ok' : 'bad'}" title="${esc(k.detail)}">${icon(k.ok ? 'check' : 'x')} ${esc(k.name)}</span>`);
  const g = (t.glossary || []).map((k) => `<span class="chip ${k.ok ? 'ok' : 'warn'}" title="Medical glossary">${icon(k.ok ? 'check' : 'warn')} ${esc(k.term)}</span>`);
  return c.concat(g).join('');
}

// ---------------------------------------------------------------------------------------------
// Audio: unlock, speak (server voice or device voice), record, voice-activity loop
// ---------------------------------------------------------------------------------------------
const SILENT_WAV = 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=';
const AudioKit = {
  ctx: null, el: null, unlocked: false,
  unlock() {
    try {
      if (!this.ctx) this.ctx = new (window.AudioContext || window.webkitAudioContext)();
      if (this.ctx.state === 'suspended') this.ctx.resume();
    } catch { /* no web audio */ }
    if (!this.el) { this.el = new Audio(); this.el.setAttribute('playsinline', ''); }
    if (!this.unlocked) {
      this.unlocked = true;
      this.el.src = SILENT_WAV; this.el.play().catch(() => {});
      try { const u = new SpeechSynthesisUtterance(' '); u.volume = 0; speechSynthesis.speak(u); } catch { /* none */ }
    }
  },
};
document.addEventListener('pointerdown', () => AudioKit.unlock(), { once: false, passive: true });

function stopSpeaking() {
  try { speechSynthesis.cancel(); } catch { /* none */ }
  if (AudioKit.el) { AudioKit.el.pause(); AudioKit.el.onended = null; }
}
function pickVoice(tag) {
  const vs = (window.speechSynthesis?.getVoices?.() || []);
  const t = tag.toLowerCase(); const p = t.slice(0, 2);
  return vs.find((v) => v.lang.toLowerCase().replace('_', '-') === t) || vs.find((v) => v.lang.toLowerCase().startsWith(p));
}
// Resolves true only if speech actually played. Never reads text with a voice from another language.
function deviceSpeak(text, lang) {
  return new Promise((resolve) => {
    if (!('speechSynthesis' in window)) return resolve(false);
    const u = new SpeechSynthesisUtterance(text);
    u.lang = L(lang).bcp47; u.rate = S.settings.rate; u.volume = 1;
    const v = pickVoice(u.lang);
    if (!v && lang !== 'en') return resolve(false);
    if (v) u.voice = v;
    let done = false; const fin = (ok) => { if (!done) { done = true; resolve(ok); } };
    u.onend = () => fin(true); u.onerror = () => fin(false);
    speechSynthesis.speak(u);
    setTimeout(() => fin(true), 4000 + text.length * 120);
  });
}
function playBlob(blob) {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(blob);
    const el = AudioKit.el || (AudioKit.el = new Audio());
    let done = false; const fin = (ok) => { if (!done) { done = true; URL.revokeObjectURL(url); resolve(ok); } };
    el.onended = () => fin(true); el.onerror = () => fin(false);
    el.src = url; el.volume = 1; el.muted = false; el.playbackRate = S.settings.rate;
    el.play().catch(() => fin(false));
  });
}
// Server voice first (every licensed language has one, normalised to full volume), then this device's voice.
async function speak(text, lang, { force = false } = {}) {
  stopSpeaking();
  if (!text) return false;
  AudioKit.unlock();
  if (force || S.settings.voice !== 'device') {
    try {
      const r = await api('/api/tts', { body: { text, lang }, raw: true });
      if (r.status === 200 && await playBlob(await r.blob())) return true;
    } catch { /* fall back to the device voice */ }
  }
  return deviceSpeak(text, lang);
}

function pickMime() {
  if (!window.MediaRecorder) return '';
  return ['audio/webm;codecs=opus', 'audio/mp4', 'audio/webm', 'audio/ogg;codecs=opus'].find((m) => MediaRecorder.isTypeSupported?.(m)) || '';
}

class Recorder {
  // closeVoice: for loud rooms (Emergency). Automatic gain would boost the background between words until it is
  // as loud as the person holding the phone; without it, the closest voice stays clearly the loudest, which is
  // what the server relies on. Noise suppression is off: in our benchmark every noise filter made speech
  // recognition worse (eval/aws_compare), and speech vendors advise sending unprocessed audio.
  constructor({ closeVoice = false } = {}) { this.closeVoice = closeVoice; }
  async open() {
    if (this.stream) return;
    if (!navigator.mediaDevices?.getUserMedia) throw new Error('This browser cannot use the microphone. Use Safari or Chrome over https.');
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: false, autoGainControl: !this.closeVoice, channelCount: 1 } });
    AudioKit.unlock();
    try {
      this.src = AudioKit.ctx.createMediaStreamSource(this.stream);
      this.an = AudioKit.ctx.createAnalyser(); this.an.fftSize = 1024;
      this.src.connect(this.an); this.buf = new Float32Array(this.an.fftSize);
    } catch { this.an = null; }
  }
  level() {
    if (!this.an) return 0.05;
    this.an.getFloatTimeDomainData(this.buf);
    let s = 0; for (let i = 0; i < this.buf.length; i++) s += this.buf[i] * this.buf[i];
    return Math.sqrt(s / this.buf.length);
  }
  start() {
    this.chunks = []; this.mime = pickMime();
    this.mr = new MediaRecorder(this.stream, this.mime ? { mimeType: this.mime } : undefined);
    this.mr.ondataavailable = (e) => { if (e.data && e.data.size) this.chunks.push(e.data); };
    this.mr.start(250); this.t0 = Date.now();
  }
  stop() {
    return new Promise((resolve) => {
      if (!this.mr || this.mr.state === 'inactive') return resolve(null);
      this.mr.onstop = () => resolve(new Blob(this.chunks, { type: this.mr.mimeType || this.mime || 'audio/webm' }));
      this.mr.stop();
    });
  }
  close() {
    try { if (this.mr && this.mr.state !== 'inactive') this.mr.stop(); } catch { /* ignore */ }
    this.stream?.getTracks().forEach((t) => t.stop());
    try { this.src?.disconnect(); } catch { /* ignore */ }
    this.stream = null; this.an = null;
  }
}

// Hands-free loop for Emergency mode: waits for speech, records it, stops after a short silence.
class VoiceLoop {
  constructor({ onUtterance, onState }) { this.onUtterance = onUtterance; this.onState = onState; this.rec = new Recorder({ closeVoice: true }); }
  async start() {
    await this.rec.open();
    // Calibrate the room's noise level for half a second
    let n = 0, sum = 0; const t0 = Date.now();
    while (Date.now() - t0 < 500) { sum += this.rec.level(); n++; await sleep(40); }
    this.noise = Math.max(0.004, sum / Math.max(1, n));
    this.running = true; this.cycle();
  }
  cycle() {
    if (!this.running) return;
    this.rec.start();
    let speech = 0, silence = 0, heard = false; const started = Date.now();
    this.onState?.('listening');
    clearInterval(this.timer);
    this.timer = setInterval(async () => {
      const lvl = this.rec.level();
      const thr = Math.max(0.012, this.noise * 2.6);
      // Hysteresis: speech starts above the threshold but only ends when it falls well below it
      if (lvl > (heard ? thr * 0.6 : thr)) { speech += 50; silence = 0; if (!heard && speech >= 250) { heard = true; this.onState?.('hearing'); } }
      else { if (heard) silence += 50; else { speech = Math.max(0, speech - 50); this.noise = this.noise * 0.97 + lvl * 0.03; } }
      const age = Date.now() - started;
      if ((heard && silence >= 1000) || (heard && age > 18000)) {
        clearInterval(this.timer);
        const blob = await this.rec.stop();
        this.running = false;
        if (speech < 450) { this.running = true; this.cycle(); return; }   // a cough or a bump, not speech
        this.onUtterance(blob);
      } else if (!heard && age > 9000) {
        clearInterval(this.timer); await this.rec.stop(); this.cycle();
      }
    }, 50);
  }
  async resume() {
    if (this.running) return;
    if (!this.rec.stream) await this.rec.open();
    this.running = true; this.cycle();
  }
  pause() { this.running = false; clearInterval(this.timer); this.rec.stop(); this.rec.close(); }
  stop() { this.pause(); }
}

// What CareBridge's safety layer noticed about a recording: corrected medicine names, sound-alike medicines it
// would not guess between, and numbers or medicine names heard with low confidence. Shown before anything is sent.
function asrNotes(tr) {
  if (!tr) return '';
  const items = [];
  (tr.ambiguous || []).forEach((a) => items.push(`<b>“${esc(a.heard)}”</b> sounds like ${a.options.map((o) => `<b>${esc(o)}</b>`).join(' or ')}. Ask the patient to show the packet or spell it.`));
  (tr.corrections || []).forEach((c) => items.push(`Heard “${esc(c.from)}”, matched to <b>${esc(c.to)}</b>. Confirm it.`));
  if ((tr.lowConfidenceWords || []).length) items.push(`Unclear: ${tr.lowConfidenceWords.map((w) => `<b>${esc(w)}</b>`).join(', ')}. Confirm these words.`);
  return items.length ? `<div class="banner amber mt">${icon('warn')}<div class="b-body"><div class="b-title">Check before sending</div>${items.join('<br>')}</div></div>` : '';
}

async function transcribe(blob, lang, candidates) {
  const fd = new FormData();
  const t = blob.type || '';
  const ext = t.includes('mp4') ? 'm4a' : t.includes('ogg') ? 'ogg' : t.includes('wav') ? 'wav' : 'webm';
  fd.append('audio', blob, 'speech.' + ext);
  if (lang) fd.append('lang', lang);
  if (candidates) fd.append('candidates', candidates.join(','));
  return api('/api/transcribe', { body: fd });
}

// ---------------------------------------------------------------------------------------------
// Live session sync (every device polls the same conversation)
// ---------------------------------------------------------------------------------------------
class Sync {
  constructor(sid, onUpdate) { this.sid = sid; this.onUpdate = onUpdate; this.since = 0; this.ids = new Set(); this.turns = []; }
  async start() { await this.poll(); this.timer = setInterval(() => this.poll(), 1200); }
  stop() { clearInterval(this.timer); }
  add(t) { if (t && !this.ids.has(t.id)) { this.ids.add(t.id); this.turns.push(t); this.since = Math.max(this.since, t.ts); } }
  async poll() {
    if (this.busy) return; this.busy = true;
    try {
      const d = await api(`/api/sessions/${this.sid}?since=${this.since}`);
      const fresh = [];
      for (const t of d.turns) if (!this.ids.has(t.id)) { this.add(t); fresh.push(t); }
      this.session = d.session;
      this.onUpdate(d.session, fresh);
    } catch { /* offline for a moment */ } finally { this.busy = false; }
  }
}
let activityAt = 0;
function setActivity(sid, who, state) {
  const now = Date.now();
  if (state !== 'idle' && now - activityAt < 1500) return;
  activityAt = now;
  api(`/api/sessions/${sid}`, { method: 'PATCH', body: { activity: { who, state } } }).catch(() => {});
}

// ---------------------------------------------------------------------------------------------
// Router
// ---------------------------------------------------------------------------------------------
const ROUTES = [
  [/^#\/login$/, viewLogin], [/^#\/home$/, viewHome], [/^#\/standard\/(\w+)$/, viewStandard],
  [/^#\/emergency\/(\w+)$/, viewEmergency], [/^#\/patient\/(\w+)$/, viewPatient], [/^#\/observer\/(\w+)$/, viewObserver],
  [/^#\/audit$/, viewAudit], [/^#\/settings$/, viewSettings], [/^#\/brief\/(\w+)$/, viewBrief], [/^#\/phrasebook$/, viewPhrasebook],
];
function go(h) { if (location.hash === h) route(); else location.hash = h; }
async function route() {
  S.cleanup.forEach((f) => { try { f(); } catch { /* ignore */ } }); S.cleanup = [];
  stopSpeaking(); document.body.className = '';
  $$('.sheet-backdrop').forEach((b) => b.remove());
  const h = location.hash || '#/home';
  if (!S.token && h !== '#/login') return go('#/login');
  for (const [re, fn] of ROUTES) {
    const m = h.match(re);
    if (m) {
      try { if (fn !== viewLogin) await ensureConfig(); await fn(...m.slice(1)); }
      catch (e) { render(`${navbar({ left: `<a class="navlink" href="#/home">${icon('chevL')} Home</a>` })}<div class="page narrow"><div class="empty">${icon('warn')}<p>${esc(e.message)}</p><button class="btn primary" onclick="location.reload()">Try again</button></div></div>`); }
      return;
    }
  }
  go('#/home');
}
window.addEventListener('hashchange', route);

// ---------------------------------------------------------------------------------------------
// Sign in
// ---------------------------------------------------------------------------------------------
function viewLogin() {
  render(`<div class="login-wrap"><div class="login-card">
    <div class="app-icon">${icon('bridge')}</div>
    <h1>CareBridge</h1>
    <p class="lead">Safe conversations across languages</p>
    <form class="card" id="loginForm" autocomplete="on">
      <label class="field"><span>Your name</span><input class="input" name="name" autocomplete="name" required placeholder="e.g. Nurse Aoife Murphy" value="${esc(store.get('lastName', ''))}"></label>
      <label class="field"><span>Staff code</span><input class="input" name="code" type="password" inputmode="numeric" autocomplete="current-password" required placeholder="6-digit code"></label>
      <div class="error-text" id="loginErr" role="alert"></div>
      <button class="btn primary block" type="submit">Sign in</button>
    </form>
    <p class="fineprint">For hospital staff only. Translations are AI-generated and checked automatically.<br>They do not replace a professional interpreter for high-stakes conversations.</p>
  </div></div>`);
  on('#loginForm', 'submit', async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    const btn = $('button[type=submit]', e.target); btn.disabled = true;
    try {
      const r = await api('/api/login', { body: { name: f.get('name'), code: f.get('code') } });
      S.token = r.token; S.user = r.name;
      store.set('token', r.token); store.set('user', r.name); store.set('lastName', r.name);
      go('#/home');
    } catch (err) { $('#loginErr').textContent = err.message; btn.disabled = false; }
  });
}

// ---------------------------------------------------------------------------------------------
// Home dashboard
// ---------------------------------------------------------------------------------------------
async function micStatus() {
  if (!navigator.mediaDevices?.getUserMedia) return ['red', 'Microphone unavailable'];
  try {
    const p = await navigator.permissions.query({ name: 'microphone' });
    if (p.state === 'granted') return ['green', 'Microphone ready'];
    if (p.state === 'denied') return ['red', 'Microphone blocked'];
  } catch { /* Safari */ }
  return ['blue', 'Microphone asks on first use'];
}
function modelsPill() {
  const h = S.health;
  if (!h) return `<span class="pill red"><span class="dot"></span>Server unreachable</span>`;
  return h.ready ? `<span class="pill green"><span class="dot"></span>AI models ready</span>`
    : `<span class="pill orange"><span class="dot"></span>AI models loading…</span>`;
}

async function viewHome() {
  render(`${navbar({ title: '', right: `<button class="navlink" id="settingsBtn" aria-label="Settings">${icon('gear')}</button><button class="navlink" id="outBtn" aria-label="Sign out">${icon('signout')}</button>` })}
  <main class="page">
    <h1 class="large-title">CareBridge</h1>
    <p class="subtitle">Signed in as ${esc(S.user || '')}. Choose how to start.</p>
    ${navigator.onLine ? '' : `<div class="banner amber">${icon('warn')}<div class="b-body"><div class="b-title">You are offline</div>The offline phrasebook still works. Everything you do is added to the audit log when you are back online.</div></div>`}
    <div class="status-bar" id="statusBar"><span class="pill"><span class="spinner" style="width:12px;height:12px;border-width:2px"></span> Checking…</span></div>
    <div class="modes">
      <button class="mode-card standard" id="stdBtn">
        <div class="mode-icon">${icon('stethoscope')}</div>
        <h2>Standard Consultation</h2>
        <p>Check every sentence before it is spoken: editable transcript, highlighted medical details and a locked language pair.</p>
        <span class="mode-cta">Start consultation ${icon('chevR')}</span>
      </button>
      <button class="mode-card emergency" id="emBtn">
        <span class="tag">ONE TAP</span>
        <div class="mode-icon">${icon('bolt')}</div>
        <h2>Emergency</h2>
        <p>One tap to start. Tap to talk for each speaker, or go hands-free in a quiet room. Medical alerts are shown but never slow you down.</p>
        <span class="mode-cta">${icon('mic')} START NOW</span>
      </button>
    </div>
    <div class="section-title">More</div>
    <div class="list">
      <button class="list-row" id="joinBtn"><span class="row-icon" style="background:#30b0c7">${icon('tablet')}</span><span class="row-text"><span class="row-title">Join a session</span><br><span class="row-sub">Use this device as the patient's screen or a live audit view</span></span><span class="chev">${icon('chevR')}</span></button>
      <button class="list-row" id="pbBtn"><span class="row-icon" style="background:#34c759">${icon('doc')}</span><span class="row-text"><span class="row-title">Offline phrasebook</span><br><span class="row-sub">Checked phrases, tap answers, pain scale and body map. Works without Wi-Fi</span></span><span class="chev">${icon('chevR')}</span></button>
      <button class="list-row" id="auditBtn"><span class="row-icon" style="background:#5856d6">${icon('clipboard')}</span><span class="row-text"><span class="row-title">Audit log</span><br><span class="row-sub">Every conversation, risk tier, check and escalation</span></span><span class="chev">${icon('chevR')}</span></button>
      <button class="list-row" disabled><span class="row-icon" style="background:#8e8e93">${icon('video')}</span><span class="row-text"><span class="row-title">Telemedicine</span><br><span class="row-sub">Remote appointments with live captions · Coming next</span></span></button>
      <button class="list-row" id="setBtn2"><span class="row-icon" style="background:#636366">${icon('gear')}</span><span class="row-text"><span class="row-title">Settings</span><br><span class="row-sub">Text size, contrast, voice, privacy</span></span><span class="chev">${icon('chevR')}</span></button>
    </div>
  </main>`);
  on('#settingsBtn, #setBtn2', 'click', () => go('#/settings'));
  on('#outBtn', 'click', signOut);
  on('#auditBtn', 'click', () => go('#/audit'));
  on('#pbBtn', 'click', () => go('#/phrasebook'));
  syncOfflineLog();
  on('#joinBtn', 'click', openJoinSheet);
  on('#stdBtn', 'click', openStandardSetup);
  on('#emBtn', 'click', async () => {
    AudioKit.unlock();
    try {
      const s = await api('/api/sessions', { body: { mode: 'emergency', patientLang: null } });
      go('#/emergency/' + s.id);
    } catch (e) { toast(e.message); }
  });
  const [mc, ml] = await micStatus();
  await refreshHealth();
  const bar = $('#statusBar');
  if (bar) bar.innerHTML = `<span class="pill ${mc}"><span class="dot"></span>${ml}</span>${modelsPill()}<span class="pill blue">${icon('shield')} Audit on · audio never stored</span>`;
}

const TIER = { pilot: ['ok', 'Pilot · voice'], speech: ['info', 'Speech + text'], text: ['', 'Text + taps'] };
function tierChip(c) { const [cls, label] = TIER[L(c).tier] || TIER.text; return `<span class="chip ${cls}">${label}</span>`; }
function langTile(c, selected) {
  return `<button class="lang-tile" data-lang="${c}" data-search="${esc((L(c).name + ' ' + L(c).native).toLowerCase())}" aria-pressed="${selected === c}"><span class="native" dir="${L(c).dir}">${esc(L(c).native)}</span><span class="eng">${esc(L(c).name)}</span>${tierChip(c)}</button>`;
}
function langTiles(selected, includeAuto, only = null) {
  const allowed = (c) => !only || only.includes(c);
  const common = (S.cfg.commonLangs || []).filter(allowed);
  const rest = S.cfg.patientLangs.filter((c) => !common.includes(c) && allowed(c));
  const auto = includeAuto ? `<button class="lang-tile" data-lang="" data-search="detect automatic" aria-pressed="${!selected}"><span class="native">${icon('globe')} Detect</span><span class="eng">From the patient's first words</span></button>` : '';
  return `<input class="input lang-search" type="search" placeholder="Search ${common.length + rest.length} languages" aria-label="Search languages" autocomplete="off">
    <div class="section-title" style="margin-left:4px">Most booked at TUH</div>
    <div class="lang-grid">${common.map((c) => langTile(c, selected)).join('')}${auto}</div>
    <div class="section-title" style="margin-left:4px">All languages</div>
    <div class="lang-grid">${rest.map((c) => langTile(c, selected)).join('')}</div>
    <p class="fineprint">Pilot: checked phrases and server voice. Speech + text: speak or type. Text + taps: no speech model yet, so type or use tap answers.</p>`;
}
function bindLangTiles(root, onPick) {
  const inp = $('.lang-search', root);
  inp?.addEventListener('input', () => {
    const q = inp.value.trim().toLowerCase();
    $$('.lang-tile[data-search]', root).forEach((t) => { t.style.display = !q || t.dataset.search.includes(q) ? '' : 'none'; });
  });
  on('.lang-tile', 'click', (e) => {
    $$('.lang-tile', root).forEach((t) => t.setAttribute('aria-pressed', t === e.currentTarget));
    onPick(e.currentTarget.dataset.lang || null);
  }, root);
}

function openStandardSetup() {
  AudioKit.unlock();
  let lang = store.get('lastLang', 'uk');
  openSheet(`<div class="sheet-head"><h3>New consultation</h3><button class="navlink" data-close>Cancel</button></div>
    <input class="input" id="mrn" placeholder="Patient record number (optional)" autocomplete="off" aria-label="Patient record number (optional)">
    <p class="muted" style="margin:14px 4px 4px">Tap the patient's language to start.</p>
    <div id="tiles">${langTiles(lang, true)}</div>`, (bd, close) => {
    let starting = false;
    bindLangTiles(bd, async (code) => {   // one tap: no scrolling to a separate Start button
      if (starting) return; starting = true;
      try {
        if (code) store.set('lastLang', code);
        const s = await api('/api/sessions', { body: { mode: 'standard', patientLang: code, mrn: $('#mrn', bd).value } });
        close(); go('#/standard/' + s.id);
      } catch (e) { starting = false; toast(e.message); }
    });
  });
}

function openJoinSheet() {
  let role = 'patient';
  openSheet(`<div class="sheet-head"><h3>Join a session</h3><button class="navlink" data-close>Cancel</button></div>
    <p class="muted">Enter the 4-digit code shown on the clinician's screen.</p>
    <input class="input kbd" id="code" inputmode="numeric" maxlength="6" placeholder="0000" style="text-align:center;min-height:76px" autocomplete="off">
    <div class="section-title" style="margin-left:4px">Use this device as</div>
    <div class="segmented" id="roleSeg"><button aria-pressed="true" data-role="patient">${icon('users')} Patient</button><button aria-pressed="false" data-role="brief">${icon('phone')} Interpreter</button><button aria-pressed="false" data-role="observer">${icon('clipboard')} Audit</button></div>
    <div class="error-text" id="joinErr"></div>
    <button class="btn primary block xl" id="joinGo">Join</button>`, (bd, close) => {
    on('#roleSeg button', 'click', (e) => { role = e.currentTarget.dataset.role; $$('#roleSeg button', bd).forEach((b) => b.setAttribute('aria-pressed', b.dataset.role === role)); }, bd);
    setTimeout(() => $('#code', bd).focus(), 300);
    on('#joinGo', 'click', async () => {
      AudioKit.unlock();
      try {
        const s = await api('/api/sessions/join', { body: { code: $('#code', bd).value } });
        close(); go(`#/${role}/${s.id}`);
      } catch (e) { $('#joinErr', bd).textContent = e.message; }
    }, bd);
  });
}

// ---------------------------------------------------------------------------------------------
// Shared pieces for consultation screens
// ---------------------------------------------------------------------------------------------
function keyFacts(turns) {
  const facts = new Map();
  for (const t of turns) {
    if (t.type !== 'utterance') continue;
    const en = t.speaker === 'patient' ? t.translation : '';
    const m = en.match(/allerg(?:ic|y|ies) (?:to )?([\w-]+(?: [\w-]+)?)/i);
    if (m && !/^(any|anything|something|medicines?)$/i.test(m[1])) facts.set('allergy', ['red', `Allergy: ${m[1].replace(/[.,]$/, '')}`]);
    if (t.phraseId === 'pain_scale_reply') { const n = t.original.match(/\d+/); if (n) facts.set('pain', ['amber', `Pain ${n[0]}/10`]); }
    if (t.speaker === 'patient' && !t.bodyRegions && /\b(left|right)\b/i.test(en)) facts.set('side', ['amber', `Side: ${en.match(/\b(left|right)\b/i)[1].toLowerCase()}`]);
    if (t.speaker === 'patient' && /pregnan/i.test(en)) facts.set('preg', ['amber', 'Pregnancy mentioned']);
    if (t.bodyRegions) facts.set('where', ['amber', 'Pain: ' + t.bodyRegions.map((r) => S.cfg.bodyRegions[r] || r).join(', ')]);
  }
  return [...facts.values()].map(([c, txt]) => `<span class="keyfact ${c === 'amber' ? 'amber' : ''}">${icon('warn')} ${esc(txt)}</span>`).join('');
}

function bubble(t, { speakable = true } = {}) {
  if (t.type === 'event') {
    const ic = { escalation: 'hand', override: 'warn', consent: 'checkCircle', language: 'globe', device: 'tablet', session: 'info' }[t.kind] || 'info';
    return `<div class="event ${esc(t.kind)}">${icon(ic)} ${esc(t.detail)} · ${timeOf(t.ts)}</div>`;
  }
  const src = L(t.srcLang), tgt = L(t.tgtLang);
  const dirArrow = `${t.srcLang.toUpperCase()} → ${t.tgtLang.toUpperCase()}`;
  const speakBtn = speakable ? `<button class="speak-btn" data-speak="${esc(t.id)}">${fillIcon('play')} ${t.speaker === 'clinician' ? 'Speak to patient' : 'Play'}</button>` : '';
  const engine = `<span class="chip" title="Translation engine">${esc(t.engine)}</span>`;
  const statusChip = t.status === 'fail' ? `<span class="chip bad">${icon('warn')} Confirm verbally</span>` : '';
  if (t.speaker === 'clinician') {
    return `<div class="bubble clinician">
      <div class="meta"><strong>${esc(t.by)}</strong> · Clinician · ${timeOf(t.ts)} · ${dirArrow} ${tierBadge(t.risk.tier)} ${t.mode === 'emergency' ? '<span class="chip bad">Emergency</span>' : ''}</div>
      <div class="primary">${esc(t.plain)}</div>
      ${t.plain !== t.original ? `<div class="secondary">Said: “${esc(t.original)}”</div>` : ''}
      <div class="translation" dir="${tgt.dir}" lang="${esc(t.tgtLang)}">${esc(t.translation)}</div>
      <div class="row">${speakBtn}${meaningChip(t.meaning)}${checkChips(t)}${statusChip}</div>
      <details><summary>Back-translation and details</summary><p dir="${src.dir}">“${esc(t.backTranslation)}”</p><div class="row">${engine}${t.override ? `<span class="chip bad">Override: ${esc(t.override)}</span>` : ''}${t.latencyMs ? `<span class="chip">${t.latencyMs.total} ms</span>` : ''}</div></details>
    </div>`;
  }
  return `<div class="bubble patient">
    <div class="meta"><strong>Patient</strong> · ${timeOf(t.ts)} · ${dirArrow} ${tierBadge(t.risk.tier)} ${t.asr?.langConfidence ? `<span class="chip info">${esc(src.name)} ${Math.round(t.asr.langConfidence * 100)}%</span>` : ''}</div>
    <div class="translation" style="margin-top:0">${esc(t.translation)}</div>
    ${t.bodyRegions ? `<div style="margin-top:8px">${bodySvg(t.bodyRegions.some((r) => BACK_REGIONS.has(r)) ? 'back' : 'front', t.bodyRegions, { interactive: false, height: 170 })}</div>` : `<div class="secondary" dir="${src.dir}" lang="${esc(t.srcLang)}">${esc(t.original)}</div>`}
    <div class="row">${speakBtn}${meaningChip(t.meaning)}${checkChips(t)}${statusChip}</div>
    <details><summary>Back-translation and details</summary><p dir="${src.dir}">“${esc(t.backTranslation)}”</p><div class="row">${engine}${t.latencyMs ? `<span class="chip">${t.latencyMs.total} ms</span>` : ''}</div></details>
  </div>`;
}

function openInterpreterSheet(sid, patientLang, reason) {
  api(`/api/sessions/${sid}/events`, { body: { kind: 'escalation', detail: `Interpreter requested${reason ? ' — ' + reason : ''}` } }).catch(() => {});
  if (patientLang) api(`/api/sessions/${sid}/turns`, { body: { speaker: 'clinician', phraseId: 'interpreter_coming', srcLang: 'en', tgtLang: patientLang } }).catch(() => {});
  openSheet(`<div class="sheet-head"><h3>Human interpreter</h3><button class="navlink" data-close>Close</button></div>
    <div class="card" style="text-align:center">
      <div class="app-icon" style="background:linear-gradient(145deg,#ff6b5f,#d70015);box-shadow:0 14px 34px rgba(215,0,21,.35)">${icon('phone')}</div>
      <h3 id="escTitle" style="margin:0 0 6px">Connecting to the interpreting service…</h3>
      <p class="muted" id="escSub">Demo only: no real call is made.</p>
      <div id="escSpin"><span class="spinner"></span></div>
    </div>
    <p class="fineprint">In the hospital this would page the on-call ${esc(patientLang ? L(patientLang).name : '')} interpreter or open the telephone interpreting line. They receive a live brief (key facts, flagged sentences and the conversation so far) so they start with context. The patient has been told in their own language that an interpreter is coming.</p>`, (bd) => {
    setTimeout(() => {
      const t = $('#escTitle', bd); if (!t) return;
      t.textContent = 'Interpreter requested';
      $('#escSub', bd).textContent = `${patientLang ? L(patientLang).name + ' interpreter · ' : ''}estimated 10–15 minutes (demo)`;
      $('#escSpin', bd).innerHTML = `<span class="pill green">${icon('check')} Logged in the audit trail</span><div class="mt"><button class="btn primary" id="openBrief">${icon('doc')} Open the interpreter's brief</button></div>`;
      on('#openBrief', 'click', () => go('#/brief/' + sid), bd);
    }, 2200);
  });
}

function openCodeSheet(s) {
  openSheet(`<div class="sheet-head"><h3>Add a device</h3><button class="navlink" data-close>Done</button></div>
    <div class="card" style="text-align:center"><p class="muted" style="margin-top:0">On the bedside iPad or another device, sign in, tap <strong>Join a session</strong> and enter:</p>
    <div class="kbd">${esc(s.code)}</div><p class="muted">Choose <strong>Patient screen</strong> for the patient, or <strong>Live audit</strong> for a supervisor.</p></div>`);
}

function openLangSheet(current, onPick, title = 'Patient language', only = null) {
  openSheet(`<div class="sheet-head"><h3>${esc(title)}</h3><button class="navlink" data-close>Cancel</button></div>
    <p class="muted">${only ? 'Emergency mode lists the languages that have speech recognition and a voice.' : 'The pair will be locked for this session. Changing it is recorded in the audit log.'}</p>${langTiles(current, false, only)}`, (bd, close) => {
    bindLangTiles(bd, (code) => { if (code) { close(); onPick(code); } });
  });
}

// ---------------------------------------------------------------------------------------------
// Standard Consultation
// ---------------------------------------------------------------------------------------------
async function viewStandard(sid) {
  const C = { sid, speaker: 'clinician', state: 'idle', text: '', analysis: null, tr: null, confirmed: false, rec: null, session: null };
  render(`${navbar({ left: `<a class="navlink" href="#/home">${icon('chevL')} Home</a>`, title: 'Standard Consultation', right: `<button class="navlink danger" id="endBtn">End</button>` })}
  <main class="page">
    <div class="hstack wrap mt" id="pills"></div>
    <div class="consult">
      <div class="composer-col"><section class="card composer" id="composer" aria-label="Speak or type"></section></div>
      <div class="conv-col"><div id="banners"></div><div class="keyfacts" id="keyfacts"></div><div class="timeline" id="timeline"></div></div>
    </div>
  </main>`);

  const patientLang = () => C.session?.patientLang || C.tr?.lang || null;
  const sync = new Sync(sid, (session, fresh) => {
    C.session = session;
    renderPills(); renderBanners();
    if (fresh.length) renderTimeline();
  });
  S.cleanup.push(() => sync.stop(), () => C.rec?.close());
  await sync.start();
  if (sync.session?.mode === 'emergency') api(`/api/sessions/${sid}/events`, { body: { kind: 'session', detail: 'Switched to Standard Consultation' } }).catch(() => {});
  renderComposer(); renderTimeline();

  on('#endBtn', 'click', () => openSheet(`<div class="sheet-head"><h3>End consultation?</h3><button class="navlink" data-close>Cancel</button></div>
    <p class="muted">The bilingual transcript is saved to the audit log and exported as a FHIR document for the patient record. No audio is stored.</p>
    <button class="btn danger block xl" id="endGo">End and save</button>`, (bd, close) => on('#endGo', 'click', async () => {
      try { await api(`/api/sessions/${sid}/end`, { body: {} }); close(); go('#/observer/' + sid); } catch (e) { toast(e.message); }
    }, bd)));

  function renderPills() {
    const s = C.session; if (!s) return;
    const pl = s.patientLang;
    $('#pills').innerHTML = `
      <button class="pill blue clickable" id="langPill">${icon(s.langLocked ? 'lock' : 'unlock')} English ⇄ ${pl ? esc(L(pl).native) : 'Detect automatically'}${s.langLocked ? '' : ' · unlocked'}</button>
      <button class="pill clickable" id="codePill">${icon('tablet')} Code ${esc(s.code)}</button>
      ${s.mrn ? `<span class="pill">${icon('doc')} ${esc(s.mrn)}</span>` : ''}
      ${s.consent === 'accepted' ? `<span class="pill green">${icon('check')} Patient consented</span>` : ''}
      ${s.activity && s.activity.who === 'patient' && s.activity.state !== 'idle' && Date.now() - s.activity.at < 15000 ? `<span class="pill orange"><span class="dot"></span>Patient is speaking…</span>` : ''}`;
    on('#codePill', 'click', () => openCodeSheet(s));
    on('#langPill', 'click', () => openLangSheet(pl, async (code) => {
      if (pl && code !== pl && !confirm(`Change the patient's language to ${L(code).name}? This is recorded in the audit log.`)) return;
      C.session = await api(`/api/sessions/${sid}`, { method: 'PATCH', body: { patientLang: code, langLocked: true } });
      store.set('lastLang', code); renderPills(); sync.poll();
    }));
  }

  function renderBanners() {
    const s = C.session; if (!s) return;
    const esc_ = sync.turns.filter((t) => t.type === 'event' && t.kind === 'escalation');
    $('#banners').innerHTML = esc_.length ? `<div class="banner red">${icon('hand')}<div class="b-body"><div class="b-title">Interpreter requested · ${timeOf(esc_[esc_.length - 1].ts)}</div>${esc(esc_[esc_.length - 1].detail)}. Keep to routine questions until they arrive.</div></div>` : '';
  }

  function renderTimeline() {
    const items = [...sync.turns].sort((a, b) => b.ts - a.ts);
    $('#keyfacts').innerHTML = keyFacts(sync.turns);
    $('#timeline').innerHTML = items.filter((t) => t.type === 'utterance').length
      ? items.map((t) => bubble(t)).join('')
      : `<div class="empty">${icon('waveform')}<p><strong>No conversation yet.</strong><br>Tap the microphone, or use a pre-checked phrase.</p></div>`;
    on('[data-speak]', 'click', (e) => {
      const t = sync.turns.find((x) => x.id === e.currentTarget.dataset.speak);
      if (t) speak(t.translation, t.tgtLang);
    });
  }

  // ----- Composer state machine: idle → recording → transcribing → review → translating -----
  function renderComposer() {
    const el = $('#composer'); if (!el) return;
    const pl = patientLang();
    const seg = `<div class="segmented who" role="group" aria-label="Who is speaking">
      <button data-who="clinician" aria-pressed="${C.speaker === 'clinician'}">${icon('stethoscope')} Clinician</button>
      <button data-who="patient" aria-pressed="${C.speaker === 'patient'}">${icon('users')} Patient</button></div>`;

    if (C.state === 'idle') {
      const noSpeech = C.speaker === 'patient' && pl && C.session?.langLocked && !L(pl).whisper;
      const hint = noSpeech ? `Speech recognition isn't available for ${esc(L(pl).name)} yet. Type the patient's words or use the tap answers.`
        : C.speaker === 'clinician' ? 'Tap and speak in English' : `Tap and let the patient speak${pl ? ' (' + esc(L(pl).native) + ')' : ''}`;
      const extra = C.speaker === 'clinician'
        ? `<div class="section-title" style="margin:18px 0 0">Pre-checked phrases</div><div class="phrase-chips">${S.cfg.clinicianPhrases.map((id) => `<button data-phrase="${id}">${esc(S.cfg.phrases[id].en)}</button>`).join('')}</div>`
        : `<div class="section-title" style="margin:18px 0 0">Patient taps an answer</div><div class="phrase-chips">${S.cfg.quickReplies.map((id) => `<button data-reply="${id}">${esc(S.cfg.phrases[id].en)}${pl && S.cfg.phrases[id][pl] ? `<br><small class="muted" dir="${L(pl).dir}">${esc(S.cfg.phrases[id][pl])}</small>` : ''}</button>`).join('')}</div>
           <button class="btn tinted small mt" id="bodyMapBtn">${icon('users')} Body map</button>
           ${!pl || pl === 'uk' ? `<button class="btn tinted small mt" id="demoClip">${icon('waveform')} Play a demo patient voice</button>` : ''}`;
      el.innerHTML = `${seg}<div class="mic-area">${noSpeech ? `<div class="mic busy">${icon('keyboard')}</div>` : `<button class="mic" id="micBtn" aria-label="Start recording">${icon('mic')}</button>`}
        <div class="mic-hint">${hint}</div><button class="btn plain small" id="typeBtn">${icon('keyboard')} Type instead</button></div>${extra}`;
      on('#micBtn', 'click', startRecording, el);
      on('#typeBtn', 'click', () => { C.text = ''; C.tr = null; C.state = 'review'; C.analysis = null; C.confirmed = false; renderComposer(); analyzeSoon(); setTimeout(() => $('#rvText')?.focus(), 50); }, el);
      on('[data-phrase]', 'click', (e) => { C.text = S.cfg.phrases[e.currentTarget.dataset.phrase].en; C.tr = null; C.state = 'review'; C.confirmed = false; renderComposer(); analyzeNow(); }, el);
      on('[data-reply]', 'click', (e) => sendPatientReply(e.currentTarget.dataset.reply), el);
      on('#demoClip', 'click', openDemoClips, el);
      on('#bodyMapBtn', 'click', () => openSheet(`<div class="sheet-head"><h3>Where does it hurt?</h3><button class="navlink" data-close>Close</button></div>
        <p class="muted">Hand the device to the patient. They tap where it hurts; tap the arrow to turn the body around.</p><div id="bm"></div>`, (bd, close) => {
        bodyPicker($('#bm', bd), async (regions) => {
          const pl2 = C.session?.patientLang;
          if (!pl2) return toast('Choose the patient\'s language first');
          try { const t = await api(`/api/sessions/${sid}/turns`, { body: { speaker: 'patient', bodyRegions: regions, srcLang: pl2, tgtLang: 'en', mode: 'standard' } }); sync.add(t); close(); renderTimeline(); }
          catch (e) { toast(e.message); }
        });
      }), el);
    } else if (C.state === 'recording') {
      el.innerHTML = `${seg}<div class="mic-area"><button class="mic recording" id="micBtn" aria-label="Stop recording">${fillIcon('stop')}</button>
        <div class="levels" id="levels">${'<i></i>'.repeat(14)}</div><div class="mic-hint" id="recHint">Listening… tap to stop</div></div>`;
      on('#micBtn', 'click', stopRecording, el);
    } else if (C.state === 'transcribing' || C.state === 'translating') {
      el.innerHTML = `${seg}<div class="mic-area"><div class="mic busy"><span class="spinner"></span></div><div class="mic-hint">${C.state === 'transcribing' ? 'Transcribing on our secure server…' : 'Translating and running safety checks…'}</div></div>`;
    } else if (C.state === 'review') {
      el.innerHTML = C.speaker === 'clinician' ? reviewClinicianHtml() : reviewPatientHtml();
      bindReview(el);
    }
    on('[data-who]', 'click', (e) => { if (C.state === 'recording') return; C.speaker = e.currentTarget.dataset.who; C.state = 'idle'; renderComposer(); }, el);
  }

  async function startRecording() {
    AudioKit.unlock(); stopSpeaking();
    try {
      C.rec = new Recorder(); await C.rec.open(); C.rec.start();
    } catch (e) { toast(e.message || 'Microphone not available'); return; }
    C.state = 'recording'; renderComposer();
    setActivity(sid, C.speaker, 'speaking');
    const bars = () => $$('#levels i');
    const tick = setInterval(() => {
      if (C.state !== 'recording') return clearInterval(tick);
      const lvl = Math.min(1, C.rec.level() * 9);
      bars().forEach((b, i) => { b.style.height = `${6 + Math.max(0, lvl * 30 * (0.5 + 0.5 * Math.sin(Date.now() / 120 + i)))}px`; });
      const secs = Math.round((Date.now() - C.rec.t0) / 1000);
      const h = $('#recHint'); if (h) h.textContent = `Listening… ${secs}s · tap to stop`;
      if (secs >= 45) stopRecording();
    }, 80);
  }

  async function stopRecording() {
    if (C.state !== 'recording') return;
    const blob = await C.rec.stop(); C.rec.close();
    setActivity(sid, C.speaker, 'idle');
    await handleAudio(blob);
  }

  async function handleAudio(blob) {
    C.state = 'transcribing'; renderComposer();
    try {
      const pl = C.session?.patientLang;
      const tr = C.speaker === 'clinician' ? await transcribe(blob, 'en')
        : await transcribe(blob, C.session?.langLocked ? pl : null, C.session?.langLocked ? null : S.cfg.patientLangs);
      if (!tr.text) { toast('Nothing was heard. Please try again.'); C.state = 'idle'; return renderComposer(); }
      C.tr = tr; C.text = tr.text; C.confirmed = false; C.analysis = null; C.state = 'review';
      renderComposer();
      if (C.speaker === 'clinician') analyzeNow();
    } catch (e) { toast(e.message); C.state = 'idle'; renderComposer(); }
  }

  let analyzeTimer;
  function analyzeSoon() { clearTimeout(analyzeTimer); analyzeTimer = setTimeout(analyzeNow, 450); }
  async function analyzeNow() {
    const text = C.text.trim();
    if (!text) { C.analysis = null; return renderAnalysis(); }
    try { const a = await api('/api/analyze', { body: { text } }); if (text === C.text.trim()) { C.analysis = a; renderAnalysis(); } } catch (e) { toast(e.message); }
  }

  function highlight(text, flags) {
    let out = '', i = 0;
    for (const f of flags) { out += esc(text.slice(i, f.start)) + `<mark class="f ${f.severity}" title="${esc(f.reason)}">${esc(text.slice(f.start, f.end))}</mark>`; i = f.end; }
    return out + esc(text.slice(i));
  }

  function reviewClinicianHtml() {
    return `<div class="review">
      <div class="block"><h4>What you said · English</h4>
        <textarea class="input" id="rvText" rows="3" placeholder="Type what you want to say…">${esc(C.text)}</textarea>
        <div class="hstack mt">${C.tr ? `<button class="btn gray small" id="rerec">${icon('refresh')} Re-record</button>` : ''}<button class="btn gray small" id="discard">${icon('trash')} Discard</button><span class="grow"></span>${C.tr ? `<span class="muted" style="font-size:.8rem">Heard in ${(C.tr.ms / 1000).toFixed(1)}s</span>` : ''}</div>${asrNotes(C.tr)}</div>
      <div id="analysis"><div class="muted"><span class="spinner"></span> Checking for medical details…</div></div>
    </div>`;
  }

  function renderAnalysis() {
    const box = $('#analysis'); if (!box) return;
    const a = C.analysis;
    if (!a) { box.innerHTML = ''; return; }
    const critical = a.flags.filter((f) => f.severity === 'critical');
    const red = a.risk.tier === 'red';
    const rewrite = a.rewrites.length ? `<div class="block"><h4>Plain English we will translate</h4><div class="rewrite"><div class="to">${esc(a.plain)}</div>
      <small>${a.rewrites.map((r) => `“${esc(r.from)}” → “${esc(r.to)}” · ${esc(r.label)}`).join('<br>')}</small></div></div>` : '';
    const phrase = a.phrase ? `<div class="banner blue">${icon('shield')}<div class="b-body"><div class="b-title">Pre-checked translation</div>This sentence has a translation prepared for interpreter review, so it skips machine translation.</div></div>` : '';
    const flags = a.flags.length ? `<div class="block"><h4>Medical information (${a.flags.length})</h4><div class="hl-preview">${highlight(a.plain, a.flags)}</div>
      <div class="flag-list mt">${a.flags.filter((f) => f.severity !== 'info').slice(0, 8).map((f) => `<div class="flag-row"><span class="ft">${esc(f.text)}</span><span class="fr">${esc(f.reason)}</span><span class="chip ${f.severity === 'critical' ? 'bad' : 'warn'}">${f.severity === 'critical' ? 'Critical' : 'Review'}</span></div>`).join('')}</div></div>`
      : `<div class="block"><h4>Medical information</h4><div class="muted">No medical details detected.</div></div>`;
    const risk = red
      ? `<div class="banner red">${icon('hand')}<div class="b-body"><div class="b-title">${esc(a.risk.message)}</div>Topics like ${esc(a.risk.reasons.join(', ').toLowerCase())} should not rely on machine translation.</div></div>
         <div class="btn-row"><button class="btn danger xl" id="reqInterp">${icon('phone')} Request interpreter</button></div>
         <button class="btn plain block mt" id="override">Proceed anyway and record a reason…</button>`
      : `<div class="banner ${a.risk.tier === 'amber' ? 'amber' : 'blue'}">${icon(a.risk.tier === 'amber' ? 'warn' : 'checkCircle')}<div class="b-body"><div class="b-title">${a.risk.tier === 'amber' ? 'Clinical details' : 'Routine'}</div>${esc(a.risk.message)}</div></div>
         ${critical.length ? `<label class="confirm-row"><input type="checkbox" id="cf" ${C.confirmed ? 'checked' : ''}> I have checked the ${critical.length} highlighted critical detail${critical.length > 1 ? 's' : ''}</label>` : ''}
         <button class="btn primary block xl" id="goTr" ${critical.length && !C.confirmed ? 'disabled' : ''}>Confirm &amp; translate${patientLang() ? ' to ' + esc(L(patientLang()).native) : ''}</button>`;
    box.innerHTML = rewrite + phrase + flags + risk;
    on('#cf', 'change', (e) => { C.confirmed = e.target.checked; const b = $('#goTr'); if (b) b.disabled = !C.confirmed; }, box);
    on('#goTr', 'click', () => sendClinician(null), box);
    on('#reqInterp', 'click', () => { openInterpreterSheet(sid, patientLang(), a.risk.reasons.join(', ')); C.state = 'idle'; renderComposer(); }, box);
    on('#override', 'click', () => openOverrideSheet((reason) => sendClinician(reason)), box);
  }

  function bindReview(el) {
    const ta = $('#rvText', el);
    ta?.addEventListener('input', () => {
      C.text = ta.value; C.confirmed = false;   // any edit clears an earlier confirmation (STD-08)
      if (C.speaker === 'clinician') { $('#analysis').innerHTML = '<div class="muted"><span class="spinner"></span> Re-checking…</div>'; analyzeSoon(); }
    });
    on('#rerec', 'click', () => { C.state = 'idle'; renderComposer(); startRecording(); }, el);
    on('#discard', 'click', () => { C.state = 'idle'; C.text = ''; renderComposer(); }, el);
    on('#lockLang', 'click', async () => {
      C.session = await api(`/api/sessions/${sid}`, { method: 'PATCH', body: { patientLang: C.tr.lang, langLocked: true } });
      store.set('lastLang', C.tr.lang); renderPills(); renderComposer();
    }, el);
    on('#changeLang', 'click', () => openLangSheet(C.tr?.lang, async (code) => {
      C.session = await api(`/api/sessions/${sid}`, { method: 'PATCH', body: { patientLang: code, langLocked: true } });
      C.tr = { ...(C.tr || {}), lang: code }; renderPills(); renderComposer();
    }), el);
    on('#goPt', 'click', sendPatient, el);
    on('[data-guess]', 'click', async (e) => {
      const code = e.currentTarget.dataset.guess;
      C.session = await api(`/api/sessions/${sid}`, { method: 'PATCH', body: { patientLang: code, langLocked: true } });
      toast(`Locked to ${L(code).name}. Re-record so it is transcribed in ${L(code).name}.`);
      C.tr = { ...(C.tr || {}), lang: code, uncertain: false }; renderPills(); renderComposer();
    }, el);
    if (C.speaker === 'clinician') renderAnalysis();
  }

  function reviewPatientHtml() {
    const lang = C.tr?.lang || C.session?.patientLang || 'uk';
    const locked = C.session?.langLocked;
    const conf = C.tr?.langConfidence;
    return `<div class="review">
      <div class="block"><h4>Patient said · ${esc(L(lang).native)} ${conf ? `<span class="chip info">${Math.round(conf * 100)}% sure</span>` : ''}</h4>
        <textarea class="input" id="rvText" rows="3" dir="${L(lang).dir}" lang="${esc(lang)}">${esc(C.text)}</textarea>
        <div class="hstack mt"><button class="btn gray small" id="rerec">${icon('refresh')} Re-record</button><button class="btn gray small" id="discard">${icon('trash')} Discard</button></div>${asrNotes(C.tr)}</div>
      ${!locked && C.tr?.uncertain ? `<div class="banner amber">${icon('warn')}<div class="b-body"><div class="b-title">Not sure which language this is</div>Tap the right one:</div></div>
        <div class="btn-row mb">${Object.entries(C.tr.langScores || {}).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([c, p]) => `<button class="btn tinted" data-guess="${c}">${esc(L(c).native)} · ${Math.round(p * 100)}%</button>`).join('')}</div>` : ''}
      ${!locked ? `<div class="banner blue">${icon('globe')}<div class="b-body"><div class="b-title">Detected ${esc(L(lang).name)}${conf ? ' · ' + Math.round(conf * 100) + '%' : ''} (not confirmed)</div>Confirm and lock this language so later speech can't switch it.</div></div>
        <div class="btn-row mb"><button class="btn tinted" id="lockLang">${icon('lock')} Confirm &amp; lock</button><button class="btn gray" id="changeLang">Change</button></div>` : ''}
      <button class="btn primary block xl" id="goPt">Translate to English</button>
    </div>`;
  }

  async function sendClinician(override) {
    const pl = patientLang();
    if (!pl) { toast('Choose the patient\'s language first'); return openLangSheet(null, async (code) => { C.session = await api(`/api/sessions/${sid}`, { method: 'PATCH', body: { patientLang: code, langLocked: true } }); renderPills(); renderComposer(); }); }
    C.state = 'translating'; renderComposer();
    try {
      const t = await api(`/api/sessions/${sid}/turns`, { body: { speaker: 'clinician', text: C.text, srcLang: 'en', tgtLang: pl, mode: 'standard', confirmed: C.confirmed, override, asr: C.tr ? { duration: C.tr.duration, asrConfidence: C.tr.asrConfidence } : null } });
      sync.add(t); C.state = 'idle'; C.text = ''; renderComposer(); renderTimeline();
      if (t.status === 'fail') toast('Some details may have changed in translation. Confirm them verbally.', 4200);
    } catch (e) { toast(e.message); C.state = 'review'; renderComposer(); }
  }

  async function sendPatient() {
    const lang = C.tr?.lang || C.session?.patientLang;
    if (!lang) return toast('Choose the patient\'s language first');
    if (!C.session?.patientLang) C.session = await api(`/api/sessions/${sid}`, { method: 'PATCH', body: { patientLang: lang, langLocked: false } });
    C.state = 'translating'; renderComposer();
    try {
      const t = await api(`/api/sessions/${sid}/turns`, { body: { speaker: 'patient', text: C.text, srcLang: lang, tgtLang: 'en', mode: 'standard', asr: C.tr ? { langConfidence: C.tr.langConfidence, duration: C.tr.duration } : null } });
      sync.add(t); C.state = 'idle'; C.text = ''; renderComposer(); renderTimeline(); renderPills();
    } catch (e) { toast(e.message); C.state = 'review'; renderComposer(); }
  }

  async function sendPatientReply(id) {
    const pl = C.session?.patientLang;
    if (!pl) return toast('Choose the patient\'s language first');
    try { const t = await api(`/api/sessions/${sid}/turns`, { body: { speaker: 'patient', phraseId: id, srcLang: pl, tgtLang: 'en', mode: 'standard' } }); sync.add(t); renderTimeline(); }
    catch (e) { toast(e.message); }
  }

  function openDemoClips() {
    openSheet(`<div class="sheet-head"><h3>Demo patient voice</h3><button class="navlink" data-close>Close</button></div>
      <p class="muted">Nobody on our team speaks Ukrainian, so these lines were recorded with a native Ukrainian synthetic voice. The app hears them exactly as it would hear a patient.</p>
      <div class="list">${S.cfg.demoClips.map((c) => `<button class="list-row" data-clip="${c.id}"><span class="row-icon" style="background:#30b0c7">${fillIcon('play')}</span><span class="row-text"><span class="row-title" lang="uk">${esc(c.text)}</span><br><span class="row-sub">${esc(c.en)}</span></span></button>`).join('')}</div>`, (bd, close) => {
      on('[data-clip]', 'click', async (e) => {
        close();
        const blob = await (await fetch(`audio/${e.currentTarget.dataset.clip}.wav`)).blob();
        C.speaker = 'patient';
        playBlob(blob);
        await handleAudio(blob);
      }, bd);
    });
  }
}

function openOverrideSheet(onDone) {
  openSheet(`<div class="sheet-head"><h3>Proceed without an interpreter?</h3><button class="navlink" data-close>Cancel</button></div>
    <p class="muted">This is recorded in the audit log with your name.</p>
    <div class="list">${['Clinical emergency, no interpreter available in time', 'Patient declined a human interpreter', 'Interpreter is present and checking the translation'].map((r, i) => `<label class="list-row"><input type="radio" name="r" value="${esc(r)}" ${i === 0 ? 'checked' : ''} style="width:22px;height:22px;accent-color:var(--red-bright)"><span class="row-text">${esc(r)}</span></label>`).join('')}</div>
    <button class="btn danger block xl mt" id="ovGo">Proceed and record</button>`, (bd, close) => on('#ovGo', 'click', () => { const v = $('input[name=r]:checked', bd)?.value; close(); onDone(v); }, bd));
}

// ---------------------------------------------------------------------------------------------
// Emergency
// ---------------------------------------------------------------------------------------------
// Emergency speaks every translation aloud, so it only offers languages with speech recognition and a server voice
const emergencyLangs = () => S.cfg.patientLangs.filter((c) => L(c).whisper && (S.cfg.voiceLangs || []).includes(c));

async function viewEmergency(sid) {
  document.body.classList.add('emergency-mode');
  // Two ways to record. "Tap to talk" (default): tap, speak, tap again; once the patient's language is known there
  // is one button per speaker, so background voices in a loud room can't change the language. "Hands-free":
  // listens on its own, for quiet rooms. The choice is remembered on this device.
  const E = { sid, paused: false, last: null, state: 'starting', session: null, mode: store.get('emMode', 'tap') === 'auto' ? 'auto' : 'tap', rec: null };
  render(`<div class="em">
    <div class="em-top">
      <span class="em-badge">${icon('bolt')} EMERGENCY</span>
      <button class="em-lang" id="emLang"></button>
      <div class="em-mode" role="group" aria-label="How to record">
        <button data-mode="tap">${icon('mic')} Tap to talk</button><button data-mode="auto">${icon('waveform')} Hands-free</button>
      </div>
      <button class="em-stop" id="emStop">${fillIcon('pause')} Pause</button>
    </div>
    <div class="em-main">
      <div class="em-state"><span class="orb" id="orb"></span><span id="emState">Starting…</span></div>
      <div id="emQuickLang"></div>
      <div class="em-label" id="emOrigLabel"></div>
      <div class="em-original" id="emOrig" dir="auto"></div>
      <div class="em-label" id="emTrLabel"></div>
      <div class="em-translation" id="emTr" dir="auto"></div>
      <div class="em-alerts" id="emAlerts"></div>
    </div>
    <div class="em-talk" id="emTalk"></div>
    <div class="em-bottom">
      <button class="btn em-gray" id="emReplay">${icon('replay')} Replay last</button>
      <button class="btn em-red" id="emInterp">${icon('phone')} Human interpreter</button>
      <button class="btn em-gray" id="emStd">${icon('stethoscope')} Standard mode</button>
    </div>
  </div>`);

  const lang = () => E.session?.patientLang || null;
  const locked = () => !!(E.session?.langLocked && lang());
  const sync = new Sync(sid, (s) => { E.session = s; renderLang(); renderTalk(); });
  await sync.start(); E.session = sync.session;

  function renderLang() {
    const l = lang();
    const key = `${l}|${locked()}`;
    if (E.langKey === key) return;   // redraw only on change, so a tap on a language is never lost
    E.langKey = key;
    $('#emLang').className = 'em-lang' + (l && !locked() ? ' provisional' : '');
    $('#emLang').innerHTML = `${icon(locked() ? 'lock' : 'globe')} ${l ? `English ⇄ ${esc(L(l).native)} · ${locked() ? 'locked for this session' : 'auto, tap to lock'}` : 'Listening for the patient\'s language'}`;
    $('#emQuickLang').innerHTML = l ? '' : `<div class="em-label">Patient speaks</div><div class="pills mb">${(S.cfg.commonLangs || []).filter((c) => emergencyLangs().includes(c)).map((c) => `<button class="em-lang" data-ql="${c}" dir="${L(c).dir}">${esc(L(c).native)}</button>`).join('')}<button class="em-lang" id="emMore">${icon('globe')} More…</button></div>`;
    on('[data-ql]', 'click', (e) => setLang(e.currentTarget.dataset.ql, true));
    on('#emMore', 'click', () => openLangSheet(null, (code) => setLang(code, true), 'Patient language', emergencyLangs()));
  }
  async function setLang(code, lock) {
    E.session = await api(`/api/sessions/${sid}`, { method: 'PATCH', body: { patientLang: code, langLocked: lock } });
    renderLang(); renderTalk();
  }
  function setState(state, text) {
    E.state = state;
    $('#orb').className = 'orb ' + ({ listening: '', hearing: 'hearing', busy: 'busy', speaking: 'speaking', paused: 'paused', ready: 'paused' }[state] || '');
    $('#emState').textContent = text;
    renderTalk();
  }
  const readyText = () => (E.mode === 'tap'
    ? (locked() ? 'Tap the button for whoever is speaking' : 'Tap to talk. The language is detected automatically')
    : 'Listening…');
  function idle() {
    if (E.mode === 'tap') setState('ready', readyText());
    else if (E.paused) setState('paused', 'Paused');
  }
  function renderMode() {
    $$('.em-mode button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.mode === E.mode)));
    $('#emStop').hidden = E.mode !== 'auto';
  }
  // Tap to talk: one button before the patient's language is known, then one button per speaker
  function renderTalk() {
    const box = $('#emTalk'); if (!box) return;
    if (E.mode !== 'tap') { box.innerHTML = ''; box.dataset.html = ''; return; }
    const busy = E.state === 'busy' || E.state === 'speaking';
    const btn = (who, label, sub) => {
      const active = E.rec?.who === who;
      return `<button class="em-talk-btn ${active ? 'rec' : ''} who-${who}" data-who="${who}" ${busy || (E.rec && !active) ? 'disabled' : ''}
        aria-label="${active ? 'Stop recording' : 'Start recording: ' + esc(label)}">
        <span class="em-talk-ic">${icon(active ? 'stop' : 'mic')}</span>
        <span class="em-talk-t">${active ? 'Tap to stop' : esc(label)}</span>
        <span class="em-talk-s">${active ? '<span class="em-meter"><i id="emMeter"></i></span> <span id="emRecTime">0:00</span>' : esc(sub)}</span>
      </button>`;
    };
    const html = locked()
      ? btn('clinician', 'Clinician', 'English') + btn('patient', 'Patient', L(lang()).native)
      : btn('any', 'Tap to talk', 'Language detected automatically');
    // Only redraw when something changed: replacing a button mid-tap would lose the tap
    if (box.dataset.html === html) return;
    box.dataset.html = html; box.innerHTML = html;
    $$('[data-who]', box).forEach((b) => b.addEventListener('click', () => toggleRecording(b.dataset.who)));
  }

  async function toggleRecording(who) {
    if (E.rec) { if (E.rec.who === who) await finishRecording(); return; }
    stopSpeaking();
    const rec = new Recorder({ closeVoice: true });
    try { await rec.open(); } catch (e) { addAlert('bad', e.message || 'Allow microphone access, then try again.'); return; }
    rec.start();
    E.rec = { who, rec, t0: Date.now() };
    setState('hearing', 'Recording… tap again when finished');
    E.rec.timer = setInterval(() => {
      if (!E.rec) return;
      const secs = Math.floor((Date.now() - E.rec.t0) / 1000);
      const m = $('#emMeter'); if (m) m.style.transform = `scaleX(${Math.min(1, rec.level() * 10).toFixed(2)})`;
      const t = $('#emRecTime'); if (t) t.textContent = `0:${String(secs).padStart(2, '0')}`;
      if (secs >= 20) finishRecording();   // one sentence at a time; longer recordings also translate slowly
    }, 100);
  }
  async function finishRecording() {
    const r = E.rec; if (!r) return;
    E.rec = null; clearInterval(r.timer);
    const blob = await r.rec.stop();
    r.rec.close();   // release the microphone so the phone plays the translation through its loudspeaker
    if (!blob || Date.now() - r.t0 < 600) { idle(); addAlert('amber', 'That was too short. Tap, speak, then tap again when you finish.', true); return; }
    await processUtterance(blob, r.who);
    idle();
  }
  function cancelRecording() {
    const r = E.rec; if (!r) return;
    E.rec = null; clearInterval(r.timer); r.rec.close();
  }

  // Hands-free: listens on its own and records whenever someone speaks
  const loop = new VoiceLoop({
    onState: (st) => { if (!E.paused && E.mode === 'auto') setState(st === 'hearing' ? 'hearing' : 'listening', st === 'hearing' ? 'Hearing speech…' : 'Listening…'); },
    onUtterance: async (blob) => {
      if (E.paused || E.mode !== 'auto') return;
      await processUtterance(blob, 'any');
      if (!E.paused && E.mode === 'auto') { try { await loop.resume(); } catch (e) { addAlert('bad', e.message); } }
    },
  });
  async function startHandsFree() {
    try {
      await loop.start();
      if (loop.noise > 0.02) addAlert('amber', 'This room is loud. Tap to talk will be more reliable here.', true, { label: 'Switch to Tap to talk', run: () => setMode('tap') });
    } catch (e) { setState('paused', 'Microphone unavailable'); addAlert('bad', e.message || 'Allow microphone access and reload.'); }
  }
  async function setMode(m) {
    if (m === E.mode) return;
    E.mode = m; store.set('emMode', m);
    renderMode();
    if (m === 'tap') { loop.pause(); E.paused = false; resetPause(); idle(); }
    else { cancelRecording(); E.paused = false; resetPause(); setState('listening', 'Listening…'); await startHandsFree(); }
  }
  S.cleanup.push(() => { loop.stop(); cancelRecording(); }, () => sync.stop());

  async function processUtterance(blob, who) {
    setState('busy', 'Translating…');
    try {
      const l = lang();
      let tr;
      if (who === 'clinician') tr = await transcribe(blob, 'en');
      else if (who === 'patient' && l) tr = await transcribe(blob, l);
      else tr = await transcribe(blob, null, locked() ? ['en', l] : ['en', ...emergencyLangs()]);
      await handle(tr, who);
    } catch (e) { addAlert('bad', e.message); }
  }

  async function handle(tr, who) {
    $('#emAlerts').innerHTML = '';
    // Nothing clear enough to translate: say so, and never translate background noise
    if (tr.noSpeech || !tr.text || tr.text.length < 2 || tr.clarity === 'unclear') {
      $('#emOrigLabel').textContent = tr.text ? 'Heard (too unclear to translate)' : '';
      $('#emOrig').textContent = tr.text || ''; $('#emTrLabel').textContent = ''; $('#emTr').textContent = '';
      addAlert('amber', 'Didn\'t catch that clearly. Hold the phone closer to whoever is speaking and try again.');
      return;
    }
    const fromClinician = who === 'clinician' || (who !== 'patient' && tr.lang === 'en');
    if (who === 'any' && !locked() && tr.uncertain) {
      $('#emOrig').textContent = tr.text;
      addAlert('amber', 'Not sure which language that was. Tap the patient\'s language above, then speak again.');
      const top = Object.entries(tr.langScores || {}).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([c]) => c);
      E.langKey = null;
      $('#emQuickLang').innerHTML = `<div class="em-label">Which language was it?</div><div class="pills mb">${top.concat((S.cfg.commonLangs || []).filter((c) => !top.includes(c))).slice(0, 6).map((c) => `<button class="em-lang" data-ql="${c}" dir="${L(c).dir}">${esc(L(c).native)}</button>`).join('')}<button class="em-lang" id="emMore">${icon('globe')} More…</button></div>`;
      on('[data-ql]', 'click', (e) => setLang(e.currentTarget.dataset.ql, true));
      on('#emMore', 'click', () => openLangSheet(null, (code) => setLang(code, true), 'Patient language', emergencyLangs()));
      return;
    }
    if (!fromClinician && !locked()) {
      // First foreign-language sentence: lock it for the whole session. From now on there is one button per
      // speaker (tap to talk), or the server only decides between English and this language (hands-free).
      await setLang(tr.lang, true);
      toast(`Locked to ${L(tr.lang).name} for this session`);
      // Shown to the patient in their own language: one tap confirms, "change" fixes a wrong guess (the one case
      // the language check cannot catch is a bystander speaking another language)
      E.langKey = null;
      $('#emQuickLang').innerHTML = `<div class="em-label">${esc(S.cfg.patientUi?.[tr.lang]?.choose || 'Language')}</div><div class="pills mb"><button class="em-lang" id="emLangOk" dir="${L(tr.lang).dir}">${icon('check')} ${esc(L(tr.lang).native)}</button><button class="em-lang" id="emLangChange">${icon('globe')} …</button></div>`;
      on('#emLangOk', 'click', () => { $('#emQuickLang').innerHTML = ''; api(`/api/sessions/${sid}/events`, { body: { kind: 'language', detail: `Patient confirmed ${L(tr.lang).name}` } }).catch(() => {}); });
      on('#emLangChange', 'click', () => openLangSheet(lang(), (code) => { $('#emQuickLang').innerHTML = ''; setLang(code, true); }, 'Patient language', emergencyLangs()));
    }
    const pl = lang();
    if (fromClinician && !pl) { addAlert('amber', 'Patient language unknown: tap their language above, or let them speak first.'); $('#emOrig').textContent = tr.text; return; }
    const t = await api(`/api/sessions/${sid}/turns`, { body: { speaker: fromClinician ? 'clinician' : 'patient', text: tr.text, srcLang: fromClinician ? 'en' : pl, tgtLang: fromClinician ? pl : 'en', mode: 'emergency', asr: { langConfidence: tr.langConfidence, duration: tr.duration, clarity: tr.clarity } } });
    E.last = t; sync.add(t);
    $('#emOrigLabel').textContent = `${fromClinician ? 'Clinician' : 'Patient'} · ${L(t.srcLang).name}${tr.langConfidence && who === 'any' ? ` · ${Math.round(tr.langConfidence * 100)}% sure` : ''}`;
    $('#emOrig').textContent = t.original; $('#emOrig').dir = L(t.srcLang).dir;
    $('#emTrLabel').textContent = `Translation · ${L(t.tgtLang).name}`;
    $('#emTr').textContent = t.translation; $('#emTr').dir = L(t.tgtLang).dir;
    if (t.risk.tier === 'red') addAlert('bad', `${t.risk.message} Tap “Human interpreter”.`);
    t.checks.filter((c) => !c.ok).forEach((c) => addAlert('bad', `${c.name}: ${c.detail}. Confirm verbally.`));
    if (t.meaning.score < 70) addAlert('amber', `${t.meaning.verdict} (score ${t.meaning.score}).`);
    (t.glossary || []).filter((g) => !g.ok).forEach((g) => addAlert('amber', `Medical word “${g.term}” not confirmed in the translation.`));
    speechAlerts(tr);
    // Medication or dose instructions are not spoken in Emergency mode: Standard mode checks them on screen first
    if (t.hold) {
      addAlert('bad', `Not spoken: ${t.hold.message}`, false, [
        { label: 'Standard mode', icon: 'stethoscope', run: () => go('#/standard/' + sid) },
        { label: 'Speak anyway', run: async () => {
          if (!confirm('Speak this medication instruction without checking it in Standard mode?')) return;
          api(`/api/sessions/${sid}/events`, { body: { kind: 'override', detail: `Medication instruction spoken in Emergency mode: ${t.original}` } }).catch(() => {});
          await speakLast();
        } },
      ]);
      if (E.mode === 'tap') idle();
      return;
    }
    // A noisy recording is shown but not spoken until someone has checked the words above
    if (tr.clarity === 'noisy') {
      addAlert('amber', 'Noisy recording. Check the words above, then tap Speak, or record again.', false, { label: 'Speak it', run: () => speakLast() });
      return;
    }
    await speakLast();
  }
  // Every translation is spoken aloud: English when the patient spoke, the patient's language when the clinician
  // spoke. The microphone is released first so phones play through the loudspeaker.
  async function speakLast() {
    const t = E.last; if (!t) return;
    loop.pause();
    setState('speaking', `Speaking ${L(t.tgtLang).name}…`);
    await sleep(250);
    let played = await speak(t.translation, t.tgtLang, { force: true });
    if (!played) { await sleep(300); played = await speak(t.translation, t.tgtLang, { force: true }); }
    if (!played) addAlert('amber', `Could not play the ${L(t.tgtLang).name} audio on this device. Tap “Replay last” or show the screen.`);
    if (E.mode === 'tap') idle();
    else if (!E.paused && E.state === 'speaking') { try { await loop.resume(); } catch { /* mic busy */ } }
  }
  function addAlert(kind, text, clear = false, action = null) {
    if (clear) $('#emAlerts').innerHTML = '';
    const actions = Array.isArray(action) ? action : action ? [action] : [];
    const ids = actions.map(() => 'ea' + Math.random().toString(36).slice(2, 8));
    $('#emAlerts').insertAdjacentHTML('beforeend', `<div class="em-alert ${kind === 'amber' ? 'amber' : ''}">${icon('warn')} <span>${esc(text)}</span>${actions.map((a, i) => `<button class="em-alert-btn" id="${ids[i]}">${icon(a.icon || 'speaker')} ${esc(a.label)}</button>`).join('')}</div>`);
    actions.forEach((a, i) => on('#' + ids[i], 'click', (e) => { e.currentTarget.closest('.em-alert')?.remove(); a.run(); }));
  }
  // The safety layer's notes on a recording (corrected / sound-alike medicines, unclear numbers), as alerts
  function speechAlerts(tr) {
    (tr.ambiguous || []).forEach((a) => addAlert('bad', `“${a.heard}” sounds like ${a.options.join(' or ')}. Ask the patient to show the packet.`));
    (tr.corrections || []).forEach((c) => addAlert('amber', `Heard “${c.from}”, matched to ${c.to}. Confirm it.`));
    if ((tr.lowConfidenceWords || []).length) addAlert('amber', `Unclear: ${tr.lowConfidenceWords.join(', ')}. Confirm these words.`);
  }
  function resetPause() { const b = $('#emStop'); b.classList.remove('paused'); b.innerHTML = `${fillIcon('pause')} Pause`; }

  $$('.em-mode button').forEach((b) => b.addEventListener('click', () => setMode(b.dataset.mode)));
  on('#emStop', 'click', async () => {
    E.paused = !E.paused;
    const b = $('#emStop');
    if (E.paused) { loop.pause(); stopSpeaking(); setState('paused', 'Paused'); b.classList.add('paused'); b.innerHTML = `${fillIcon('play')} Resume`; }
    else { resetPause(); try { await loop.resume(); } catch (e) { addAlert('bad', e.message); } }
  });
  on('#emReplay', 'click', async () => {
    if (!E.last || E.rec) return;
    await speakLast();
  });
  on('#emInterp', 'click', () => openInterpreterSheet(sid, lang(), 'requested from Emergency mode'));
  on('#emStd', 'click', () => go('#/standard/' + sid));
  on('#emLang', 'click', () => {
    // Changing a locked language is a deliberate act with a confirmation (team UI spec LANG-05)
    if (locked() && !confirm(`The patient's language is locked to ${L(lang()).name}. Change it?`)) return;
    openLangSheet(lang(), (code) => setLang(code, true), 'Patient language', emergencyLangs());
  });

  renderLang(); renderMode();
  $('#emTr').textContent = E.mode === 'tap'
    ? 'Tap the microphone, speak, then tap again. CareBridge detects the language and translates both ways.'
    : 'Speak now. CareBridge listens, detects the language and translates both ways.';
  if (E.mode === 'tap') {
    idle();
    // Ask for microphone permission now, while the person is ready for it, then release the microphone
    try { const r = new Recorder({ closeVoice: true }); await r.open(); r.close(); } catch (e) { addAlert('bad', e.message || 'Allow microphone access, then try again.'); }
  } else {
    setState('listening', 'Starting microphone…');
    await startHandsFree();
  }
}

// ---------------------------------------------------------------------------------------------
// Patient bedside screen (everything in the patient's language)
// ---------------------------------------------------------------------------------------------
const PAIN_FACES = ['😀', '🙂', '🙂', '😐', '😐', '😕', '😕', '😣', '😣', '😫', '😭'];
const PAIN_COLORS = ['#34c759', '#4cc85a', '#7ccb4b', '#a8cc3c', '#d0c22f', '#f2b51f', '#ff9f0a', '#ff8410', '#ff6a1f', '#ff4f2d', '#ff3b30'];

async function viewPatient(sid) {
  const P = { sid, session: null, seen: new Set(), latest: null, mine: null, rec: null, recording: false, started: false };
  const sync = new Sync(sid, (s, fresh) => {
    P.session = s;
    const newClin = fresh.filter((t) => t.type === 'utterance' && t.speaker === 'clinician');
    if (newClin.length) { P.latest = newClin[newClin.length - 1]; if (P.started) speak(P.latest.translation, P.latest.tgtLang); }
    fresh.filter((t) => t.type === 'event' && t.kind === 'escalation').forEach((t) => { P.escalatedAt = Math.max(P.escalatedAt || 0, t.ts); });
    draw();
  });
  S.cleanup.push(() => sync.stop(), () => P.rec?.close());
  await sync.start();
  P.session = sync.session;
  P.latest = [...sync.turns].reverse().find((t) => t.type === 'utterance' && t.speaker === 'clinician') || null;
  sync.turns.filter((t) => t.type === 'event' && t.kind === 'escalation').forEach((t) => { P.escalatedAt = Math.max(P.escalatedAt || 0, t.ts); });
  P.started = false;
  draw();

  function draw() {
    const s = P.session; if (!s) return;
    const lang = s.patientLang;
    const ui = pui(lang);
    if (!P.started) {
      render(`<div class="tap-overlay"><div><div class="app-icon">${icon('bridge')}</div><h2 style="margin:0">CareBridge</h2>
        <p style="opacity:.85">Tap to start · Натисніть, щоб почати · Нажмите, чтобы начать · Dotknij, aby zacząć · Atingeți pentru a începe · اضغط للبدء</p>
        <button class="btn primary xl" id="startBtn">${fillIcon('play')} Start</button></div></div>`);
      on('#startBtn', 'click', () => { AudioKit.unlock(); P.started = true; draw(); if (P.session.patientLang && P.session.consent && P.latest) speak(P.latest.translation, P.latest.tgtLang); });
      return;
    }
    if (!lang) {
      render(`<div class="patient"><div class="patient-top"><span class="brand"><span class="app-icon">${icon('bridge')}</span>CareBridge</span></div>
        <div class="patient-main"><h1 class="large-title" style="text-align:center">Choose your language${['uk', 'ar', 'pl', 'ro', 'ru', 'ga', 'fr', 'es'].map((c) => `<span dir="${L(c).dir}" style="display:block;font-size:.55em;color:var(--label-2);font-weight:600">${esc(pui(c).choose)}</span>`).join('')}</h1>
        ${langTiles(null, false)}</div></div>`);
      bindLangTiles(appEl(), async (code) => {
        if (!code) return;
        P.session = await api(`/api/sessions/${sid}`, { method: 'PATCH', body: { patientLang: code, langLocked: true } });
        draw(); speak(pui(P.session.patientLang).consent, P.session.patientLang);
      });
      return;
    }
    const dir = L(lang).dir;
    if (!s.consent) {
      render(`<div class="patient" dir="${dir}" lang="${esc(lang)}"><div class="patient-top"><span class="brand"><span class="app-icon">${icon('bridge')}</span>${esc(ui.consent_title)}</span></div>
        <div class="patient-main"><div class="card consent-card">${icon('shield')}<p class="big">${esc(ui.consent)}</p><p class="big" style="margin-top:0">${esc(ui.consent_q)}</p>
        <div class="btn-row"><button class="btn success xl" data-c="accepted">${icon('check')} ${esc(ui.yes)}</button><button class="btn gray xl" data-c="declined">${icon('x')} ${esc(ui.no)}</button></div>
        <button class="btn tinted red block xl mt" data-c="interpreter">${icon('phone')} ${esc(ui.human)}</button>
        <button class="btn plain mt" id="replayConsent">${icon('speaker')} ${esc(L(lang).native)}</button></div></div></div>`);
      on('[data-c]', 'click', async (e) => {
        const c = e.currentTarget.dataset.c;
        P.session = await api(`/api/sessions/${sid}`, { method: 'PATCH', body: { consent: c } });
        if (c !== 'accepted') { P.escalatedAt = Date.now(); api(`/api/sessions/${sid}/events`, { body: { kind: 'escalation', detail: c === 'declined' ? 'Patient declined the AI translator' : 'Patient asked for a human interpreter' } }).catch(() => {}); }
        draw();
      });
      on('#replayConsent', 'click', () => speak(ui.consent + ' ' + ui.consent_q, lang));
      return;
    }
    const act = s.activity && s.activity.who === 'clinician' && s.activity.state === 'speaking' && Date.now() - s.activity.at < 15000;
    // An interpreter request shows until the clinician says something new
    const showEsc = P.escalatedAt && (!P.latest || P.latest.ts < P.escalatedAt);
    const msg = showEsc ? `<div class="msg">${esc(ui.interpreter_coming)}</div>`
      : P.latest ? `<div class="msg" lang="${esc(lang)}">${esc(P.latest.translation)}</div><div class="msg-en" dir="ltr">${esc(P.latest.plain)}</div>
          <div class="hstack mt"><button class="btn tinted" id="again">${icon('speaker')} ▶</button></div>`
        : `<div class="status">${icon('waveform')} …</div>`;
    render(`<div class="patient" dir="${dir}" lang="${esc(lang)}">
      <div class="patient-top"><span class="brand"><span class="app-icon">${icon('bridge')}</span>CareBridge</span><span class="grow"></span>
        <span class="pill">${icon('globe')} ${esc(L(lang).native)}</span>${lang === 'uk' ? `<button class="pill clickable" id="demoBtn" dir="ltr" title="Demo voice">${icon('waveform')} Demo</button>` : ''}</div>
      <div class="patient-main">
        <div class="message-card">${act ? `<div class="status"><span class="spinner"></span> ${esc(ui.waiting)}</div>` : msg}</div>
        ${L(lang).whisper ? `<div class="patient-actions"><button class="mic ${P.recording ? 'recording' : ''}" id="ptMic" aria-label="${esc(ui.speak)}">${P.recording ? fillIcon('stop') : icon('mic')}</button>
          <div style="font-size:1.25rem;font-weight:600">${esc(P.recording ? ui.listening : ui.speak)}${P.mine ? `<div class="muted" style="font-size:.95rem;font-weight:400">✓ ${esc(P.mine)}</div>` : ''}</div></div>` : (P.mine ? `<div class="muted">✓ ${esc(P.mine)}</div>` : '')}
        <form class="hstack" id="ptTypeForm"><input class="input" id="ptText" placeholder="${esc(ui.type || '…')}" dir="${dir}" autocomplete="off"><button class="btn primary" type="submit" aria-label="Send">${icon('chevR')}</button></form>
        <div><div class="section-title" style="margin:6px 4px 8px">${esc(ui.replies)}</div>
          <div class="reply-grid">${S.cfg.quickReplies.map((id) => `<button class="reply ${id === 'r_yes' ? 'yes' : id === 'r_no' ? 'no' : ''}" data-reply="${id}">${icon({ r_yes: 'check', r_no: 'x', r_pain: 'warn', r_not_understand: 'question', r_repeat: 'replay', r_water: 'drop', r_toilet: 'toilet', r_interpreter: 'phone' }[id])} ${esc(S.cfg.phrases[id][lang] || S.cfg.phrases[id].en)}</button>`).join('')}</div></div>
        <div><div class="section-title" style="margin:6px 4px 8px">${esc(S.cfg.phrases.where_hurt?.[lang] || 'Where does it hurt?')}</div><div class="card" id="ptBody"></div></div>
        <div><div class="section-title" style="margin:6px 4px 8px">${esc(ui.pain)}</div>
          <div class="pain-row" dir="ltr">${PAIN_COLORS.map((c, n) => `<button style="background:${c}" data-pain="${n}" aria-label="${n}"><span>${PAIN_FACES[n]}</span>${n}</button>`).join('')}</div></div>
        <button class="btn tinted red block xl" id="ptHuman">${icon('phone')} ${esc(ui.human)}</button>
      </div></div>`);
    on('#again', 'click', () => P.latest && speak(P.latest.translation, P.latest.tgtLang));
    on('#ptMic', 'click', toggleRecord);
    if ($('#ptBody')) bodyPicker($('#ptBody'), (regions) => sendReply({ bodyRegions: regions }, '📍 ' + regions.length));
    on('#ptTypeForm', 'submit', async (e) => {
      e.preventDefault();
      const text = $('#ptText').value.trim(); if (!text) return;
      try {
        const t = await api(`/api/sessions/${sid}/turns`, { body: { speaker: 'patient', text, srcLang: lang, tgtLang: 'en', mode: P.session.mode || 'standard' } });
        sync.add(t); P.mine = text; draw();
      } catch (err) { toast(err.message); }
    });
    on('[data-reply]', 'click', (e) => sendReply({ phraseId: e.currentTarget.dataset.reply }, S.cfg.phrases[e.currentTarget.dataset.reply][lang] || S.cfg.phrases[e.currentTarget.dataset.reply].en));
    on('[data-pain]', 'click', (e) => sendReply({ pain: Number(e.currentTarget.dataset.pain) }, `${e.currentTarget.dataset.pain}/10`));
    on('#ptHuman', 'click', () => { P.escalatedAt = Date.now(); api(`/api/sessions/${sid}/events`, { body: { kind: 'escalation', detail: 'Patient asked for a human interpreter' } }).catch(() => {}); draw(); speak(ui.interpreter_coming, lang); });
    on('#demoBtn', 'click', openPatientDemo);
  }

  async function sendReply(extra, label) {
    const lang = P.session.patientLang;
    try {
      const t = await api(`/api/sessions/${sid}/turns`, { body: { speaker: 'patient', srcLang: lang, tgtLang: 'en', mode: P.session.mode || 'standard', ...extra } });
      sync.add(t); P.mine = label; draw();
      if (extra.phraseId === 'r_interpreter') { P.escalatedAt = Date.now(); api(`/api/sessions/${sid}/events`, { body: { kind: 'escalation', detail: 'Patient asked for a human interpreter' } }).catch(() => {}); draw(); }
    } catch (e) { toast(e.message); }
  }

  async function toggleRecord() {
    if (!P.recording) {
      stopSpeaking();
      try { P.rec = new Recorder(); await P.rec.open(); P.rec.start(); } catch (e) { return toast(e.message); }
      P.recording = true; setActivity(sid, 'patient', 'speaking'); draw();
      setTimeout(() => { if (P.recording) toggleRecord(); }, 30000);
    } else {
      P.recording = false; draw();
      const blob = await P.rec.stop(); P.rec.close(); setActivity(sid, 'patient', 'idle');
      await sendAudio(blob);
    }
  }

  async function sendAudio(blob) {
    const lang = P.session.patientLang;
    const mc = $('.message-card'); if (mc) mc.innerHTML = `<div class="status"><span class="spinner"></span> …</div>`;
    try {
      const tr = await transcribe(blob, lang);
      if (!tr.text) { draw(); return; }
      const t = await api(`/api/sessions/${sid}/turns`, { body: { speaker: 'patient', text: tr.text, srcLang: lang, tgtLang: 'en', mode: P.session.mode || 'standard', asr: { duration: tr.duration, asrConfidence: tr.asrConfidence } } });
      sync.add(t); P.mine = tr.text; draw();
    } catch (e) { toast(e.message); draw(); }
  }

  function openPatientDemo() {
    openSheet(`<div class="sheet-head"><h3>Demo patient voice</h3><button class="navlink" data-close>Close</button></div>
      <p class="muted">For the demo only: a Ukrainian voice clip plays the patient's line, and the app hears it as if the patient spoke.</p>
      <div class="list">${S.cfg.demoClips.map((c) => `<button class="list-row" data-clip="${c.id}"><span class="row-icon" style="background:#30b0c7">${fillIcon('play')}</span><span class="row-text"><span class="row-title" lang="uk">${esc(c.text)}</span><br><span class="row-sub">${esc(c.en)}</span></span></button>`).join('')}</div>`, (bd, close) => {
      on('[data-clip]', 'click', async (e) => {
        close();
        const blob = await (await fetch(`audio/${e.currentTarget.dataset.clip}.wav`)).blob();
        await playBlob(blob);
        await sendAudio(blob);
      }, bd);
    });
  }
}

// ---------------------------------------------------------------------------------------------
// Live audit (observer) and audit log
// ---------------------------------------------------------------------------------------------
function statsHtml(turns, s) {
  const u = turns.filter((t) => t.type === 'utterance');
  const avg = u.length ? Math.round(u.reduce((a, t) => a + (t.meaning?.score || 0), 0) / u.length) : '–';
  const lat = u.length ? (u.reduce((a, t) => a + (t.latencyMs?.total || 0), 0) / u.length / 1000).toFixed(1) + 's' : '–';
  const red = u.filter((t) => t.risk.tier === 'red').length, amber = u.filter((t) => t.risk.tier === 'amber').length;
  const failed = u.filter((t) => t.status === 'fail').length;
  const escs = turns.filter((t) => t.type === 'event' && t.kind === 'escalation').length;
  const stat = (v, k, c = '') => `<div class="stat"><div class="v" style="${c ? 'color:var(--' + c + ')' : ''}">${v}</div><div class="k">${k}</div></div>`;
  return `<div class="stats">${stat(u.length, 'Sentences translated')}${stat(avg, 'Average meaning score', 'green')}${stat(amber, 'Clinical (amber)', 'orange')}${stat(red, 'Interpreter topics (red)', 'red')}${stat(failed, 'Flagged to confirm verbally', failed ? 'red' : '')}${stat(escs, 'Interpreter requests', escs ? 'red' : '')}${stat(lat, 'Average turn time')}${stat(s.status === 'ended' ? 'Ended' : 'Live', 'Status', s.status === 'ended' ? '' : 'green')}</div>`;
}

function auditRows(turns) {
  return [...turns].sort((a, b) => a.ts - b.ts).map((t) => {
    if (t.type === 'event') return `<div class="audit-row"><div class="t">${timeOf(t.ts)}</div><div class="l"><span class="event ${esc(t.kind)}" style="align-self:auto">${esc(t.detail)}</span> <span class="muted" style="font-size:.8rem">${esc(t.by || '')}</span></div></div>`;
    return `<div class="audit-row"><div class="t">${timeOf(t.ts)}</div><div class="l">
      <div class="hstack wrap"><strong>${t.speaker === 'clinician' ? esc(t.by) + ' (clinician)' : 'Patient'}</strong>${tierBadge(t.risk.tier)}${meaningChip(t.meaning)}<span class="chip">${esc(t.engine)}</span></div>
      <div class="k">Original · ${esc(L(t.srcLang).name)}</div><div dir="${L(t.srcLang).dir}">${esc(t.original)}</div>
      ${t.plain !== t.original ? `<div class="k">Plain English</div><div>${esc(t.plain)}</div>` : ''}
      <div class="k">Translation · ${esc(L(t.tgtLang).name)}</div><div dir="${L(t.tgtLang).dir}" style="font-weight:600">${esc(t.translation)}</div>
      <div class="k">Back-translation</div><div dir="${L(t.srcLang).dir}" class="muted">${esc(t.backTranslation)}</div>
      <div class="row hstack wrap" style="margin-top:8px">${checkChips(t)}${t.risk.reasons.length ? `<span class="chip">${esc(t.risk.reasons.join(', '))}</span>` : ''}${t.override ? `<span class="chip bad">Override: ${esc(t.override)}</span>` : ''}</div>
    </div></div>`;
  }).join('');
}

async function viewObserver(sid) {
  render(`${navbar({ left: `<a class="navlink" href="#/audit">${icon('chevL')} Audit</a>`, title: 'Live audit', right: `<button class="navlink" id="fhirBtn">${icon('doc')} FHIR</button>` })}
    <main class="page"><div id="obsHead" class="mt"></div><div id="obsStats"></div><div class="list" id="obsRows"></div></main>`);
  const sync = new Sync(sid, (s) => draw(s));
  S.cleanup.push(() => sync.stop());
  await sync.start();
  function draw(s) {
    $('#obsHead').innerHTML = `<h1 class="large-title" style="margin-top:6px">${s.mode === 'emergency' ? 'Emergency' : 'Consultation'} · ${s.patientLang ? esc(L(s.patientLang).name) : 'language not set'}</h1>
      <p class="subtitle">${esc(s.createdBy)} · ${new Date(s.createdAt).toLocaleString()} · code ${esc(s.code)}${s.mrn ? ' · ' + esc(s.mrn) : ''}</p>
      ${s.fhirKey ? `<div class="banner blue">${icon('doc')}<div class="b-body"><div class="b-title">Saved for the patient record</div>FHIR DocumentReference stored at ${esc(s.fhirKey)}</div></div>` : ''}`;
    $('#obsStats').innerHTML = statsHtml(sync.turns, s);
    $('#obsRows').innerHTML = auditRows(sync.turns) || '<div class="empty">No activity yet.</div>';
  }
  on('#fhirBtn', 'click', async () => {
    try {
      const doc = await api(`/api/sessions/${sid}/fhir`);
      const json = JSON.stringify(doc, null, 2);
      openSheet(`<div class="sheet-head"><h3>Export to patient record</h3><button class="navlink" data-close>Done</button></div>
        <p class="muted">HL7 FHIR R4 DocumentReference with the bilingual transcript, risk tiers, checks and escalations. A hospital integration engine can file this into the patient administration system.</p>
        <pre class="code">${esc(json)}</pre><button class="btn primary block" id="dl">${icon('download')} Download JSON</button>`, (bd) => on('#dl', 'click', () => {
          const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([json], { type: 'application/fhir+json' })); a.download = `carebridge-${sid}.json`; a.click();
        }, bd));
    } catch (e) { toast(e.message); }
  });
}

async function viewAudit() {
  render(`${navbar({ left: `<a class="navlink" href="#/home">${icon('chevL')} Home</a>`, title: 'Audit log' })}
    <main class="page narrow"><h1 class="large-title">Audit log</h1><p class="subtitle">Every session with its translations, checks and escalations. Audio is never stored.</p>
    <div class="list" id="auditList"><div class="empty"><span class="spinner"></span></div></div></main>`);
  const { sessions } = await api('/api/sessions');
  $('#auditList').innerHTML = sessions.length ? sessions.map((s) => `<button class="list-row" data-sid="${s.id}">
      <span class="row-icon" style="background:${s.mode === 'emergency' ? '#ff3b30' : '#007aff'}">${icon(s.mode === 'emergency' ? 'bolt' : 'stethoscope')}</span>
      <span class="row-text"><span class="row-title">${s.patientLang ? esc(L(s.patientLang).name) : 'Language not set'} · ${esc(s.createdBy)}</span><br>
      <span class="row-sub">${new Date(s.createdAt).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })} · ${s.status === 'ended' ? 'Ended' : 'Live'}${s.escalations ? ` · ${s.escalations} interpreter request${s.escalations > 1 ? 's' : ''}` : ''}</span></span>
      <span class="chev">${icon('chevR')}</span></button>`).join('') : '<div class="empty">No sessions yet.</div>';
  on('[data-sid]', 'click', (e) => go('#/observer/' + e.currentTarget.dataset.sid));
}

// ---------------------------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------------------------
async function viewSettings() {
  await refreshHealth();
  const h = S.health;
  const seg = (name, opts) => `<div class="segmented" data-set="${name}">${opts.map(([v, l]) => `<button data-v="${v}" aria-pressed="${String(S.settings[name]) === String(v)}">${l}</button>`).join('')}</div>`;
  render(`${navbar({ left: `<a class="navlink" href="#/home">${icon('chevL')} Home</a>`, title: 'Settings' })}
  <main class="page narrow">
    <h1 class="large-title">Settings</h1>
    <div class="section-title">Display</div>
    <div class="card">
      <div class="field"><span>Text size</span>${seg('scale', [[1, 'Default'], [1.15, 'Large'], [1.3, 'Extra large']])}</div>
      <div class="field"><span>Appearance</span>${seg('theme', [['auto', 'Automatic'], ['light', 'Light'], ['dark', 'Dark']])}</div>
      <div class="hstack"><span class="grow">High contrast</span><label class="toggle"><input type="checkbox" id="contrast" ${S.settings.contrast ? 'checked' : ''}><span></span></label></div>
    </div>
    <div class="section-title">Voice</div>
    <div class="card">
      <div class="field"><span>Spoken translations</span>${seg('voice', [['auto', 'Our server voices'], ['device', 'This device\'s voices']])}</div>
      <div class="field"><span>Speaking speed</span><input type="range" min="0.7" max="1.2" step="0.05" value="${S.settings.rate}" id="rate" style="width:100%"></div>
      <button class="btn tinted small" id="testVoice">${icon('speaker')} Test Ukrainian voice</button>
    </div>
    <div class="section-title">Privacy</div>
    <div class="card"><p style="margin:0">${icon('shield')} Audio is processed on CareBridge's own server inside the hospital's AWS account and is never stored. Only the text of each conversation is kept, in an encrypted audit log, for quality review and the patient record. Patients are told it is a computer translator and can ask for a human interpreter at any time.</p></div>
    <div class="section-title">AI models (self-hosted)</div>
    <div class="list">${h ? Object.entries(h.models).map(([k, v]) => `<div class="list-row"><span class="row-text"><span class="row-title">${esc({ speech: 'Speech to text', translation: 'Translation', meaning: 'Meaning check', voice: 'Voices' }[k] || k)}</span><br><span class="row-sub">${esc(h.modelInfo?.[k] || '')}</span></span><span class="pill ${v === 'ready' ? 'green' : v.startsWith('error') ? 'red' : 'orange'}">${esc(v)}</span></div>`).join('') : '<div class="list-row">Server unreachable</div>'}</div>
    <p class="fineprint">CareBridge prototype ${h ? 'v' + esc(h.version) : ''} · Healthcare Innovation Challenge 2026 · Signed in as ${esc(S.user)}</p>
    <button class="btn tinted red block mt" id="signOut">${icon('signout')} Sign out</button>
  </main>`);
  on('.segmented[data-set] button', 'click', (e) => {
    const name = e.currentTarget.parentElement.dataset.set; let v = e.currentTarget.dataset.v;
    if (name === 'scale') v = Number(v);
    S.settings[name] = v; applySettings();
    $$(`.segmented[data-set="${name}"] button`).forEach((b) => b.setAttribute('aria-pressed', b === e.currentTarget));
  });
  on('#contrast', 'change', (e) => { S.settings.contrast = e.target.checked; applySettings(); });
  on('#rate', 'input', (e) => { S.settings.rate = Number(e.target.value); applySettings(); });
  on('#testVoice', 'click', () => { AudioKit.unlock(); speak('Добрий день, я тут, щоб вам допомогти.', 'uk'); });
  on('#signOut', 'click', signOut);
}

// ---------------------------------------------------------------------------------------------
if ('speechSynthesis' in window) speechSynthesis.onvoiceschanged = () => {};
route();

// ---------------------------------------------------------------------------------------------
// Body map: the patient taps where it hurts (no language needed)
// ---------------------------------------------------------------------------------------------
const BODY_SHAPES = {
  // Front view: the patient's right side is on the viewer's left (as when facing the patient)
  front: [
    ['head', 'e', 100, 36, 24, 28], ['neck', 'r', 89, 66, 22, 16, 6],
    ['chest_r', 'r', 60, 84, 39, 54, 14], ['chest_l', 'r', 101, 84, 39, 54, 14],
    ['abd_upper', 'r', 62, 140, 76, 32, 10], ['abd_r', 'r', 62, 174, 37, 40, 10], ['abd_l', 'r', 101, 174, 37, 40, 10],
    ['groin', 'r', 66, 216, 68, 24, 12],
    ['arm_r', 'r', 34, 86, 22, 78, 11], ['hand_r', 'r', 28, 166, 22, 84, 11],
    ['arm_l', 'r', 144, 86, 22, 78, 11], ['hand_l', 'r', 150, 166, 22, 84, 11],
    ['thigh_r', 'r', 66, 242, 32, 80, 14], ['thigh_l', 'r', 102, 242, 32, 80, 14],
    ['knee_r', 'r', 67, 324, 30, 22, 10], ['knee_l', 'r', 103, 324, 30, 22, 10],
    ['leg_r', 'r', 68, 348, 28, 66, 12], ['leg_l', 'r', 104, 348, 28, 66, 12],
  ],
  // Back view: the patient's left side is on the viewer's left
  back: [
    ['head_back', 'e', 100, 36, 24, 28], ['neck_back', 'r', 89, 66, 22, 16, 6],
    ['back_ul', 'r', 60, 84, 39, 64, 14], ['back_ur', 'r', 101, 84, 39, 64, 14],
    ['back_ll', 'r', 62, 150, 37, 64, 10], ['back_lr', 'r', 101, 150, 37, 64, 10],
    ['buttocks', 'r', 66, 216, 68, 26, 13],
    ['arm_l', 'r', 34, 86, 22, 78, 11], ['hand_l', 'r', 28, 166, 22, 84, 11],
    ['arm_r', 'r', 144, 86, 22, 78, 11], ['hand_r', 'r', 150, 166, 22, 84, 11],
    ['thigh_l', 'r', 66, 244, 32, 78, 14], ['thigh_r', 'r', 102, 244, 32, 78, 14],
    ['knee_l', 'r', 67, 324, 30, 22, 10], ['knee_r', 'r', 103, 324, 30, 22, 10],
    ['leg_l', 'r', 68, 348, 28, 66, 12], ['leg_r', 'r', 104, 348, 28, 66, 12],
  ],
};
const BACK_REGIONS = new Set(['head_back', 'neck_back', 'back_ul', 'back_ur', 'back_ll', 'back_lr', 'buttocks']);
function bodySvg(view, selected = [], { interactive = true, height = 360 } = {}) {
  const sel = new Set(selected);
  const names = S.cfg?.bodyRegions || {};
  const shapes = BODY_SHAPES[view].map(([id, kind, a, b, c, d, rx]) => {
    const on = sel.has(id);
    const attrs = `data-region="${id}" ${interactive ? `role="button" tabindex="0" aria-pressed="${on}" aria-label="${esc(names[id] || id)}"` : ''} fill="${on ? 'var(--red-bright)' : 'var(--fill-2)'}" style="${interactive ? 'cursor:pointer;' : ''}transition:fill .2s"`;
    return kind === 'e' ? `<ellipse cx="${a}" cy="${b}" rx="${c}" ry="${d}" ${attrs}/>` : `<rect x="${a}" y="${b}" width="${c}" height="${d}" rx="${rx}" ${attrs}/>`;
  }).join('');
  const leftLabel = view === 'front' ? 'R' : 'L', rightLabel = view === 'front' ? 'L' : 'R';
  return `<svg viewBox="0 0 200 420" style="height:${height}px;width:auto;display:block;margin:0 auto" aria-label="Body map, ${view} view">
    ${shapes}<text x="10" y="80" font-size="16" font-weight="700" fill="var(--label-3)">${leftLabel}</text><text x="182" y="80" font-size="16" font-weight="700" fill="var(--label-3)">${rightLabel}</text></svg>`;
}
// Interactive picker. onSend(regions) is called with the chosen region ids.
function bodyPicker(root, onSend) {
  let view = 'front'; const sel = new Set();
  const draw = () => {
    root.innerHTML = `<div style="position:relative">${bodySvg(view, [...sel])}
      <button class="pill clickable" data-flip style="position:absolute;top:0;right:0" aria-label="Turn the body around">${icon('refresh')} ${view === 'front' ? '↻' : '↺'}</button></div>
      <div class="btn-row mt"><button class="btn success xl" data-send ${sel.size ? '' : 'disabled'} aria-label="Send">${icon('check')}</button>
      <button class="btn gray xl" data-clear ${sel.size ? '' : 'disabled'} aria-label="Clear">${icon('x')}</button></div>`;
    $$('[data-region]', root).forEach((el) => {
      const toggle = () => { const r = el.dataset.region; sel.has(r) ? sel.delete(r) : sel.add(r); draw(); };
      el.addEventListener('click', toggle);
      el.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } });
    });
    on('[data-flip]', 'click', () => { view = view === 'front' ? 'back' : 'front'; draw(); }, root);
    on('[data-clear]', 'click', () => { sel.clear(); draw(); }, root);
    on('[data-send]', 'click', async () => { const regions = [...sel]; sel.clear(); draw(); await onSend(regions); }, root);
  };
  draw();
}

// ---------------------------------------------------------------------------------------------
// Interpreter hand-off brief
// ---------------------------------------------------------------------------------------------
async function viewBrief(sid) {
  render(`${navbar({ left: `<a class="navlink" href="#/home">${icon('chevL')} Home</a>`, title: 'Interpreter brief', right: `<button class="navlink" id="liveBtn">${icon('clipboard')} Live</button>` })}
    <main class="page narrow" id="briefBody"><div class="empty"><span class="spinner"></span></div></main>`);
  on('#liveBtn', 'click', () => go('#/observer/' + sid));
  const draw = async () => {
    let b;
    try { b = await api(`/api/sessions/${sid}/brief`); } catch (e) { return; }
    const el = $('#briefBody'); if (!el) return;
    const lang = b.language || {};
    el.innerHTML = `
      <h1 class="large-title">${esc(lang.name || 'Language not set')} <span class="muted" dir="auto">${esc(lang.native || '')}</span></h1>
      <p class="subtitle">${b.requestedAt ? `Requested by ${esc(b.requestedBy)} at ${timeOf(b.requestedAt)}` : 'No interpreter requested yet'}${b.mrn ? ' · ' + esc(b.mrn) : ''} · ${b.turnCount} sentences so far</p>
      <div class="banner red">${icon('hand')}<div class="b-body"><div class="b-title">Why you were called</div>${esc(b.reason)}${b.redTopics.length ? `<div class="pills mt">${b.redTopics.map((r) => `<span class="pill red">${esc(r)}</span>`).join('')}</div>` : ''}</div></div>
      <div class="section-title">Key facts</div>
      <div class="keyfacts">${b.keyFacts.length ? b.keyFacts.map((f) => `<span class="keyfact ${f.kind === 'critical' ? '' : 'amber'}">${icon('warn')} ${esc(f.label)}</span>`).join('') : '<span class="muted">None recorded yet.</span>'}
        <span class="pill ${b.consent === 'accepted' ? 'green' : ''}">${icon('shield')} Consent to AI translator: ${esc(b.consent || 'not asked')}</span></div>
      ${b.needsAttention.length ? `<div class="section-title">Please check with the patient</div><div class="list">${b.needsAttention.map((n) => `<div class="audit-row"><div class="t">${timeOf(n.ts)}</div><div class="l"><strong>${n.speaker === 'clinician' ? 'Clinician' : 'Patient'}:</strong> ${esc(n.english)}<div class="muted" dir="auto">${esc(n.original)}</div><div class="row hstack wrap" style="margin-top:6px">${n.why.map((w) => `<span class="chip bad">${esc(w)}</span>`).join('')}</div></div></div>`).join('')}</div>` : ''}
      <div class="section-title">Conversation so far</div>
      <div class="list">${b.recent.length ? b.recent.map((r) => `<div class="audit-row"><div class="t">${timeOf(r.ts)}</div><div class="l"><strong>${r.speaker === 'clinician' ? 'Clinician' : 'Patient'}:</strong> ${esc(r.english)}<div class="muted" dir="auto">${esc(r.patientLanguage)}</div></div></div>`).join('') : '<div class="empty">Nothing said yet.</div>'}</div>
      <p class="fineprint">This brief updates live. It is generated from the CareBridge transcript; translations are AI-generated and checked automatically.</p>`;
  };
  await draw();
  const timer = setInterval(draw, 3000);
  S.cleanup.push(() => clearInterval(timer));
}

// ---------------------------------------------------------------------------------------------
// Offline phrasebook: pre-checked phrases, tap answers, pain scale and body map without Wi-Fi
// ---------------------------------------------------------------------------------------------
function logOffline(entry) {
  const q = store.get('offlineLog', []); q.push({ ...entry, at: Date.now(), by: S.user }); store.set('offlineLog', q.slice(-200));
}
async function syncOfflineLog() {
  const q = store.get('offlineLog', []);
  if (!q.length || !navigator.onLine || !S.token) return;
  try {
    const s = await api('/api/sessions', { body: { mode: 'offline', patientLang: q[0].lang || null } });
    for (const e of q) await api(`/api/sessions/${s.id}/events`, { body: { kind: 'note', detail: `Offline phrasebook (${new Date(e.at).toLocaleTimeString()}): ${e.text}` } });
    await api(`/api/sessions/${s.id}/end`, { body: {} });
    store.del('offlineLog');
    toast(`${q.length} offline phrase${q.length > 1 ? 's' : ''} added to the audit log`);
  } catch { /* try again later */ }
}
window.addEventListener('online', () => { syncOfflineLog(); if (location.hash === '#/home') route(); });
window.addEventListener('offline', () => { if (location.hash === '#/home') route(); });

async function viewPhrasebook() {
  let lang = store.get('lastLang', 'uk');
  if (!L(lang).native || !S.cfg.patientLangs.includes(lang)) lang = S.cfg.patientLangs[0];
  render(`${navbar({ left: `<a class="navlink" href="#/home">${icon('chevL')} Home</a>`, title: 'Offline phrasebook', right: `<button class="navlink" id="pbLang">${icon('globe')}</button>` })}
    <main class="page narrow" id="pb"></main>`);
  on('#pbLang', 'click', () => openLangSheet(lang, (code) => { lang = code; store.set('lastLang', code); draw(); }, 'Phrasebook language'));
  const show = (big, small, speakText, speakLang) => {
    const card = $('#pbCard');
    card.innerHTML = `<div class="msg" dir="${L(speakLang).dir}" style="font-size:1.9rem;font-weight:700;line-height:1.25">${esc(big)}</div><div class="muted mt">${esc(small)}</div>`;
    card.scrollIntoView({ behavior: 'smooth', block: 'center' });
    if (speakText) deviceSpeak(speakText, speakLang);
  };
  const draw = () => {
    const ph = S.cfg.phrases, en = (id) => ph[id].en;
    $('#pb').innerHTML = `
      <h1 class="large-title">${esc(L(lang).native)}</h1>
      <p class="subtitle">${navigator.onLine ? 'Works even without Wi-Fi: everything here is stored on this device.' : 'You are offline. Everything here still works.'} Spoken with this device's own voice.</p>
      <div class="message-card" id="pbCard" style="min-height:140px"><div class="status">${icon('info')} Tap a phrase.</div></div>
      <div class="section-title">Clinician says</div>
      <div class="phrase-chips">${S.cfg.clinicianPhrases.filter((id) => ph[id][lang]).map((id) => `<button data-c="${id}">${esc(en(id))}</button>`).join('')}</div>
      <div class="section-title">Patient answers</div>
      <div class="reply-grid">${S.cfg.quickReplies.filter((id) => ph[id][lang]).map((id) => `<button class="reply" data-p="${id}" dir="${L(lang).dir}">${esc(ph[id][lang])}</button>`).join('')}</div>
      <div class="section-title">Pain score</div>
      <div class="pain-row" dir="ltr">${PAIN_COLORS.map((c, n) => `<button style="background:${c}" data-pain="${n}" aria-label="${n}"><span>${PAIN_FACES[n]}</span>${n}</button>`).join('')}</div>
      <div class="section-title">Where does it hurt?</div>
      <div class="card" id="pbBody"></div>
      <p class="fineprint">${L(lang).drafted ? 'Phrases drafted by the team, pending review by a TUH interpreter.' : 'Machine-translated phrases, pending review by a TUH interpreter.'} Every tap is logged on this device and added to the audit log when you are back online.</p>`;
    on('[data-c]', 'click', (e) => { const id = e.currentTarget.dataset.c; show(ph[id][lang], en(id), ph[id][lang], lang); logOffline({ lang, text: `Clinician: ${en(id)}` }); });
    on('[data-p]', 'click', (e) => { const id = e.currentTarget.dataset.p; show(en(id), ph[id][lang], en(id), 'en'); logOffline({ lang, text: `Patient: ${en(id)}` }); });
    on('[data-pain]', 'click', (e) => { const n = e.currentTarget.dataset.pain; show(`Pain ${n} out of 10`, PAIN_FACES[n], `Pain ${n} out of 10`, 'en'); logOffline({ lang, text: `Patient pain score ${n}/10` }); });
    bodyPicker($('#pbBody'), (regions) => {
      const names = regions.map((r) => S.cfg.bodyRegions[r]).join(', ');
      show(`It hurts here: ${names}`, '', `It hurts here: ${names}`, 'en'); logOffline({ lang, text: `Patient body map: ${names}` });
    });
  };
  draw();
}

if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(() => {});
