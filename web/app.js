/* CRUCIBLE — the desk.
   Steps arrive from the server as they happen and are rendered on a slow drip,
   so a shift reads at the pace a person can follow rather than appearing all at
   once. For a baseline that finishes in a millisecond this is a replay; for a
   model run the steps genuinely arrive this slowly. */

const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const pct = (x) => Math.round(x * 100) + "%";
const prose = (t) => String(t || "").trim().split(/\n\s*\n/)
  .map((p) => `<p>${esc(p.replace(/\n/g, " "))}</p>`).join("");

const S = {
  meta: null, agent: "oracle", split: "public", family: null,
  task: null, brief: null, job: null, poll: null,
  queue: [], shown: 0, ticker: null, finished: false, suite: false,
};

/* ------------------------------------------------------------------ boot */

async function boot() {
  S.meta = await (await fetch("/api/meta")).json();
  renderAgents();
  renderFilters();
  renderTaskList();
  renderTaskGrid();
  loadBoard();

  $("#views").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-view]");
    if (b) showView(b.dataset.view);
  });
  $("#run").addEventListener("click", () => startRun([S.task]));
  $("#runall").addEventListener("click", () => startRun(null));

  const open = tasks().find((t) => t.id === "T-102") || tasks()[0];
  if (open) await selectTask(open.id);
  $("#run").disabled = false;
  $("#runall").disabled = false;
}

const tasks = () => (S.meta.tasks[S.split] || []).slice().sort((a, b) => a.id.localeCompare(b.id));

function showView(v) {
  document.querySelectorAll(".view").forEach((s) => s.classList.toggle("on", s.id === "view-" + v));
  document.querySelectorAll("#views button").forEach((b) => b.setAttribute("aria-current", String(b.dataset.view === v)));
  if (v === "board") loadBoard();
}

/* --------------------------------------------------------------- railing */

function renderAgents() {
  $("#agents").innerHTML = S.meta.agents.map((a) => `
    <button class="agent" data-id="${a.id}" data-kind="${a.kind}" aria-pressed="${a.id === S.agent}">
      <span class="an"><i class="dot"></i>${esc(a.label)}</span>
      <span class="ab">${esc(a.blurb)}</span>
    </button>`).join("");
  $("#agents").addEventListener("click", (e) => {
    const b = e.target.closest(".agent");
    if (!b) return;
    S.agent = b.dataset.id;
    document.querySelectorAll(".agent").forEach((x) => x.setAttribute("aria-pressed", String(x.dataset.id === S.agent)));
    updateRunLabel();
  });
}

function renderFilters() {
  const html = ["all", ...S.meta.families].map((f) => `
    <button data-fam="${f}" aria-pressed="${(f === "all") === (S.family === null) && (f === "all" || f === S.family)}">${f}</button>`).join("");
  for (const id of ["#filters", "#filters2"]) {
    const el = $(id);
    el.innerHTML = html;
    el.addEventListener("click", (e) => {
      const b = e.target.closest("button[data-fam]");
      if (!b) return;
      S.family = b.dataset.fam === "all" ? null : b.dataset.fam;
      document.querySelectorAll("[data-fam]").forEach((x) =>
        x.setAttribute("aria-pressed", String((x.dataset.fam === "all" && !S.family) || x.dataset.fam === S.family)));
      renderTaskList(); renderTaskGrid();
    });
  }
}

const visible = () => tasks().filter((t) => !S.family || t.family === S.family);

function renderTaskList() {
  $("#tasklist").innerHTML = visible().map((t) => `
    <button class="titem" data-id="${t.id}" aria-current="${t.id === S.task}">
      <span class="tid">${esc(t.id)}</span>
      <span><span class="tt">${esc(t.title)}</span>
        <span class="tm">${esc(t.difficulty)} · ${t.n_checks} checks · ${t.n_critical} critical</span></span>
    </button>`).join("");
  $("#tasklist").onclick = (e) => {
    const b = e.target.closest(".titem");
    if (b) selectTask(b.dataset.id);
  };
}

function renderTaskGrid() {
  $("#taskgrid").innerHTML = visible().map((t) => `
    <button class="card" data-id="${t.id}">
      <span class="top"><span class="cid">${esc(t.id)}</span><span class="diff">${esc(t.difficulty)}</span></span>
      <h4>${esc(t.title)}</h4>
      <span class="meta"><span>${esc(t.family)}</span><span>${t.n_checks} checks</span><span>${t.n_critical} critical</span></span>
    </button>`).join("");
  $("#taskgrid").onclick = (e) => {
    const b = e.target.closest(".card");
    if (b) { selectTask(b.dataset.id); showView("desk"); window.scrollTo(0, 0); }
  };
}

/* ------------------------------------------------------------------ task */

async function selectTask(id) {
  S.task = id;
  document.querySelectorAll(".titem").forEach((x) => x.setAttribute("aria-current", String(x.dataset.id === id)));
  S.brief = await (await fetch("/api/task/" + id)).json();
  const b = S.brief;

  $("#crumbs").innerHTML = `${esc(b.id)} &nbsp;·&nbsp; <b>${esc(b.family)}</b> &nbsp;·&nbsp; ${esc(b.difficulty)}`;
  $("#title").textContent = b.title;
  $("#subtitle").textContent = b.prompt;

  $("#inbox").innerHTML = b.inbox.map((m) => `
    <article class="paper">
      <div class="from"><span>from ${esc(m.from)}</span><span>${esc(m.channel)} · ${esc(m.id)}</span></div>
      <div class="subj">${esc(m.subject)}</div>
      <div class="body">${prose(m.body)}</div>
    </article>`).join("") || `<div class="panel"><div class="pad tagline">Nothing in the inbox.</div></div>`;

  const rows = [];
  if (b.leads.length) rows.push(["Customers on file", b.leads.map((l) => `${l.name} · ${l.zip} · ${l.status}`).join("<br>")]);
  if (b.appointments.length) rows.push(["Booked", b.appointments.map((a) => `${a.date} ${a.time} · ${a.tech}`).join("<br>")]);
  if (b.ledger.length) rows.push(["Charges", b.ledger.map((t) => `${t.id} · $${t.amount.toFixed(2)} · ${String(t.at).slice(0, 10)}`).join("<br>")]);
  if (b.suppression.length) rows.push(["Do not contact", b.suppression.join("<br>")]);
  $("#worldpanel").hidden = !rows.length;
  $("#world").innerHTML = `<dl class="kv">${rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${v}</dd>`).join("")}</dl>`;

  const crit = b.checks.filter((c) => c.critical).length;
  $("#ncrit").textContent = `${b.checks.length} checks · ${crit} critical`;
  $("#checkchips").innerHTML = b.checks.map((c) =>
    `<span class="chip ${c.critical ? "crit" : ""}">${esc(c.desc)}</span>`).join("");

  resetShift();
  updateRunLabel();
}

function updateRunLabel() {
  const a = S.meta.agents.find((x) => x.id === S.agent);
  $("#run").textContent = a && !a.instant ? `Run ${a.label} on this shift` : "Run this shift";
  $("#runall").textContent = `Run all ${tasks().length}`;
}

/* ------------------------------------------------------------------- run */

function resetShift() {
  clearInterval(S.ticker); S.ticker = null;
  S.queue = []; S.shown = 0; S.finished = false;
  $("#log").innerHTML = "";
  $("#verdict").classList.remove("on");
  $("#verdict").innerHTML = "";
  $("#clock").innerHTML = "+0<i>m</i>";
  $("#acts").textContent = "0";
  $("#score").textContent = "—";
}

async function startRun(taskIds) {
  S.suite = !taskIds;
  resetShift();
  $("#run").disabled = true; $("#runall").disabled = true;
  $("#suite").classList.toggle("on", S.suite);
  $("#brief").hidden = S.suite;
  $("#tally").hidden = !S.suite;
  $("#tally-rows").innerHTML = "";
  $("#tally-count").textContent = "";
  S.tallied = 0;

  const res = await fetch("/api/run", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ agent: S.agent, split: S.split, tasks: taskIds }),
  });
  const out = await res.json();
  if (out.error) { alert(out.error); $("#run").disabled = false; $("#runall").disabled = false; return; }
  S.job = out.job;
  S.poll = setInterval(pollJob, 320);
  pollJob();
}

async function pollJob() {
  const j = await (await fetch("/api/job/" + S.job)).json();

  if (S.suite) {
    $("#suite-txt").textContent = `${j.done} of ${j.total} · ${j.status === "done" ? "finished" : "working " + (j.current || "")}`;
    $("#suite-bar").style.width = (j.done / j.total * 100) + "%";
    if (j.current && j.current !== S.task) selectTaskQuiet(j.current);
  }

  if (S.suite) renderTally(j);
  pushSteps(j.live_steps || []);

  if (j.status === "done" || j.status === "error") {
    clearInterval(S.poll);
    $("#run").disabled = false; $("#runall").disabled = false;
    if (j.status === "error") { $("#log").innerHTML += `<div class="ev bad"><span class="t"></span><span class="c"><span class="err">${esc(j.error)}</span></span></div>`; return; }
    S.finished = true;
    S.lastEpisode = j.episodes[j.episodes.length - 1];
    if (S.suite) { loadBoard(); suiteVerdict(j); return; }
    maybeVerdict();
  }
}

function renderTally(j) {
  for (let i = S.tallied; i < j.episodes.length; i++) {
    const ep = j.episodes[i], g = ep.grade;
    const word = g.passed ? "pass" : (g.safe ? "partial" : "unsafe");
    const label = g.passed ? "pass" : (g.safe ? "incomplete" : "unsafe");
    const row = document.createElement("div");
    row.className = "trow";
    row.innerHTML = `<span class="tid">${esc(ep.task.id)}</span>
      <span class="tt">${esc(ep.task.title)}</span>
      <span class="tv ${word}">${label}</span>`;
    $("#tally-rows").appendChild(row);
  }
  S.tallied = j.episodes.length;
  const p = j.episodes.filter((e) => e.grade.passed).length;
  const u = j.episodes.filter((e) => !e.grade.safe).length;
  $("#tally-count").textContent = `${p} passed · ${u} unsafe · ${j.done} of ${j.total}`;
}

function selectTaskQuiet(id) {
  S.task = id;
  document.querySelectorAll(".titem").forEach((x) => x.setAttribute("aria-current", String(x.dataset.id === id)));
  const t = tasks().find((x) => x.id === id);
  if (t) { $("#title").textContent = t.title; $("#crumbs").innerHTML = `${esc(t.id)} &nbsp;·&nbsp; <b>${esc(t.family)}</b> &nbsp;·&nbsp; ${esc(t.difficulty)}`; }
  $("#log").innerHTML = ""; S.shown = 0; S.queue = [];
}

function pushSteps(steps) {
  for (let i = S.shown + S.queue.length; i < steps.length; i++) S.queue.push(steps[i]);
  if (!S.ticker) S.ticker = setInterval(drip, 75);
}

function drip() {
  const ev = S.queue.shift();
  if (!ev) {
    clearInterval(S.ticker); S.ticker = null;
    maybeVerdict();
    return;
  }
  S.shown++;
  const args = Object.entries(ev.args || {})
    .map(([k, v]) => `<b>${esc(k)}</b> ${esc(String(v).slice(0, 58))}`).join("&nbsp; ");
  const cls = !ev.ok ? "ev bad" : (ev.tool === "done" ? "ev fin" : "ev");
  const el = document.createElement("div");
  el.className = cls;
  el.innerHTML = `<span class="t">+${ev.elapsed_min}m</span><span class="c">
      <span class="tool">${esc(ev.tool)}</span> <span class="args">${args}</span>
      ${ev.error ? `<div class="err">${esc(ev.error)}</div>` : ""}</span>`;
  const log = $("#log");
  log.appendChild(el);
  log.scrollTop = log.scrollHeight;
  $("#clock").innerHTML = `+${ev.elapsed_min}<i>m</i>`;
  $("#acts").textContent = S.shown;
}

/* --------------------------------------------------------------- verdict */

function maybeVerdict() {
  if (!S.finished || S.queue.length || !S.lastEpisode) return;
  const ep = S.lastEpisode, g = ep.grade;
  const word = g.passed ? "pass" : (g.safe ? "partial" : "unsafe");
  const label = g.passed ? "Pass" : (g.safe ? "Safe but incomplete" : "Unsafe");
  const okN = g.n_checks - g.n_failed;
  $("#score").textContent = `${okN}/${g.n_checks}`;

  const checks = g.checks.map((c, i) => `
    <div class="check ${c.passed ? "ok" : "no"}" style="animation-delay:${i * 45}ms">
      <span class="m">${c.passed ? "✓" : "✕"}</span>
      <span><span class="d">${esc(c.desc)}</span>
        ${c.critical ? ' <span class="flag">hard rule</span>' : ""}
        <div class="why">${esc(c.detail)}</div></span>
    </div>`).join("");

  const sent = (ep.outbox || []).map((m) => `
    <div class="sent"><div class="to">to ${esc(m.to)} · sent at +${m.elapsed_min}m</div>
    <div class="txt">${prose(m.body)}</div></div>`).join("");

  $("#verdict").innerHTML = `
    <div class="vhead">
      <span class="vword ${word}">${label}</span>
      <span class="vsub">${okN} of ${g.n_checks} checks · ${ep.steps} actions ·
        ${ep.elapsed_min_in_world} minutes of shift · world ${esc(ep.fingerprint)}</span>
    </div>
    ${checks}
    ${sent ? `<div class="label" style="margin-top:24px">What the customer received</div>${sent}` : ""}`;
  $("#verdict").classList.add("on");
}

function suiteVerdict(j) {
  const s = j.summary;
  if (!s) return;
  $("#verdict").innerHTML = `
    <div class="vhead"><span class="vword ${s.pass_rate >= .8 ? "pass" : s.safety_rate === 1 ? "partial" : "unsafe"}">
      ${pct(s.pass_rate)} pass</span>
      <span class="vsub">${pct(s.safety_rate)} safety · ${pct(s.partial_credit)} partial ·
      ${s.n_tasks} tasks · ${s.avg_steps.toFixed(1)} actions each${
        s.agent_stats ? ` · $${s.agent_stats.cost_usd.toFixed(2)}` : ""}</span></div>
    ${(s.top_failures || []).length ? `<div class="label" style="margin-top:8px">What it got wrong most often</div>
      ${s.top_failures.map(([d, n]) => `<div class="check no"><span class="m">${n}&times;</span>
        <span><span class="d">${esc(d)}</span></span></div>`).join("")}` : ""}`;
  $("#verdict").classList.add("on");
}

/* ----------------------------------------------------------------- board */

async function loadBoard() {
  const { runs } = await (await fetch("/api/board")).json();
  if (!runs.length) {
    $("#board").innerHTML = `<div class="empty">No full runs yet. Pick an agent and press
      <b>Run all 30</b> on the desk — the baselines finish in about a second.</div>`;
    return;
  }
  const fams = S.meta.families;
  const spread = (r) => r.n_runs > 1 ? `<span class="sp">${pct(r.pass_min)}–${pct(r.pass_max)}</span>` : "";
  $("#board").innerHTML = `<table>
    <thead><tr><th>Agent</th><th>Pass</th><th>Safety</th><th>Partial</th><th>Steps</th><th>Cost</th>
      ${fams.map((f) => `<th>${f}</th>`).join("")}</tr></thead>
    <tbody>${runs.map((r) => `
      <tr class="${r.note ? "baseline" : ""}">
        <td class="who"><b>${esc(r.agent)}</b><span>${r.note ? esc(r.note) + " · " : ""}${
          r.n_runs} run${r.n_runs > 1 ? "s" : ""} × ${r.n_tasks} tasks${
          r.crashed ? ` · ${r.crashed} crashed` : ""}</span></td>
        <td><span class="num pass">${pct(r.pass_rate)}</span>${spread(r)}</td>
        <td><span class="num ${r.safety_rate < 0.95 ? "warn" : "safe"}">${pct(r.safety_rate)}</span></td>
        <td>${pct(r.partial_credit)}</td>
        <td>${r.avg_steps.toFixed(1)}</td>
        <td>${r.cost_usd ? "$" + r.cost_usd.toFixed(2) : "—"}</td>
        ${fams.map((f) => {
          const b = r.by_family[f];
          if (!b) return "<td>—</td>";
          return `<td class="fam">${pct(b.pass_rate)}<u><i style="width:${b.pass_rate * 100}%"></i></u></td>`;
        }).join("")}
      </tr>`).join("")}</tbody></table>`;
}

boot();
