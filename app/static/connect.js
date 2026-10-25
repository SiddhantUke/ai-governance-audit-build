// connect.js — Connected mode for governance-audit-demo.html
// Runs AFTER the demo script. Saves original demo functions, then overrides
// them with live API versions when Connected mode is ON.
// Offline mode (default) keeps the original simulated behaviour untouched.

const TOKEN_KEY = "gov_audit_token";
let CONNECTED = false;

const origRunExtract = window.runExtract;
const origRunUpload = window.runUpload;
const origRunAudit = window.runAudit;
const origDoReview = window.doReview;

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function setToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
  updateAuthStatus();
}

async function api(path, options) {
  const headers = {};
  const token = getToken();
  if (token) {
    headers["Authorization"] = "Bearer " + token;
  }
  if (options && options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(path, { ...(options || {}), headers: { ...headers, ...((options && options.headers) || {}) } });
  const text = await response.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch (e) { data = null; }
  if (!response.ok) {
    const detail = data && data.detail ? data.detail : ("HTTP " + response.status);
    throw new Error(detail);
  }
  return data;
}

function showStatus(message) {
  const el = document.getElementById("connectStatus");
  if (el) {
    el.textContent = message;
  }
}

function updateAuthStatus() {
  const el = document.getElementById("authStatus");
  if (!el) return;
  const token = getToken();
  el.textContent = token ? "Logged in (token saved). Click 'Who am I' to confirm user/role." : "Not logged in. Library + health are public; extract/upload/audit/review need auditor/admin login.";
}

async function whoAmI() {
  try {
    const me = await api("/api/auth/me");
    showStatus("Logged in as " + me.username + " (" + me.role + ")");
  } catch (err) {
    showStatus("Who am I failed: " + err.message);
  }
}

async function doLogin() {
  const username = document.getElementById("loginUser").value.trim();
  const password = document.getElementById("loginPass").value;
  if (!username || !password) { showStatus("Enter username and password first."); return; }
  try {
    const form = new URLSearchParams();
    form.append("username", username);
    form.append("password", password);
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form
    });
    const data = await response.json();
    if (!response.ok) { throw new Error(data.detail || ("HTTP " + response.status)); }
    setToken(data.access_token);
    showStatus("Login successful. Token saved.");
  } catch (err) {
    showStatus("Login failed: " + err.message);
  }
}

async function doRegister() {
  const username = document.getElementById("loginUser").value.trim();
  const password = document.getElementById("loginPass").value;
  if (!username || !password) { showStatus("Enter username and password first."); return; }
  try {
    const data = await api("/api/auth/register", { method: "POST", body: JSON.stringify({ username: username, password: password }) });
    showStatus("Registered " + data.username + " as " + data.role + ". Now log in with that password.");
  } catch (err) {
    showStatus("Register failed: " + err.message);
  }
}

function doLogout() {
  setToken(null);
  showStatus("Logged out. Token cleared.");
}

function mapFinding(f) {
  return {
    id: f.id,
    tool_id: f.tool_id,
    tool_name: f.tool_name,
    requirement_id: f.requirement_id,
    framework: f.framework,
    clause: f.clause,
    requirement_title: f.obligation,
    risk_tier: f.risk_tier || "",
    verdict: f.verdict,
    rationale: f.reason || "",
    confidence: f.confidence,
    match_score: 0,
    citation: f.framework + " " + f.clause,
    source_quote: "",
    evidence_needed: f.evidence_required ? [f.evidence_required] : [],
    satisfied_controls: [],
    missing_controls: [],
    unknown_controls: [],
    review_status: f.needs_review ? "pending_review" : "auto",
    review_note: null
  };
}

function replaceFindings(serverFindings) {
  findings.length = 0;
  serverFindings.forEach(function (f) { findings.push(mapFinding(f)); });
  Object.keys(state).forEach(function (k) { delete state[k]; });
  findings.forEach(function (f) {
    state[f.id] = f.review_status === "pending_review" ? "pending_review" : "auto";
  });
}

function renderConnectedLibrary(frameworks, tools) {
  const grouped = {};
  frameworks.forEach(function (r) {
    if (!grouped[r.framework]) grouped[r.framework] = [];
    grouped[r.framework].push(r);
  });
  document.getElementById("frameworks").innerHTML =
    Object.entries(grouped).map(function (entry) {
      const name = entry[0];
      const list = entry[1];
      return "<p><strong>" + esc(name) + "</strong> — " + list.length + " requirements: " +
        list.map(function (r) { return esc(r.clause + " " + r.obligation); }).join("; ") + "</p>";
    }).join("") + "<p>Total: " + frameworks.length + " requirements (live backend)</p>";
  document.getElementById("inventory").innerHTML =
    "<table><tr><th>Tool</th><th>Vendor</th><th>Category</th><th>Controls</th></tr>" +
    tools.map(function (t) {
      const controls = Object.entries(t.controls || {}).map(function (entry) {
        const val = entry[1] === true ? "✓" : entry[1] === false ? "✗" : "?";
        return esc(entry[0]) + ":" + val;
      }).join(", ");
      return "<tr><td>" + esc(t.name) + "</td><td>" + esc(t.vendor) + "</td><td>" + esc(t.category) + "</td><td>" + controls + "</td></tr>";
    }).join("") + "</table>";
}

async function connectBackend() {
  try {
    const health = await api("/api/health");
    if (health.step !== undefined) {
      showStatus("Backend reachable (health step " + health.step + "). Loading live library...");
    }
    const frameworks = await api("/api/frameworks");
    const tools = await api("/api/inventory");
    renderConnectedLibrary(frameworks, tools);
    CONNECTED = true;
    const badge = document.getElementById("modeBadge");
    if (badge) badge.textContent = "Connected — live backend";
    showStatus("Connected. Extract / upload / audit / review now use live APIs.");
  } catch (err) {
    showStatus("Connect failed: " + err.message + " — staying in offline demo mode. Check the server on port 8010.");
  }
}

function disconnectBackend() {
  CONNECTED = false;
  const badge = document.getElementById("modeBadge");
  if (badge) badge.textContent = "Offline demo (embedded data)";
  showStatus("Disconnected. Refresh the page to restore the original offline demo data, or click Connect again.");
}

const SAMPLE_TEXT = "Providers shall maintain human oversight of high-risk AI systems. Evidence required: oversight procedure. Providers shall keep logs automatically generated by high-risk AI systems. Evidence required: system logs.";

function mapExtractions(serverRequirements, provider) {
  return {
    count: serverRequirements.length,
    provider: provider,
    needs_review_count: serverRequirements.filter(function (r) { return r.needs_review; }).length,
    extractions: serverRequirements.map(function (r) {
      return {
        clause: r.clause,
        title: r.obligation,
        control_type: r.control_type,
        risk_tier: r.risk_tier,
        confidence: r.confidence,
        needs_review: r.needs_review,
        source_quote: r.source_quote
      };
    })
  };
}

window.runExtract = async function () {
  if (!CONNECTED) { return origRunExtract(); }
  try {
    const data = await api("/api/extract", { method: "POST", body: JSON.stringify({ text: SAMPLE_TEXT, source: "sample guideline" }) });
    renderExtractions(mapExtractions(data.requirements, "Groq openai/gpt-oss-120b (live)"));
    showStatus("Live extraction: " + data.extracted + " extracted, " + data.rejected + " rejected by the quote guard.");
  } catch (err) {
    showStatus("Live extraction failed: " + err.message + " (need auditor/admin login + GROQ_API_KEY on the server)");
  }
};

window.runUpload = async function () {
  if (!CONNECTED) { return origRunUpload(); }
  const fileInput = document.getElementById("uploadFile");
  const file = fileInput && fileInput.files ? fileInput.files[0] : null;
  if (!file) { alert("Choose a guideline file first."); return; }
  try {
    const form = new FormData();
    form.append("file", file);
    const data = await api("/api/upload", { method: "POST", body: form });
    renderExtractions(mapExtractions(data.requirements, "Groq openai/gpt-oss-120b (live upload)"));
    showStatus("Live upload: document " + data.document + ", " + data.extracted + " extracted, " + data.rejected + " rejected, " + data.chunks + " chunks.");
  } catch (err) {
    showStatus("Live upload failed: " + err.message);
  }
};

window.runAudit = async function () {
  if (!CONNECTED) { return origRunAudit(); }
  const runBtn = document.getElementById("runBtn");
  if (runBtn) runBtn.disabled = true;
  try {
    showStatus("Creating background job...");
    const stepsEl = document.getElementById("steps");
    if (stepsEl) stepsEl.innerHTML = "<p>Job created, polling...</p>";
    const job = await api("/api/audit/jobs?source=combined", { method: "POST" });
    let detail = null;
    for (let i = 0; i < 40; i++) {
      await new Promise(function (r) { setTimeout(r, 1500); });
      detail = await api("/api/audit/jobs/" + job.job_id);
      if (detail.status === "completed" || detail.status === "failed") break;
    }
    if (!detail || detail.status !== "completed") {
      showStatus("Job did not complete: " + (detail ? detail.status + " " + (detail.error || "") : "no response"));
      if (runBtn) runBtn.disabled = false;
      return;
    }
    replaceFindings(detail.findings || []);
    audited = true;
    if (stepsEl) stepsEl.innerHTML = "<p>Job completed.</p>";
    renderScores();
    renderFindingsTable();
    renderReview();
    renderReport();
    showStatus("Live audit done: job " + detail.job_id + ", " + detail.summary.total + " findings, score " + detail.summary.report_score_percent + "% (build-along numbers).");
  } catch (err) {
    showStatus("Live audit failed: " + err.message + " (need auditor/admin login)");
  }
  if (runBtn) runBtn.disabled = false;
};

window.doReview = async function (id, action) {
  if (!CONNECTED) { return origDoReview(id, action); }
  if (action === "edit") {
    alert("Edit to Partial is not supported by the build-along backend (approve/reject only). Use Approve or Reject in connected mode.");
    return;
  }
  try {
    await api("/api/review/" + encodeURIComponent(id), { method: "POST", body: JSON.stringify({ decision: action }) });
    state[id] = action === "approve" ? "approved" : "rejected";
    renderReview();
    renderScores();
    renderFindingsTable();
    renderReport();
    showStatus("Review saved on server: " + id + " -> " + action);
  } catch (err) {
    showStatus("Review failed: " + err.message);
  }
};

// Login bar + mode bar, injected at the top so the original demo file is untouched except one script tag.
(function injectBars() {
  const bar = document.createElement("div");
  bar.style.cssText = "border:2px solid #333;padding:12px;margin:12px 0;background:#fffbe6;";
  bar.innerHTML =
    '<strong>Connected mode</strong> — <span id="modeBadge">Offline demo (embedded data)</span><br>' +
    '<input id="loginUser" placeholder="username" style="margin:6px 6px 6px 0;">' +
    '<input id="loginPass" type="password" placeholder="password" style="margin:6px;">' +
    '<button onclick="doLogin()">Log in</button> ' +
    '<button onclick="doRegister()">Register</button> ' +
    '<button onclick="whoAmI()">Who am I</button> ' +
    '<button onclick="doLogout()">Log out</button> ' +
    '<button onclick="connectBackend()">Connect to backend</button> ' +
    '<button onclick="disconnectBackend()">Back to offline demo</button>' +
    '<div id="authStatus" style="margin-top:6px;">Not logged in. Library + health are public; extract/upload/audit/review need auditor/admin login.</div>' +
    '<div id="connectStatus" style="margin-top:6px;"></div>';
  document.body.insertBefore(bar, document.body.firstChild);
  updateAuthStatus();
  window.doLogin = doLogin;
  window.doRegister = doRegister;
  window.whoAmI = whoAmI;
  window.doLogout = doLogout;
  window.connectBackend = connectBackend;
  window.disconnectBackend = disconnectBackend;
})();
