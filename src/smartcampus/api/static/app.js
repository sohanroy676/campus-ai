// Live demo dashboard. All state comes from the API; this file only renders it and sends actions.
"use strict";

const DAY_MIN = 1440;
const OPEN = 8 * 60;
const CLOSE = 18 * 60;
const SPAN = CLOSE - OPEN;
const AGENT_COLORS = {
  "Digital twin": "#6250d6",
  "Maintenance agent": "#e34948",
  "Impact analysis": "#eb6834",
  "Room agents": "#1baf7a",
  "Equipment agent": "#eda100",
  "Coordinator": "#2a78d6",
  "Optimizer (CP-SAT)": "#2a78d6",
  "Rule validator": "#008300",
  "Approval": "#e87ba4",
};

let S = null; // the latest snapshot from the API
const ui = { day: null, selected: null, running: null, busy: false, formScenario: null };

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const hhmm = (min) => {
  const m = ((min % DAY_MIN) + DAY_MIN) % DAY_MIN;
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
};
const dayOf = (min) => Math.floor(min / DAY_MIN);
const dayName = (min) => (S ? S.days[dayOf(min)]?.name ?? "" : "");
const when = (min) => `${dayName(min)} ${hhmm(min)}`;

async function api(path, body) {
  const res = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `${res.status} ${res.statusText}`);
  return data;
}

function toast(message) {
  const el = $("toast");
  el.textContent = message;
  el.classList.remove("hidden");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.add("hidden"), 6000);
}

function setState(next) {
  S = next;
  if (ui.selected && !S.proposals[ui.selected]) ui.selected = null;
  if (ui.formScenario !== S.scenario.id) {
    ui.formScenario = S.scenario.id;
    ui.day = S.focus_day;
    fillIncidentForm();
  }
  if (S.faults.length && ui.day === null) ui.day = S.focus_day;
  render();
}

// ----- incident form ---------------------------------------------------------------------------

function timeOptions(select, day, from, to, chosen) {
  const opts = [];
  for (let m = OPEN; m <= CLOSE; m += 30) {
    const minute = day * DAY_MIN + m;
    if (minute < from || minute > to) continue;
    opts.push(`<option value="${minute}" ${minute === chosen ? "selected" : ""}>${hhmm(minute)}</option>`);
  }
  select.innerHTML = opts.join("");
}

function fillIncidentForm() {
  const sug = S.suggested_incident;
  $("f-room").innerHTML = S.rooms
    .map((r) => `<option value="${esc(r.id)}" ${r.id === sug.room_id ? "selected" : ""}>${esc(r.id)} (${esc(r.type)}, ${r.capacity} seats)</option>`)
    .join("");
  $("f-kind").innerHTML = Object.entries(S.fault_kinds)
    .map(([k, label]) => `<option value="${k}" ${k === sug.kind ? "selected" : ""}>${esc(label)}</option>`)
    .join("");
  const clockDay = dayOf(S.clock.min);
  $("f-day").innerHTML = S.days
    .filter((d) => d.index >= clockDay)
    .map((d) => `<option value="${d.index}" ${d.index === dayOf(sug.start) ? "selected" : ""}>${d.name}</option>`)
    .join("");
  fillIncidentTimes(sug.start, sug.end);
}

function fillIncidentTimes(start, end) {
  const day = Number($("f-day").value);
  const base = day * DAY_MIN;
  const clock = S.clock.min;
  timeOptions($("f-start"), day, Math.max(clock, base + OPEN), base + CLOSE - 30, start);
  const s = Number($("f-start").value);
  timeOptions($("f-end"), day, s + 30, base + CLOSE, end ?? s + 240);
  if (!$("f-end").value && $("f-end").options.length) $("f-end").selectedIndex = $("f-end").options.length - 1;
}

function fillOverrunForm() {
  const fault = S.faults[S.faults.length - 1];
  const form = $("overrun-form");
  if (!fault) {
    form.classList.add("hidden");
    return;
  }
  const day = dayOf(fault.end - 1);
  const latestReport = Math.min(fault.end, day * DAY_MIN + CLOSE - 30);
  timeOptions($("o-at"), day, S.clock.min, latestReport, Number($("o-at").value) || S.clock.min);
  timeOptions($("o-end"), day, fault.end + 30, day * DAY_MIN + CLOSE, Number($("o-end").value) || fault.end + 120);
  const canOverrun = $("o-end").options.length > 0 && $("o-at").options.length > 0;
  form.classList.toggle("hidden", !canOverrun);
}

// ----- rendering -------------------------------------------------------------------------------

function render() {
  $("clock").textContent = `Clock ${S.clock.label}`;
  $("version").textContent = `Log v${S.version}`;
  $("scenario").innerHTML = S.scenarios
    .map((s) => `<option value="${s.id}" ${s.id === S.scenario.id ? "selected" : ""}>${esc(s.title)}</option>`)
    .join("");
  $("scenario-desc").textContent = S.scenario.description;
  $("replan").disabled = ui.busy || !S.impact || !S.impact.affected.length;
  $("inject").disabled = ui.busy;
  renderStepper();
  renderOverview();
  renderIncident();
  renderFeed();
  renderComparison();
  renderUpdated();
  renderMetrics();
}

// The proposals to show: the live ones, or those the last applied plan was chosen from.
function shownRound() {
  if (Object.keys(S.proposals).length || !S.last_round) {
    return { live: true, proposals: S.proposals, recommended: S.recommended, applied: null };
  }
  return { live: false, ...S.last_round };
}

function currentStep() {
  if (ui.running) return 3;
  if (!S.faults.length) return 1;
  if (Object.keys(S.proposals).length) return 4;
  const last = S.events[S.events.length - 1];
  if (last && last.type === "plan_applied") return 5;
  return 2;
}

function renderStepper() {
  const step = currentStep();
  for (const li of $("stepper").children) {
    const n = Number(li.dataset.step);
    li.className = n === step ? "current" : n < step ? "done" : "";
  }
}

function tile(value, label) {
  return `<div class="tile"><div class="v">${esc(value)}</div><div class="k">${esc(label)}</div></div>`;
}

function renderOverview() {
  const labs = S.rooms.filter((r) => r.type === "lab").length;
  const units = S.rooms.reduce((n, r) => n + r.equipment.reduce((k, e) => k + e.units, 0), 0);
  const day = ui.day ?? S.focus_day;
  const today = S.timetable.filter((c) => dayOf(c.start) === day && c.status !== "cancelled").length;
  const down = S.rooms.filter((r) => r.faults.length).length;
  $("tiles").innerHTML = [
    tile(S.buildings.length, "Buildings"),
    tile(S.rooms.length, "Rooms"),
    tile(labs, "Labs"),
    tile(units, "Equipment units"),
    tile(today, `Classes on ${S.days[day].name}`),
    tile(S.rooms.length - down, "Rooms available"),
  ].join("");

  $("rooms").innerHTML = S.rooms
    .map((r) => {
      const eq = r.equipment.map((e) => `${e.units} x ${e.type}`).join(", ") || "no equipment";
      const f = r.faults[r.faults.length - 1];
      const status = f ? `${S.fault_kinds[f.kind] || f.kind}, ${f.label}` : "Available";
      return `<div class="room ${f ? "down" : ""}"><b>${esc(r.id)}</b> <span class="muted">bldg ${esc(r.building)}</span><br>
        ${esc(r.type)} · ${r.capacity} seats${r.step_free ? " · step-free" : ""}<br>${esc(eq)}<br>
        <span class="status">${f ? "⚠ " : "✓ "}${esc(status)}</span></div>`;
    })
    .join("");

  $("day-tabs").innerHTML = S.days
    .map((d) => `<button role="tab" data-day="${d.index}" aria-selected="${d.index === day}">${d.name}</button>`)
    .join("");

  const blocks = S.timetable.map((c) => ({
    room: c.room,
    start: c.start,
    end: c.end,
    text: c.id,
    cls: c.status === "cancelled" ? "cancelled" : c.affected ? "hit" : c.status === "moved" ? "moved" : "",
    tip: classTip(c),
  }));
  timetable($("timetable-now"), day, blocks);
}

function classTip(c, extra) {
  const needs = Object.entries(c.needs || {}).map(([t, n]) => `${n} x ${t}`).join(", ");
  return [
    `${c.id} · ${c.cohort} (${c.size} students)`,
    `${c.room}, ${when(c.start)} to ${hhmm(c.end)}`,
    c.faculty?.length ? `Faculty: ${c.faculty.join(", ")}` : "",
    needs ? `Needs: ${needs}` : "",
    c.status === "moved" ? `Originally ${c.original_room}, ${when(c.original_start)}` : "",
    c.status === "cancelled" ? "Cancelled" : "",
    c.affected ? "Hit by the incident" : "",
    extra || "",
  ].filter(Boolean).join("\n");
}

function timetable(el, day, blocks) {
  const pct = (min) => (((min - day * DAY_MIN - OPEN) / SPAN) * 100).toFixed(3);
  const ticks = [];
  for (let h = 8; h <= 18; h += 1) {
    ticks.push(`<span style="left:${((h * 60 - OPEN) / SPAN) * 100}%">${String(h).padStart(2, "0")}</span>`);
  }
  const byBuilding = new Map();
  for (const r of S.rooms) {
    if (!byBuilding.has(r.building)) byBuilding.set(r.building, []);
    byBuilding.get(r.building).push(r);
  }
  const rows = [];
  for (const [, rooms] of byBuilding) {
    for (const r of rooms) {
      const inside = (s, e) => dayOf(s) === day && e > s;
      const faults = S.faults
        .filter((f) => f.room === r.id && dayOf(f.start) === day)
        .map((f) => {
          const s = Math.max(f.start, day * DAY_MIN + OPEN);
          const e = Math.min(f.end, day * DAY_MIN + CLOSE);
          return `<div class="fault-band" style="left:${pct(s)}%;width:${pct(e) - pct(s)}%" data-tip="${esc(`${S.fault_kinds[f.kind] || f.kind} in ${f.room}\n${f.label}`)}"></div>`;
        })
        .join("");
      const items = blocks
        .filter((b) => b.room === r.id && inside(b.start, b.end))
        .map((b) => `<div class="blk ${b.cls}" style="left:${pct(b.start)}%;width:calc(${pct(b.end) - pct(b.start)}% - 2px)" data-tip="${esc(b.tip)}">${esc(b.text)}</div>`)
        .join("");
      rows.push(`<div class="tt-row"><div class="label">${esc(r.id)}<small>bldg ${esc(r.building)} · ${r.capacity} seats</small></div><div class="lane">${faults}${items}</div></div>`);
    }
  }
  el.innerHTML = `<div class="tt"><div class="tt-hours"><div></div><div class="ticks">${ticks.join("")}</div></div>${rows.join("")}</div>`;
}

function renderIncident() {
  const cards = S.faults
    .map((f) => `<div class="incident-card"><b>⚠ ${esc(S.fault_kinds[f.kind] || f.kind)}</b> in <b>${esc(f.room)}</b><br>${esc(f.label)}<br><span class="muted">${esc(f.id)}</span></div>`)
    .join("");
  $("active-incidents").innerHTML = cards;
  fillOverrunForm();
  if (!S.impact) {
    $("impact").innerHTML = "";
    return;
  }
  const byId = Object.fromEntries(S.timetable.map((c) => [c.id, c]));
  const hit = S.impact.affected
    .map((id) => byId[id])
    .filter(Boolean)
    .map((c) => `<li><b>${esc(c.id)}</b>: ${esc(c.cohort)}, ${c.size} students, ${esc(c.room)} ${esc(when(c.start))}</li>`)
    .join("");
  $("impact").innerHTML = `<div class="impact"><h3>Impact</h3>
    <div>Recovery window: <b>${esc(S.impact.window.label)}</b></div>
    <div>${S.impact.affected.length
      ? `${S.impact.affected.length} class(es) hit, ${S.impact.movable.length} may move to make room.`
      : "No class is hit any more."}</div>
    <ul>${hit || "<li>Nothing left to recover: every class has a valid place.</li>"}</ul></div>`;
}

function renderFeed() {
  const items = S.steps.map((s) => {
    const color = AGENT_COLORS[s.agent] || "#2a78d6";
    return `<li class="${s.level}"><span class="t">${esc(s.at)}</span><div><span class="agent" style="--dot:${color}">${esc(s.agent)}</span><div>${esc(s.text)}</div></div></li>`;
  });
  if (ui.running) {
    const label = S.methods.find((m) => m.id === ui.running)?.label || ui.running;
    items.push(`<li class="running"><span class="t"><span class="spinner"></span></span><div><span class="agent">Coordinator</span><div>${esc(label)} is planning…</div></div></li>`);
  }
  const feed = $("feed");
  const atBottom = feed.scrollHeight - feed.scrollTop - feed.clientHeight < 40;
  // Append only new entries, so earlier ones do not replay their entry animation.
  feed.querySelector("li.running")?.remove();
  const known = feed.children.length;
  if (known > S.steps.length + 1 || feed.dataset.scenario !== S.scenario.id) {
    feed.innerHTML = "";
    feed.dataset.scenario = S.scenario.id;
  }
  feed.insertAdjacentHTML("beforeend", items.slice(feed.children.length).join(""));
  if (atBottom || ui.busy) feed.scrollTop = feed.scrollHeight;
  $("busy").innerHTML = ui.busy ? '<span class="spinner"></span> working' : "";
}

function renderComparison() {
  const round = shownRound();
  const rows = S.methods.map((m) => {
    const p = round.proposals[m.id];
    const best = round.recommended === m.id;
    const name = `${esc(m.label)}${best ? '<span class="badge best">Best</span>' : ""}`;
    if (!p) {
      const status = ui.running === m.id ? '<span class="spinner"></span> planning' : S.impact ? "not run" : "";
      return `<tr data-method="${m.id}"><td>${name}</td><td colspan="8" class="muted">${status}</td></tr>`;
    }
    if (!p.ok) {
      return `<tr data-method="${m.id}"><td>${name}</td><td colspan="8"><span class="badge bad">No plan</span> ${esc(p.reason)}</td></tr>`;
    }
    const v = p.values;
    const approval = p.triggers.length
      ? `<span class="badge warn">Officer</span> <span class="muted small">${esc(p.triggers.join(", ").replaceAll("_", " "))}</span>`
      : '<span class="badge ok">Not needed</span>';
    return `<tr data-method="${m.id}" class="${ui.selected === m.id ? "selected" : ""}">
      <td>${name}</td><td class="num">${v.cancellations}</td><td class="num">${v.people_moved}</td>
      <td class="num">${v.delay}</td><td class="num">${v.cost}</td><td class="num">${p.changed}</td>
      <td class="wrap">${approval}</td><td class="num">${p.seconds.toFixed(2)}${p.limit_hit ? " ⏱" : ""}</td>
      <td>${round.live
        ? `<button class="small apply" data-method="${m.id}" ${ui.busy ? "disabled" : ""}>Apply</button>`
        : round.applied === m.id ? '<span class="badge ok">Applied</span>' : ""}</td></tr>`;
  });
  $("methods").querySelector("tbody").innerHTML = rows.join("");
}

function renderUpdated() {
  const day = ui.day ?? S.focus_day;
  const proposal = ui.selected ? S.proposals[ui.selected] : null;
  const label = $("updated-label");
  if (proposal && proposal.ok) {
    label.textContent = `Preview of ${proposal.label} (not applied yet)`;
    const assigned = proposal.assignments;
    const cancelled = new Set(proposal.cancelled);
    const blocks = [];
    for (const c of S.timetable) {
      if (c.status === "cancelled") continue;
      const a = assigned[c.id];
      const length = c.end - c.start;
      if (cancelled.has(c.id)) {
        blocks.push({ room: c.room, start: c.start, end: c.end, text: c.id, cls: "cancelled", tip: classTip(c, "Cancelled by this plan") });
      } else if (a && (a.room !== c.room || a.start !== c.start)) {
        blocks.push({ room: c.room, start: c.start, end: c.end, text: c.id, cls: "ghost", tip: `${c.id} was here` });
        const moved = { ...c, room: a.room, start: a.start, end: a.start + length };
        blocks.push({ room: a.room, start: a.start, end: a.start + length, text: `${c.id} ←`, cls: "moved", tip: classTip(moved, `Moved from ${c.room}, ${when(c.start)}`) });
      } else {
        blocks.push({ room: c.room, start: c.start, end: c.end, text: c.id, cls: "", tip: classTip(c) });
      }
    }
    timetable($("timetable-after"), day, blocks);
    $("changes").innerHTML = changesTable(proposal.changes.filter((c) => c.changed), proposal.moves);
    return;
  }
  if (S.applied.length) {
    const last = S.applied[S.applied.length - 1];
    label.textContent = `After the ${last.label} plan (event ${last.version})`;
    const blocks = [];
    for (const c of S.timetable) {
      if (c.status === "moved") {
        blocks.push({ room: c.original_room, start: c.original_start, end: c.original_start + (c.end - c.start), text: c.id, cls: "ghost", tip: `${c.id} was here` });
      }
      blocks.push({ room: c.room, start: c.start, end: c.end, text: c.status === "moved" ? `${c.id} ←` : c.id, cls: c.status === "moved" ? "moved" : c.status === "cancelled" ? "cancelled" : c.affected ? "hit" : "", tip: classTip(c) });
    }
    timetable($("timetable-after"), day, blocks);
    const changed = S.timetable
      .filter((c) => c.status !== "unchanged")
      .map((c) => ({
        activity: c.id, cohort: c.cohort, size: c.size,
        before: { room: c.original_room, label: when(c.original_start) },
        after: c.status === "cancelled" ? null : { room: c.room, label: when(c.start) },
      }));
    const loans = S.loans.map((l) => ({ pool_id: l.pool, units: l.units, activity_id: l.activity, label: l.label }));
    $("changes").innerHTML = changesTable(changed, loans);
    return;
  }
  label.textContent = "";
  $("timetable-after").innerHTML = '<p class="muted">Inject an incident, let the agents plan, then click a row in Solution Comparison to preview it here. Apply it to update the digital campus.</p>';
  $("changes").innerHTML = "";
}

function changesTable(changes, moves) {
  if (!changes.length && !moves.length) return '<p class="muted">No class changes.</p>';
  const rows = changes.map((c) => `<tr><td><b>${esc(c.activity)}</b></td><td>${esc(c.cohort)} (${c.size})</td>
    <td>${esc(c.before.room)} ${esc(c.before.label)}</td>
    <td>${c.after ? `→ <b>${esc(c.after.room)} ${esc(c.after.label)}</b>` : '<span class="badge bad">Cancelled</span>'}</td></tr>`);
  const mv = moves.map((m) => `<tr><td>Equipment</td><td>${m.units} x ${esc(m.pool_id)}</td><td colspan="2">to ${esc(m.activity_id)}, carried ${esc(m.label || `${when(m.start_min)} to ${hhmm(m.end_min)}`)}</td></tr>`);
  return `<table><thead><tr><th>Class</th><th>Cohort</th><th>Before</th><th>After</th></tr></thead><tbody>${rows.join("")}${mv.join("")}</tbody></table>`;
}

function barChart(title, entries, fmt) {
  if (!entries.length) return "";
  const max = Math.max(...entries.map((e) => e.value), 1);
  const rows = entries
    .map((e) => `<div class="bar-row ${e.best ? "best" : ""}" data-tip="${esc(`${e.label}: ${fmt(e.value)}`)}"><span class="name">${esc(e.label)}</span>
      <span class="track"><div class="bar" style="width:${(e.value / max) * 100}%"></div></span><span class="val">${esc(fmt(e.value))}</span></div>`)
    .join("");
  return `<div class="chart"><div class="title">${esc(title)}</div>${rows}</div>`;
}

function renderMetrics() {
  const round = shownRound();
  const done = S.methods.map((m) => round.proposals[m.id]).filter((p) => p && p.ok);
  const greedy = round.proposals.greedy;
  const best = round.recommended ? round.proposals[round.recommended] : null;
  let saving = "–";
  if (greedy?.ok && best?.ok && greedy.values.people_moved > 0) {
    const pct = Math.round((1 - best.values.people_moved / greedy.values.people_moved) * 100);
    saving = `${pct}%`;
  }
  const hit = S.impact ? S.impact.affected.length : 0;
  $("metric-tiles").innerHTML = [
    tile(S.faults.length, "Incidents"),
    tile(hit, "Classes still hit"),
    tile(done.length, "Plans built"),
    tile(S.applied.length, "Plans applied"),
    tile(done.length ? "0" : "–", "Rule violations"),
    tile(saving, "Fewer people moved than greedy"),
  ].join("");
  const entries = (key, f) => done.map((p) => ({ label: p.label, value: f(p), best: p.method === round.recommended }));
  $("charts").innerHTML = done.length
    ? barChart("People moved (lower is better)", entries("p", (p) => p.values.people_moved), String) +
      barChart("Classes cancelled", entries("c", (p) => p.values.cancellations), String) +
      barChart("Delay, minutes", entries("d", (p) => p.values.delay), String) +
      barChart("Planning time, seconds", entries("t", (p) => p.seconds), (v) => v.toFixed(2))
    : '<p class="muted">Charts appear once the planners have run.</p>';
  $("events").innerHTML = S.events.length
    ? S.events.map((e) => `<li><b>v${e.version}</b> ${esc(e.at)}: ${esc(e.summary)}</li>`).join("")
    : '<li class="muted">Empty: the campus runs as timetabled.</li>';
}

// ----- actions ---------------------------------------------------------------------------------

async function guarded(fn) {
  if (ui.busy) return;
  ui.busy = true;
  render();
  try {
    await fn();
  } catch (err) {
    toast(err.message);
  } finally {
    ui.busy = false;
    ui.running = null;
    render();
  }
}

async function runPlanners() {
  for (const m of S.methods) {
    ui.running = m.id;
    render();
    const res = await api(`/api/plan/${m.id}`, {});
    setState(res.state);
  }
  ui.running = null;
  ui.selected = S.recommended;
}

$("fault-form").addEventListener("submit", (ev) => {
  ev.preventDefault();
  guarded(async () => {
    const body = {
      room_id: $("f-room").value,
      kind: $("f-kind").value,
      start_min: Number($("f-start").value),
      end_min: Number($("f-end").value),
    };
    const res = await api("/api/incident", body);
    ui.day = dayOf(body.start_min);
    ui.selected = null;
    setState(res.state);
    if ($("auto-plan").checked) await runPlanners();
  });
});

$("overrun-form").addEventListener("submit", (ev) => {
  ev.preventDefault();
  guarded(async () => {
    const fault = S.faults[S.faults.length - 1];
    const res = await api("/api/overrun", {
      fault_id: fault.id,
      new_end_min: Number($("o-end").value),
      reported_min: Number($("o-at").value),
    });
    ui.selected = null;
    setState(res.state);
    if ($("auto-plan").checked) await runPlanners();
  });
});

$("f-day").addEventListener("change", () => fillIncidentTimes());
$("f-start").addEventListener("change", () => fillIncidentTimes(Number($("f-start").value)));
$("replan").addEventListener("click", () => guarded(runPlanners));
$("reset").addEventListener("click", () =>
  guarded(async () => {
    ui.formScenario = null;
    ui.selected = null;
    setState((await api("/api/reset", { scenario: S.scenario.id })).state);
  }),
);
$("scenario").addEventListener("change", (ev) =>
  guarded(async () => {
    ui.formScenario = null;
    ui.selected = null;
    setState((await api("/api/reset", { scenario: ev.target.value })).state);
  }),
);
$("day-tabs").addEventListener("click", (ev) => {
  const b = ev.target.closest("button[data-day]");
  if (!b) return;
  ui.day = Number(b.dataset.day);
  render();
});
$("methods").addEventListener("click", (ev) => {
  const apply = ev.target.closest("button.apply");
  if (apply) {
    guarded(async () => {
      const res = await api(`/api/apply/${apply.dataset.method}`, {});
      ui.selected = null;
      setState(res.state);
    });
    return;
  }
  const row = ev.target.closest("tr[data-method]");
  if (row && S.proposals[row.dataset.method]?.ok) {
    ui.selected = ui.selected === row.dataset.method ? null : row.dataset.method;
    render();
  }
});

// Tooltips for timetable blocks, fault bands and bars.
const tip = $("tooltip");
document.addEventListener("mousemove", (ev) => {
  const t = ev.target.closest("[data-tip]");
  if (!t) {
    tip.classList.add("hidden");
    return;
  }
  tip.textContent = t.dataset.tip;
  tip.classList.remove("hidden");
  const x = Math.min(ev.clientX + 12, window.innerWidth - tip.offsetWidth - 8);
  const y = Math.min(ev.clientY + 14, window.innerHeight - tip.offsetHeight - 8);
  tip.style.left = `${x}px`;
  tip.style.top = `${y}px`;
});

api("/api/state").then(setState).catch((err) => toast(err.message));
