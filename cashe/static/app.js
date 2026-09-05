function pollInvestigation(runId) {
  pollBoard(runId);
}

async function pollBoard(runId) {
  const tape = document.getElementById("tape");
  const statusEl = document.getElementById("status");
  const nowEl = document.getElementById("now-line");
  let lastSeq = 0;
  const seen = new Set();
  let evidenceSignature = "";

  async function tick() {
    const board = await fetch(`/api/investigations/${runId}/board`).then((r) => r.json());
    const inv = board.investigation || {};
    const evidence = await fetch(`/api/investigations/${runId}/evidence`).then((r) => r.json());
    const signature = JSON.stringify(evidence);
    if (signature !== evidenceSignature) {
      renderBrowserEvidence(evidence);
      evidenceSignature = signature;
    }
    const acquisitionMessage = document.getElementById("acquisition-message");
    if (acquisitionMessage) acquisitionMessage.textContent = inv.pause_reason || "";
    if (statusEl) {
      statusEl.textContent = inv.status || "";
      statusEl.className = `pill ${inv.status || ""}`;
    }
    if (nowEl && board.now) nowEl.textContent = board.now.text;
    if (tape) {
      for (const ev of board.events || []) {
        if (ev.seq <= lastSeq || seen.has(ev.id)) continue;
        seen.add(ev.id);
        lastSeq = Math.max(lastSeq, ev.seq);
        const li = document.createElement("li");
        const when = document.createElement("span");
        when.className = "when";
        when.textContent = (ev.created_at || "").slice(11, 19);
        const body = document.createElement("span");
        const who = document.createElement("span");
        who.className = "who";
        who.textContent = ev.actor;
        const line = document.createElement("span");
        line.textContent = formatEvent(ev);
        body.append(who, line);
        li.append(when, body);
        tape.appendChild(li);
      }
      tape.scrollTop = tape.scrollHeight;
    }
    const voiceLive = board.live && board.live.voice && board.live.voice.status === "in_progress";
    if (!voiceLive) renderChannel(board);
    renderHil(board);
    renderGraph(board.graph, voiceLive);
    if (board.explanation && !document.querySelector("#explanation .narrative") && !voiceLive) {
      window.location.reload();
      return;
    }
    setTimeout(tick, 1100);
  }
  tick();
  pollVoice();
}

function pollVoice() {
  if (!document.getElementById("channel-card") && !document.getElementById("channel-title")) return;
  let lastSig = "";
  async function tick() {
    try {
      const voice = await fetch("/api/voice/live").then((r) => r.json());
      const live = voice && voice.status === "in_progress";
      const sig = JSON.stringify({
        status: voice && voice.status,
        transcript: voice && voice.transcript,
      });
      if (sig !== lastSig) {
        lastSig = sig;
        renderVoice(voice);
      }
    } catch (_err) {
      /* bridge may be down between calls */
    }
    setTimeout(tick, 350);
  }
  tick();
}

function renderVoice(voice) {
  const title = document.getElementById("channel-title");
  const body = document.getElementById("channel-body");
  const card = document.getElementById("channel-card") || (title && title.closest(".channel-card"));
  if (!title || !body) return;
  const live = voice && voice.status === "in_progress";
  if (card) card.classList.toggle("live", live);
  if (!live) {
    if (title.textContent === "On the line") {
      title.textContent = "Idle";
      body.innerHTML = `<p class="muted">Call ended.</p>`;
    }
    return;
  }
  title.textContent = "On the line";
  const transcript = (voice.transcript || []).filter((turn) => (turn.speaker || "") !== "system");
  if (!transcript.length) {
    body.innerHTML = `<p class="muted">Connecting…</p>`;
    return;
  }
  const wrap = document.createElement("div");
  wrap.className = "dialogue";
  for (const turn of transcript) {
    const bubble = document.createElement("div");
    const role = /caller|cashe|veronica/i.test(turn.speaker || "") ? "caller" : "counterparty";
    bubble.className = `bubble ${role}${turn.partial ? " partial" : ""}`;
    const who = document.createElement("span");
    who.className = "who";
    who.textContent = role === "caller" ? "Cashe" : "Desk";
    const text = document.createElement("span");
    text.textContent = turn.text || "";
    bubble.append(who, text);
    wrap.appendChild(bubble);
  }
  body.innerHTML = "";
  body.appendChild(wrap);
  wrap.scrollTop = wrap.scrollHeight;
}

function renderChannel(board) {
  const title = document.getElementById("channel-title");
  const body = document.getElementById("channel-body");
  const card = document.getElementById("channel-card") || (title && title.closest(".channel-card"));
  if (!title || !body) return;
  const channel = (board.now && board.now.channel) || "";
  const voice = (board.live && board.live.voice) || {};
  const browser = (board.live && board.live.browser) || null;
  if (voice.status === "in_progress") {
    renderVoice(voice);
    return;
  }
  if (channel === "browser") {
    title.textContent = browser && browser.invoice_number ? browser.invoice_number : "Portal walk";
    const steps = (browser && browser.steps) || [];
    if (!steps.length) {
      body.innerHTML = `<p class="muted">${(board.now && board.now.text) || "Opening the portal."}</p>`;
      return;
    }
    const ul = document.createElement("ol");
    ul.className = "steps";
    for (const step of steps) {
      const li = document.createElement("li");
      li.textContent = step.intent || step.result || JSON.stringify(step);
      ul.appendChild(li);
    }
    body.innerHTML = "";
    body.appendChild(ul);
    return;
  }
  if (channel === "human" || (board.investigation && board.investigation.status === "awaiting_human")) {
    title.textContent = "Your verdict";
    body.innerHTML = `<p class="muted">Open packets are below. Cashe will not write the close until you rule.</p>`;
    return;
  }
  title.textContent = channel || "Idle";
  body.innerHTML = `<p class="muted">${(board.now && board.now.text) || "Waiting for a subagent."}</p>`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderHil(board) {
  const root = document.getElementById("hil");
  const packets = document.getElementById("hil-packets");
  if (!root || !packets) return;
  const open = (board.escalations || []).filter((e) => e.status === "open");
  if (!open.length) {
    root.hidden = true;
    packets.innerHTML = "";
    return;
  }
  const reason = document.getElementById("hil-reason");
  if (reason) {
    reason.textContent =
      (board.investigation && board.investigation.pause_reason) ||
      "Cashe will not close until you rule.";
  }
  root.hidden = false;
  packets.innerHTML = open.map(packetMarkup).join("");
}

function packetMarkup(esc) {
  const conflict = esc.kind === "conflict";
  const choices = esc.choices || [];
  const radios = choices
    .map(
      (c, i) => `
      <label class="choice">
        <input type="radio" name="chosen_assertion_id" value="${escapeHtml(c.id)}" ${
          conflict && i === 0 ? "checked" : ""
        }>
        <span>
          <strong>${escapeHtml(c.label)}</strong>
          <em>${escapeHtml(c.authority)} · ${escapeHtml(c.field)}</em>
        </span>
      </label>`
    )
    .join("");
  const decisions = conflict
    ? `<option value="choose_assertion">Use the selected claim</option>
       <option value="request_more_evidence">Need more evidence</option>`
    : `<option value="approve_provisionally">Accept as provisional</option>
       <option value="request_more_evidence">Need a document</option>
       <option value="reject">Reject the claim</option>`;
  return `
    <article class="hil-packet">
      <p class="eyebrow">${escapeHtml(esc.kind)}</p>
      <h3>${escapeHtml(esc.title)}</h3>
      <p>${escapeHtml(esc.likely_interpretation || esc.recommended_action || "")}</p>
      <form class="resolve-form" data-id="${escapeHtml(esc.id)}">
        ${radios ? `<fieldset><legend>What do you believe?</legend>${radios}</fieldset>` : ""}
        <label>Decision
          <select name="decision">${decisions}</select>
        </label>
        <label>Why
          <textarea name="rationale" required placeholder="Your ruling, in one or two sentences."></textarea>
        </label>
        <button type="submit">Record verdict</button>
      </form>
    </article>
  `;
}

function renderGraph(graph, voiceLive) {
  const svg = document.getElementById("graph");
  if (!svg || !graph) return;
  const card = svg.closest(".graph-card");
  const nodes = graph.nodes || [];
  const edges = graph.edges || [];
  if (card) card.classList.toggle("live", Boolean(voiceLive || nodes.some((n) => n.active)));
  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
  const ns = "http://www.w3.org/2000/svg";
  const w = 176;
  const h = 52;
  while (svg.firstChild) svg.removeChild(svg.firstChild);

  for (const edge of edges) {
    const a = byId[edge.from];
    const b = byId[edge.to];
    if (!a || !b) continue;
    const line = document.createElementNS(ns, "path");
    line.setAttribute("d", `M ${a.x} ${a.y} C ${a.x} ${(a.y + b.y) / 2}, ${b.x} ${(a.y + b.y) / 2}, ${b.x} ${b.y}`);
    line.setAttribute("class", `g-edge ${edge.rel || ""}${edge.active ? " active" : ""}`);
    svg.appendChild(line);
  }
  for (const node of nodes) {
    const g = document.createElementNS(ns, "g");
    g.setAttribute("class", `g-node ${node.kind || ""}${node.active ? " active" : ""}`);
    g.setAttribute("transform", `translate(${node.x - w / 2}, ${node.y - h / 2})`);
    const rect = document.createElementNS(ns, "rect");
    rect.setAttribute("width", String(w));
    rect.setAttribute("height", String(h));
    const label = document.createElementNS(ns, "text");
    label.setAttribute("x", "12");
    label.setAttribute("y", "22");
    label.textContent = node.label || "";
    const fact = document.createElementNS(ns, "text");
    fact.setAttribute("class", "kind");
    fact.setAttribute("x", "12");
    fact.setAttribute("y", "40");
    fact.textContent = node.detail || "";
    g.append(rect, label, fact);
    svg.appendChild(g);
  }
}

function formatEvent(ev) {
  const p = ev.payload || {};
  if (ev.event_type === "tool_call") return `${p.tool}`;
  if (ev.event_type === "tool_result") return `${p.tool} ${p.ok ? "ok" : "err"}`;
  if (ev.event_type === "subagent_spawn") return `spawn ${p.role}: ${p.goal || ""}`;
  if (ev.event_type === "subagent_complete") return `${p.role} complete`;
  if (ev.event_type === "escalation") return p.title || "escalation";
  if (ev.event_type === "explanation") return p.headline || "explanation";
  if (ev.event_type === "browser_capture") return `Browser step ${p.step}: ${p.intent}`;
  if (ev.event_type === "browser_completed") return `Browser ${p.status} after ${p.steps_used} actions`;
  if (ev.event_type === "browser_test_started") return `Reading ${p.invoice_number}`;
  if (ev.event_type === "browser_test_finished") return p.message || p.status;
  if (ev.event_type === "llm_message") return (p.text || "").slice(0, 180);
  return ev.event_type;
}

function renderBrowserEvidence(data) {
  const section = document.getElementById("browser-evidence");
  if (!section || !data.artifacts) return;
  section.hidden = !data.artifacts.some(a => a.retrieval_method === "browser");
  const records = document.getElementById("browser-records");
  records.replaceChildren();
  const artifacts = new Map(data.artifacts.map(a => [a.id, a]));
  for (const assertion of data.assertions || []) {
    const row = document.createElement("tr");
    const artifact = artifacts.get(assertion.artifact_id);
    const value = typeof assertion.value === "string" ? assertion.value : JSON.stringify(assertion.value);
    for (const text of [assertion.subject_id, assertion.field, value, artifact?.source_id || assertion.authority, assertion.confidence]) {
      const cell = document.createElement("td");
      cell.textContent = text;
      row.append(cell);
    }
    const cell = document.createElement("td");
    const link = document.createElement("a");
    link.href = `/evidence/${encodeURIComponent(assertion.artifact_id)}`;
    link.textContent = "View source";
    cell.append(link);
    row.append(cell);
    records.append(row);
  }
  const checks = document.getElementById("browser-checks");
  checks.replaceChildren();
  for (const report of data.browser_reports || []) {
    const text = document.createElement("p");
    text.textContent = `${report.status} · ${report.steps_used} browser actions · ` +
      Object.entries(report.checks).map(([name, passed]) => `${name}: ${passed ? "passed" : "failed"}`).join("; ");
    checks.append(text);
    for (const gap of report.remaining_gaps || []) {
      const message = document.createElement("p");
      message.textContent = gap;
      checks.append(message);
    }
  }
  const screenshots = document.getElementById("browser-screenshots");
  screenshots.replaceChildren();
  for (const artifact of data.artifacts.filter(a => a.media_type === "image/png")) {
    const link = document.createElement("a");
    link.href = `/evidence/${encodeURIComponent(artifact.id)}`;
    const img = document.createElement("img");
    img.src = `/api/evidence/${encodeURIComponent(artifact.id)}/content`;
    img.alt = artifact.summary;
    img.loading = "lazy";
    link.append(img);
    screenshots.append(link);
  }
}

const browserTest = document.getElementById("browser-test-form");
if (browserTest) {
  browserTest.addEventListener("submit", async event => {
    event.preventDefault();
    const button = browserTest.querySelector("button");
    const error = document.getElementById("browser-test-error");
    button.disabled = true;
    error.textContent = "";
    try {
      const response = await fetch("/api/browser-investigations", {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({source_id: document.getElementById("browser-source").value,
                             invoice_number: document.getElementById("browser-invoice").value})
      });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Unable to start browser test");
      window.location.href = result.url;
    } catch (reason) {
      error.textContent = reason.message;
      button.disabled = false;
    }
  });
}

const ask = document.getElementById("ask-form");
if (ask) {
  ask.addEventListener("submit", async (e) => {
    e.preventDefault();
    const question = document.getElementById("question").value;
    const res = await fetch("/api/investigations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const data = await res.json();
    window.location.href = `/investigations/${data.id}`;
  });
}

document.addEventListener("submit", async (e) => {
  const form = e.target.closest(".resolve-form");
  if (!form) return;
  e.preventDefault();
  const chosen = form.chosen_assertion_id;
  const body = {
    decision: form.decision.value,
    rationale: form.rationale.value,
    chosen_assertion_id: chosen && chosen.value ? chosen.value : null,
    reviewer: "operator",
    resume: true,
  };
  const btn = form.querySelector("button");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Recording…";
  }
  await fetch(`/api/escalations/${form.dataset.id}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  window.location.reload();
});
