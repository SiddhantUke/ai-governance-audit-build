(function () {
  var savedRunAudit = (typeof runAudit === "function") ? runAudit : null;

  if (typeof pendingFindings === "function") {
    renderReview = function () {
      var box = document.getElementById("review");
      if (!box) {
        return;
      }
      var q = pendingFindings();
      if (!q.length) {
        box.innerHTML = "<p>No findings waiting for review.</p>";
        return;
      }
      function txt(s) {
        if (typeof esc === "function") {
          return esc(s);
        }
        return String(s == null ? "" : s);
      }
      function verdictBadge(v) {
        if (typeof badge === "function") {
          return badge(v);
        }
        return txt(v);
      }
      var html = "<table><tr><th>Tool</th><th>Requirement</th><th>Verdict</th><th>Confidence</th><th>Why it is uncertain</th><th>Action</th></tr>";
      q.forEach(function (f) {
        html += "<tr><td>" + txt(f.tool_name) + "</td><td>" + txt(f.framework) + " " + txt(f.clause) + "</td><td>" + verdictBadge(f.verdict) + "</td><td>" + f.confidence + "</td><td>" + txt(f.rationale) + "</td><td><button class=\"small\" onclick=\"doReview('" + f.id + "','approve')\">Approve</button> <button class=\"small edit\" onclick=\"doReview('" + f.id + "','edit')\">Edit to Partial</button> <button class=\"small reject\" onclick=\"doReview('" + f.id + "','reject')\">Reject</button></td></tr>";
      });
      html += "</table>";
      box.innerHTML = html;
    };
  }

  function getToken() {
    return localStorage.getItem("gov_audit_token");
  }

  function setStatus(text) {
    var el = document.getElementById("connectStatus");
    if (el) {
      el.textContent = text;
    }
  }

  function sleepMs(ms) {
    return new Promise(function (resolve) {
      setTimeout(resolve, ms);
    });
  }

  async function apiCall(path, options) {
    if (typeof api === "function") {
      return api(path, options);
    }
    var headers = {};
    var token = getToken();
    if (token) {
      headers["Authorization"] = "Bearer " + token;
    }
    var body = options ? options.body : undefined;
    if (body && !(body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }
    var res = await fetch(path, {
      method: (options && options.method) || "GET",
      headers: headers,
      body: body
    });
    var data = await res.json().catch(function () { return {}; });
    if (!res.ok) {
      throw new Error((data && data.detail) || ("HTTP " + res.status));
    }
    return data;
  }

  runAudit = async function () {
    if (!getToken()) {
      setStatus("Log in first, then click Run Audit.");
      return;
    }

    var custom;
    try {
      custom = await apiCall("/api/custom-requirements");
    } catch (e) {
      setStatus("Could not check uploaded requirements: " + e.message + " — log in again, then Run Audit.");
      return;
    }
    var customList = Array.isArray(custom) ? custom : (custom.requirements || []);
    if (customList.length === 0) {
        setStatus("No uploaded document found — audit not run. Upload a document first, then click Run Audit.");
        return;
    }


    setStatus("Uploaded document found (" + customList.length + " requirements) — running uploaded-only audit...");
    var job;
    try {
      job = await apiCall("/api/audit/jobs?source=uploaded_only", { method: "POST" });
    } catch (e) {
      setStatus("Uploaded-only audit failed to start: " + e.message + " — upload the document again, then Run Audit.");
      return;
    }

    var detail = null;
    for (var i = 0; i < 40; i++) {
      await sleepMs(1500);
      try {
        detail = await apiCall("/api/audit/jobs/" + job.job_id);
      } catch (e) {
        setStatus("Could not poll job: " + e.message);
        return;
      }
      if (detail.status === "completed" || detail.status === "failed") {
        break;
      }
    }
    if (!detail || detail.status !== "completed") {
      setStatus("Uploaded-only audit did not complete: " + (detail && detail.error ? detail.error : "timeout — try again"));
      return;
    }
    if (typeof replaceFindings !== "function") {
      setStatus("Audit completed but findings could not be displayed.");
      return;
    }
    replaceFindings(detail.findings);
    audited = true;
    if (typeof renderScores === "function") { renderScores(); }
    if (typeof renderFindingsTable === "function") { renderFindingsTable(); }
    if (typeof renderReview === "function") { renderReview(); }
    if (typeof renderReport === "function") { renderReport(); }

    var s = detail.summary || {};
    var total = s.total || detail.findings.length;
    var score = s.report_score_percent;
    if ((score === undefined || score === null) && s.report_total) {
      score = Math.round((s.compliant / s.report_total) * 1000) / 10;
    }
    setStatus("Uploaded-only audit completed — Job " + job.job_id + ": " + total + " findings from your uploaded document only. Compliant " + (s.compliant || 0) + ", Gap " + (s.gap || 0) + ", Pending " + (s.pending_review || 0) + ", Score " + score + "%.");
  };
})();
