const $ = id => document.getElementById(id);
const screens = ["setup-screen", "lock-screen", "home-screen", "app-screen"];

let state = null;
let currentApp = "home";
let lockPoll = null;
let lockoutTimer = null;
let lockoutDemo = { attempts: 0, total: 0, lockedUntil: 0, log: [] };

function show(id) {
  screens.forEach(screen => $(screen).classList.toggle("hidden", screen !== id));
}

async function api(path, { method = "GET", body = null } = {}) {
  const options = { method, headers: {} };
  if (body !== null) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  try {
    const response = await fetch(path, options);
    const data = await response.json().catch(() => ({}));
    return { ok: response.ok, ...data };
  } catch (error) {
    return {
      ok: false,
      message: "Cannot reach the virtual phone server. Start it from the BFL terminal with 'phone launch'."
    };
  }
}

function setMessage(element, text, ok) {
  element.textContent = text;
  element.classList.toggle("success", Boolean(ok));
  element.classList.toggle("error", !ok);
}

function clock() {
  const now = new Date();
  const time = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
  $("status-time").textContent = time;
  $("clock-time").textContent = time;
  $("home-clock").textContent = time;
  $("clock-date").textContent = now.toLocaleDateString(undefined, {
    weekday: "long", month: "long", day: "numeric"
  }).toUpperCase();
  $("home-date").textContent = now.toLocaleDateString(undefined, {
    weekday: "long", day: "numeric", month: "long"
  });
}

function stopLockPolling() {
  if (lockPoll) {
    clearInterval(lockPoll);
    lockPoll = null;
  }
}

function startLockPolling() {
  if (lockPoll) return;
  lockPoll = setInterval(async () => {
    const next = await api("/api/state");
    if (next.ok === false && next.message) return;
    state = next;
    updateLockStatus();
    if (!state.locked) {
      stopLockPolling();
      if (state.unlocked) refresh();
    }
  }, 1000);
}

function updateLockStatus() {
  if (!state) return;
  const element = $("lock-status");
  if (state.locked) {
    element.textContent = "Security lock active: " + state.lock_seconds + "s remaining";
    startLockPolling();
  } else {
    element.textContent = state.configured ? "Enter your PIN to unlock" : "";
    stopLockPolling();
  }
}

async function refresh() {
  state = await api("/api/state");
  if (state.ok === false && state.message && typeof state.configured === "undefined") {
    $("setup-message").textContent = state.message;
    show("setup-screen");
    return;
  }

  if (!state.configured) show("setup-screen");
  else if (state.unlocked) show("home-screen");
  else show("lock-screen");

  updateLockStatus();
}

function row(label, value = "") {
  return '<div class="setting-row"><span>' + label + '</span><span>' + value + '</span></div>';
}

function actionRow(label, detail, action) {
  return '<button type="button" class="setting-row setting-action" data-action="' + action + '">' +
    '<span><strong>' + label + '</strong><small>' + detail + '</small></span>' +
    '<span class="row-arrow" aria-hidden="true">›</span></button>';
}

function renderApp(title, content) {
  $("app-content").innerHTML =
    '<div class="app-body"><p class="eyebrow">VIRTUAL APPLICATION</p><h2>' +
    title + '</h2>' + content + '</div>';
  $("back-home").textContent = currentApp === "pin-protection" ? "← Security" : "← Home";
  show("app-screen");
}

function lockoutRemaining() {
  return Math.max(0, Math.ceil((lockoutDemo.lockedUntil - Date.now()) / 1000));
}

function scheduleLockoutRender() {
  if (lockoutTimer) return;
  lockoutTimer = setTimeout(() => {
    lockoutTimer = null;
    if (currentApp === "lockout-demo") renderLockoutDemo();
  }, 1000);
}

function renderLockoutDemo() {
  const locked = lockoutRemaining() > 0;
  if (locked) scheduleLockoutRender();

  const max = state.max_failures;
  const log = lockoutDemo.log.length
    ? lockoutDemo.log.slice().reverse().map(item =>
        '<div class="demo-log-row"><span>' + item.label + '</span><b>' + item.result + '</b></div>'
      ).join("")
    : '<p class="app-description">No simulated attempts yet.</p>';

  renderApp("Lockout Demo",
    '<p class="app-description"><strong>SIMULATION ONLY.</strong> This panel demonstrates the device policy. It never sends guesses to the real PIN verifier. The lockout timer is shortened to 5 seconds for the demo.</p>' +
    '<div class="demo-stat"><small>SIMULATED ATTEMPTS THIS ROUND</small><strong>' +
      lockoutDemo.attempts + ' / ' + max + '</strong></div>' +
    '<button type="button" class="security-lock-button" data-action="demo-attempt"' +
      (locked ? ' disabled' : '') + '>TRY A SIMULATED UNLOCK</button>' +
    '<button type="button" class="demo-reset-button" data-action="demo-reset">RESET DEMO</button>' +
    (locked ? '<p class="demo-lock">Simulated lockout: ' + lockoutRemaining() + 's remaining</p>' : '') +
    '<h3 class="demo-heading">EVENT LOG</h3><div class="demo-log">' + log + '</div>' +
    '<p class="app-description">The real device locks for ' + state.lockout_seconds +
      ' seconds after ' + max + ' failed attempts. This panel uses a 5-second timer so the demo stays quick.</p>');
}

function openApp(name) {
  currentApp = name;

  if (name === "settings") {
    renderApp("Settings",
      row("Display", "Adaptive") +
      row("Sound", "Enabled") +
      actionRow("Security & PIN protection", "Manage virtual device security", "open-security") +
      row("Network", "Offline / local only"));
    return;
  }

  if (name === "security") {
    renderApp("Security",
      '<p class="app-description">Review the protection currently active on this simulated device.</p>' +
      actionRow("PIN Protection", "View authentication and lockout status", "open-pin-protection") +
      row("Lockout threshold", state.max_failures + " attempts") +
      row("Lockout duration", state.lockout_seconds + " seconds") +
      row("PIN length", state.pin_length + " digits") +
      row("PIN storage", "Salted PBKDF2-HMAC-SHA256"));
    return;
  }

  if (name === "pin-protection") {
    const locked = Boolean(state.locked);
    renderApp("PIN Protection",
      '<p class="app-description">This local virtual device uses a PIN to control access.</p>' +
      row("PIN configured", state.configured ? "Yes" : "No") +
      row("Device status", state.unlocked ? "Unlocked" : "Locked") +
      row("Failed attempts", state.failed_attempts + " / " + state.max_failures) +
      row("Lockout status", locked ? "Active — " + state.lock_seconds + "s remaining" : "Not active") +
      row("PIN verification", "PBKDF2-HMAC-SHA256") +
      row("KDF iterations", Number(state.kdf_iterations).toLocaleString()) +
      '<button type="button" class="security-lock-button" data-action="lock-device">LOCK DEVICE</button>' +
      '<p class="app-description">The PIN verifier is stored locally as a salted hash. The PIN itself is not stored.</p>');
    return;
  }

  if (name === "lockout-demo") {
    renderLockoutDemo();
    return;
  }

  if (name === "about") {
    renderApp("About device",
      row("Model", "BFL-VIRTUAL-01") +
      row("Software", "BFL Phone OS 1.0") +
      row("Connectivity", "Loopback only") +
      row("Calls", "Not supported"));
    return;
  }

  const pages = {
    gallery: ["Gallery", '<p class="app-description">Your simulated gallery is empty. No real files are accessed.</p>'],
    calculator: ["Calculator", '<p class="app-description">Calculator application placeholder.</p>'],
    files: ["Files", '<p class="app-description">Virtual storage is empty. No computer files are accessed.</p>']
  };
  const page = pages[name] || [
    "Unknown app",
    '<p class="app-description">This app is not available in the simulator.</p>'
  ];
  renderApp(page[0], page[1]);
}

$("setup-form").addEventListener("submit", async event => {
  event.preventDefault();
  const result = await api("/api/setup-pin", {
    method: "POST",
    body: { pin: $("setup-pin").value, confirmation: $("setup-confirm").value }
  });
  setMessage($("setup-message"), result.message || "PIN setup failed.", result.ok);
  $("setup-pin").value = "";
  $("setup-confirm").value = "";
  if (result.ok) await refresh();
});

$("unlock-form").addEventListener("submit", async event => {
  event.preventDefault();
  const result = await api("/api/unlock", {
    method: "POST",
    body: { pin: $("unlock-pin").value }
  });
  setMessage($("unlock-message"), result.message || "Unlock failed.", result.ok);
  $("unlock-pin").value = "";
  await refresh();
});

$("lock-button").addEventListener("click", async () => {
  await api("/api/lock", { method: "POST", body: {} });
  $("unlock-message").textContent = "";
  await refresh();
});

$("back-home").addEventListener("click", () => {
  if (currentApp === "pin-protection") {
    openApp("security");
  } else {
    currentApp = "home";
    if (lockoutTimer) {
      clearTimeout(lockoutTimer);
      lockoutTimer = null;
    }
    show("home-screen");
  }
});

document.querySelectorAll("[data-app]").forEach(button => {
  button.addEventListener("click", () => openApp(button.dataset.app));
});

$("app-content").addEventListener("click", async event => {
  const actionButton = event.target.closest("[data-action]");
  if (!actionButton) return;
  const action = actionButton.dataset.action;

  if (action === "open-security") {
    openApp("security");
    return;
  }
  if (action === "open-pin-protection") {
    openApp("pin-protection");
    return;
  }
  if (action === "lock-device") {
    await api("/api/lock", { method: "POST", body: {} });
    $("unlock-message").textContent = "";
    await refresh();
    return;
  }
  if (action === "demo-attempt") {
    if (lockoutRemaining() > 0) return;
    lockoutDemo.total += 1;
    lockoutDemo.attempts += 1;
    const label = "SIM-" + String(lockoutDemo.total).padStart(3, "0");
    if (lockoutDemo.attempts >= state.max_failures) {
      lockoutDemo.log.push({ label, result: "LOCKED" });
      lockoutDemo.attempts = 0;
      lockoutDemo.lockedUntil = Date.now() + 5000;
    } else {
      lockoutDemo.log.push({ label, result: "REJECTED" });
    }
    if (lockoutDemo.log.length > 100) lockoutDemo.log.shift();
    renderLockoutDemo();
    return;
  }
  if (action === "demo-reset") {
    if (lockoutTimer) {
      clearTimeout(lockoutTimer);
      lockoutTimer = null;
    }
    lockoutDemo = { attempts: 0, total: 0, lockedUntil: 0, log: [] };
    renderLockoutDemo();
  }
});

clock();
setInterval(clock, 1000);
refresh();
