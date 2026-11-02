"use strict";
const data = window.LAB_DATA || {
  runs: [],
  episodes: [],
  metrics: [],
  contrasts: [],
  gates: {},
  inspection: [],
  validity: [],
};
const el = (id) => document.getElementById(id);
const fmt = (x, n = 2) =>
  x === null || x === undefined ? "—" : Number(x).toFixed(n);
const pct = (x) =>
  x === null || x === undefined ? "—" : fmt(x * 100, 1) + "%";
function node(tag, text, cls) {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = String(text);
  if (cls) n.className = cls;
  return n;
}
function table(id, columns, rows) {
  const host = el(id);
  host.replaceChildren();
  if (!rows.length) {
    host.append(node("div", "No completed eligible episodes yet.", "empty"));
    return;
  }
  const t = node("table"),
    head = node("tr"),
    thead = node("thead"),
    body = node("tbody");
  columns.forEach((c) => head.append(node("th", c[0])));
  thead.append(head);
  for (const r of rows) {
    const tr = node("tr");
    columns.forEach((c) =>
      tr.append(
        node("td", typeof c[1] === "function" ? c[1](r) : (r[c[1]] ?? "—")),
      ),
    );
    body.append(tr);
  }
  t.append(thead, body);
  host.append(t);
}
const conditionName = (value) => ({ C1: "C1 · Own choices only", C2: "C2 · Add reward feedback", C3: "C3 · Add moral wording", neutral: "Neutral message", promise: "Promise to cooperate" }[value] || value);
function coreRows(task) {
  return data.episodes.filter(
    (r) =>
      r.run.startsWith("pilot_core") &&
      r.task === task &&
      r.status === "complete" &&
      !r.model.startsWith("script:"),
  );
}
function groups(rows, keys) {
  const m = new Map();
  for (const r of rows) {
    const k = JSON.stringify(keys.map((x) => r[x]));
    if (!m.has(k)) m.set(k, []);
    m.get(k).push(r);
  }
  return [...m.values()];
}
const mean = (rows, k) => rows.reduce((s, r) => s + r[k], 0) / rows.length;
const sum = (rows, k) => rows.reduce((s, r) => s + (r[k] || 0), 0);
function renderProgress(runs, live = false) {
  const pilot = runs.filter((r) => r.name.startsWith("pilot"));
  el("run-progress").replaceChildren();
  for (const r of runs) {
    const done = r.counts.complete || 0;
    const a = node("article");
    a.append(node("h3", r.name.replaceAll("_", " ")));
    const bar = node("div", undefined, "bar");
    const fill = node("div");
    fill.style.width = (100 * done) / r.episodes + "%";
    bar.append(fill);
    a.append(
      bar,
      node("p", `${done} / ${r.episodes} episodes complete`),
      node(
        "p",
        `${r.rounds.toLocaleString()} rounds · ${r.attempts.toLocaleString()} attempts · ${r.counts.invalid || 0} invalid episodes · ${r.counts.incomplete || 0} incomplete`,
        "small",
      ),
    );
    el("run-progress").append(a);
  }
  const completed = pilot.reduce((s, r) => s + (r.counts.complete || 0), 0),
    planned = pilot.reduce((s, r) => s + r.episodes, 0);
  const validity = data.validity.filter(
    (r) => r.run.startsWith("pilot") && !r.model.startsWith("script:"),
  );
  const attempts = sum(validity, "attempted_decisions"),
    valid = sum(validity, "valid_decisions");
  el("kpis").replaceChildren();
  for (const [v, label] of [
    [`${completed}/${planned || 64}`, "original pilot games completed"],
    [attempts.toLocaleString(), "original pilot AI choices"],
    [
      attempts ? pct(valid / attempts) : "—",
      "replies with a legal choice",
    ],
    ["2", "local AI models"],
  ]) {
    const k = node("div", undefined, "kpi");
    k.append(node("strong", v), node("small", label));
    el("kpis").append(k);
  }
  el("refresh-state").textContent = live
    ? "Live status from read-only logs. Figures update only when analysis is rebuilt."
    : "Saved snapshot. Figures and tables reflect the last analysis build.";
}
renderProgress(data.runs);
const stages = [
  ["Engineering tests & agent-assisted reviews", "Verified"],
  ["Local inference smoke and exact replay", "Verified"],
  ["Scripted policy baselines", "Verified"],
  [
    "Real model gameplay pilot",
    data.runs.filter((r) => r.name.startsWith("pilot")).length === 2 &&
    data.runs
      .filter((r) => r.name.startsWith("pilot"))
      .every((r) => r.counts.complete === r.episodes)
      ? "Complete"
      : "Collecting",
  ],
  ["Check strategy detection with known rules and matched histories", "Not run", "Test whether the analysis recognizes programmed strategies, then give models identical histories while changing one factor."],
  ["Run a new study and estimate decision rules", "Not run", "Collect fresh data under a fixed plan, then compare behavioral rules that could explain and predict choices."],
];
for (const [name, status, description] of stages) {
  const r = node("div", undefined, "stage");
  const label = node("div");
  label.append(node("span", name));
  if (description) label.append(node("p", description, "small"));
  r.append(
    label,
    node("span", status, "pill" + (status === "Not run" ? " pending" : "")),
  );
  el("stages").append(r);
}
table(
  "validity",
  [
    ["Model", "model"],
    ["Condition", "condition"],
    [
      "Complete / planned",
      (r) => `${r.completed_episodes}/${r.planned_episodes}`,
    ],
    [
      "Invalid / attempted",
      (r) => `${r.invalid_decisions}/${r.attempted_decisions}`,
    ],
    ["Invalid rate", (r) => pct(r.invalid_decision_rate)],
    ["Transport errors", "transport_errors"],
  ],
  data.validity.filter(
    (r) => r.run.startsWith("pilot") && !r.model.startsWith("script:"),
  ),
);
const pd = groups(coreRows("pd"), ["model", "condition"]).map((rs) => ({
  model: rs[0].model,
  condition: rs[0].condition,
  n: rs.length,
  coop: mean(rs, "cooperation_rate"),
  points: mean(rs, "score"),
  repeat: mean(rs, "repeat_rate"),
})).sort((a, b) => a.model.localeCompare(b.model) || a.condition.localeCompare(b.condition));
table(
  "pd-table",
  [
    ["Model", "model"],
    ["Condition", (r) => conditionName(r.condition)],
    ["Games", "n"],
    ["Cooperative choices / all choices", (r) => `${Math.round(r.coop * r.n * 30)}/${r.n * 30}`],
    ["Cooperation rate", (r) => pct(r.coop)],
  ],
  pd,
);
table(
  "label-table",
  [
    ["Model", "model"],
    ["Condition", "condition"],
    ["Cooperative label", "cooperate_label"],
    ["Games", "episodes"],
    ["Literal A / decisions", (r) => `${r.literal_A_count}/${r.decisions}`],
    ["Cooperation", (r) => pct(r.cooperation_rate)],
  ],
  data.label_diagnostics || [],
);
const transitions = data.metrics.filter(
  (r) =>
    r.run.startsWith("pilot_core") &&
    r.metric.startsWith("cooperate_after_") &&
    !r.model.startsWith("script:"),
);
table(
  "transition-table",
  [
    ["Model", "model"],
    ["Condition", "condition"],
    ["Previous outcome", (r) => r.metric.replace("cooperate_after_", "")],
    ["Cooperate / eligible", (r) => `${r.numerator}/${r.denominator}`],
    ["Probability", (r) => pct(r.value)],
  ],
  transitions,
);
const bandit = groups(coreRows("bandit"), ["model"]).map((rs) => ({
  model: rs[0].model,
  n: rs.length,
  wins: sum(rs, "win"),
  ties: sum(rs, "tie"),
  points: mean(rs, "score"),
  regret: mean(rs, "expected_total_regret"),
  regretPerPull: mean(rs, "mean_regret_per_pull"),
  repeat: mean(rs, "repeat_rate"),
}));
table(
  "bandit-table",
  [
    ["Model", "model"],
    ["Games won / played", (r) => `${r.wins}/${r.n}`],
    ["Ties", "ties"],
    ["Average final points", (r) => fmt(r.points)],
  ],
  bandit,
);
table("bandit-detail-table", [
  ["Model", "model"], ["Expected points forgone / game", (r) => fmt(r.regret)],
  ["Expected points forgone / choice", (r) => fmt(r.regretPerPull)],
  ["Repeated previous port", (r) => pct(r.repeat)],
], bandit);
const banditMeasures = {
  highest_mean_port: "Highest-mean port selected",
  selection_port_A: "Port A selected",
  selection_port_B: "Port B selected",
  selection_port_C: "Port C selected",
  switch_when_ahead: "Switched while ahead",
  switch_when_tied: "Switched while tied",
  switch_when_behind: "Switched while behind",
};
const banditMetrics = groups(
  data.metrics.filter(
    (r) =>
      r.run.startsWith("pilot_core") &&
      r.task === "bandit" &&
      !r.model.startsWith("script:") &&
      Object.hasOwn(banditMeasures, r.metric),
  ),
  ["model", "metric"],
).map((rs) => ({
  model: rs[0].model,
  measure: banditMeasures[rs[0].metric],
  numerator: sum(rs, "numerator"),
  denominator: sum(rs, "denominator"),
}));
table(
  "bandit-metrics",
  [
    ["Model", "model"],
    ["Measure", "measure"],
    ["Count / eligible", (r) => `${r.numerator}/${r.denominator}`],
    [
      "Fraction",
      (r) => pct(r.denominator ? r.numerator / r.denominator : null),
    ],
  ],
  banditMetrics,
);
const stress = groups(
  data.episodes.filter(
    (r) =>
      r.run.startsWith("pilot_stress") &&
      r.status === "complete" &&
      !r.model.startsWith("script:"),
  ),
  ["model", "condition"],
).map((rs) => ({
  model: rs[0].model,
  condition: rs[0].condition,
  n: rs.length,
  coop: mean(rs, "post_switch_cooperation"),
  reward: mean(rs, "post_switch_mean_reward"),
})).sort((a, b) => a.model.localeCompare(b.model) || a.condition.localeCompare(b.condition));
table(
  "messages-table",
  [
    ["Model", "model"],
    ["Messages", (r) => conditionName(r.condition)],
    ["Games", "n"],
    ["Cooperation in rounds 11–30", (r) => pct(r.coop)],
    ["Cooperative choices / all choices", (r) => `${Math.round(r.coop * r.n * 20)}/${r.n * 20}`],
  ],
  stress,
);
const baseline = groups(
  data.episodes.filter(
    (r) =>
      r.run.startsWith("baseline") && r.status === "complete" && r.player === 0,
  ),
  ["task", "model"],
).map((rs) => ({
  task: rs[0].task,
  model: rs[0].model,
  n: rs.length,
  points: mean(rs, "score"),
  wins: sum(rs, "win"),
  regret: rs[0].task === "bandit" ? mean(rs, "expected_total_regret") : null,
  regretPerPull:
    rs[0].task === "bandit" ? mean(rs, "mean_regret_per_pull") : null,
}));
table(
  "baseline-table",
  [
    ["Task", "task"],
    ["Policy", "model"],
    ["Episodes", "n"],
    ["Mean points", (r) => fmt(r.points)],
    ["Wins", "wins"],
    ["Mean total regret / episode", (r) => fmt(r.regret)],
    ["Mean regret / pull", (r) => fmt(r.regretPerPull)],
  ],
  baseline,
);
table(
  "contrast-table",
  [
    ["Model", "model"],
    ["Contrast", "contrast"],
    ["Measure", (r) => r.metric.replaceAll("_", " ")],
    ["Pairs", "paired_blocks"],
    ["Difference", (r) => fmt(r.effect, 3)],
    [
      "Descriptive interval",
      (r) =>
        `${fmt(r.ci_low, 3)} to ${fmt(r.ci_high, 3)}${r.degenerate_bootstrap ? " (degenerate)" : ""}`,
    ],
  ],
  data.contrasts,
);
for (const button of document.querySelectorAll("[data-panel]"))
  button.addEventListener("click", () => {
    document
      .querySelectorAll("[data-panel]")
      .forEach((b) => {
        b.classList.toggle("active", b === button);
        b.setAttribute("aria-pressed", String(b === button));
      });
    document
      .querySelectorAll(".result-panel")
      .forEach((p) => (p.hidden = p.id !== "panel-" + button.dataset.panel));
  });
const select = el("decision-select");
data.inspection.forEach((d, i) => {
  const option = node(
    "option",
    `${d.run} / ${d.episode} / ${d.model} / round ${d.trial}`,
  );
  option.value = String(i);
  select.append(option);
});
function inspect() {
  const d = data.inspection[Number(select.value)];
  if (!d) return;
  el("observation").textContent = JSON.stringify(d.observation, null, 2);
  el("response").textContent =
    `Accepted action: ${d.action ?? "none"}\n\nRaw response:\n${d.raw ?? "no valid response"}`;
  el("prompt").textContent =
    d.prompt + "\n\nSHA-256 snapshot: " + d.snapshot_hash;
}
select.addEventListener("change", inspect);
inspect();
for (const [name, g] of Object.entries(data.gates)) {
  const d = node("div", undefined, "gate");
  d.append(
    node(
      "strong",
      name.replaceAll("_", " ") + " · " + g.status.replaceAll("_", " "),
    ),
  );
  el("gates").append(d);
}
for (const r of data.runs) {
  const a = node("a", r.name + " — trace export", "trace-link");
  a.href = window.PUBLICATION?.static
    ? (window.PUBLICATION.release_url || "#publication-evidence")
    : "../results/" + encodeURIComponent(r.name) + "_trace.json";
  if (!window.PUBLICATION?.static) a.download = "";
  el("trace-links").append(a);
}
function finding(title, bullets) {
  const card = node("article"), list = node("ul");
  bullets.forEach((text) => list.append(node("li", text)));
  card.append(node("h3", title), list);
  el("findings").append(card);
}
finding("Labels affected the interpretation", [
  "Qwen’s near-constant B choice explains most of its 50% cooperation rate.",
  "Reward controls showed strong simple-reward scores, but weak game-table scores.",
]);
finding("Feedback, wording, and messages", [
  "Feedback did not change average cooperation.",
  "Gemma’s moral-wording increase came from one game.",
  "In the revised message study, Qwen’s message difference changed direction across display orders; Gemma always chose the second-listed action.",
]);
finding("Bandit wins were evenly split", [
  "Each model won 6 of 12 games.",
  "Different repetition rates do not identify a learning rule or confidence level.",
]);
finding("Simplification helps, but errors remain", [
  "Relevant-only rewards improved choices, especially for Qwen. Reporting payoffs improved Gemma’s choices but often produced incorrect values.",
  "Current evidence does not establish exploration, exploitation, or a specific policy.",
]);
const liveProgress = !window.PUBLICATION?.static
  && ["127.0.0.1", "localhost"].includes(location.hostname)
  && new URLSearchParams(location.search).get("live") === "1";
async function refresh() {
  if (!liveProgress) return;
  try {
    const response = await fetch("/api/progress", { cache: "no-store" });
    if (response.ok) {
      const live = await response.json();
      renderProgress(live.runs, true);
    }
  } catch {}
}
refresh();
if (liveProgress) setInterval(refresh, 15000);

for (const link of document.querySelectorAll("[data-show-panel]")) {
  link.addEventListener("click", () => {
    document.querySelector(`[data-panel="${link.dataset.showPanel}"]`)?.click();
  });
}
for (const [id, url, label] of [
  ["repository-link", window.PUBLICATION?.repository_url, "View on GitHub"],
  ["release-link", window.PUBLICATION?.release_url, "Download full evidence from releases"],
]) {
  if (url && /^https:\/\//.test(url)) {
    el(id).href = url;
    el(id).textContent = label;
  }
}
