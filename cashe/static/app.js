async function pollInvestigation(runId) {
  const tape = document.getElementById("tape");
  const statusEl = document.getElementById("status");
  let after = 0;
  const seen = new Set();

  async function tick() {
    const res = await fetch(`/api/investigations/${runId}/events?after=${after}`);
    const data = await res.json();
    for (const ev of data.events) {
      after = Math.max(after, ev.seq);
      if (seen.has(ev.id)) continue;
      seen.add(ev.id);
      const li = document.createElement("li");
      const when = document.createElement("span");
      when.className = "when";
      when.textContent = ev.created_at.slice(11, 19);
      const actor = document.createElement("span");
      actor.textContent = ev.actor;
      const body = document.createElement("span");
      body.textContent = formatEvent(ev);
      li.append(when, actor, body);
      tape.appendChild(li);
    }
    const inv = await fetch(`/api/investigations/${runId}`).then((r) => r.json());
    if (statusEl) {
      statusEl.textContent = inv.status;
      statusEl.className = `pill ${inv.status}`;
    }
    if (inv.status === "completed" && inv.explanation && !document.querySelector(".narrative")) {
      window.location.reload();
      return;
    }
    if (inv.status !== "completed" && inv.status !== "failed") {
      setTimeout(tick, 1200);
    }
  }
  tick();
}

function formatEvent(ev) {
  const p = ev.payload || {};
  if (ev.event_type === "tool_call") return `${p.tool}`;
  if (ev.event_type === "tool_result") return `${p.tool} ${p.ok ? "ok" : "err"}`;
  if (ev.event_type === "subagent_spawn") return `spawn ${p.role}: ${p.goal || ""}`;
  if (ev.event_type === "subagent_complete") return `${p.role} complete`;
  if (ev.event_type === "escalation") return p.title || "escalation";
  if (ev.event_type === "explanation") return p.headline || "explanation";
  if (ev.event_type === "llm_message") return (p.text || "").slice(0, 180);
  return ev.event_type;
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

document.querySelectorAll(".resolve-form").forEach((form) => {
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = form.dataset.id;
    const body = {
      decision: form.decision.value,
      rationale: form.rationale.value,
      chosen_assertion_id: form.chosen_assertion_id.value || null,
      reviewer: "operator",
      resume: true,
    };
    await fetch(`/api/escalations/${id}/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    window.location.reload();
  });
});
