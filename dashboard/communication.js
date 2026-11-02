"use strict";
(() => {
  const report = window.COMMUNICATION_DATA;
  if (!report) return;
  const labels = {before: "Before · rounds 1–10", first_defection: "First defection · round 11", after_evidence: "After evidence · rounds 12–30"};
  const rows = [];
  for (const model of [...new Set(report.summary.map(r => r.model))].sort()) {
    for (const [window, label] of Object.entries(labels)) {
      const find = condition => report.summary.find(r => r.model === model && r.condition === condition && r.window === window && r.order === "all");
      const neutral = find("neutral"), promise = find("promise");
      rows.push({model, window: label, neutral, promise,
        gap: neutral.rate === null || promise.rate === null ? null : 100 * (promise.rate - neutral.rate)});
    }
  }
  const rateCount = r => `${pct(r.rate)} (${r.cooperative}/${r.observed})`;
  table("communication-summary", [
    ["Model", "model"], ["Period", "window"], ["Neutral", r => rateCount(r.neutral)],
    ["Promise", r => rateCount(r.promise)], ["Promise − neutral", r => fmt(r.gap, 1) + " pp"],
  ], rows);
  table("communication-contrasts", [
    ["Model", "model"], ["Matched pairs", r => `${r.included_pairs}/${r.planned_pairs}`],
    ["Gap before", r => fmt(r.pre_gap_pp,1)+" pp"], ["Gap after", r => fmt(r.post_gap_pp,1)+" pp"],
    ["Change in gap", r => fmt(r.change_pp,1)+" pp"],
  ], report.contrasts.filter(r => r.order === "all"));
  table("communication-order", [
    ["Model", "model"], ["Display order", "order"], ["Pairs", r => `${r.included_pairs}/${r.planned_pairs}`],
    ["Gap before", r => fmt(r.pre_gap_pp,1)+" pp"], ["Gap after", r => fmt(r.post_gap_pp,1)+" pp"],
    ["Change", r => fmt(r.change_pp,1)+" pp"],
  ], report.contrasts.filter(r => r.order !== "all"));
  for (const [id, order] of [["communication-cooperate-counts", "cooperate / defect"], ["communication-defect-counts", "defect / cooperate"]]) {
    const orderRows = [];
    for (const model of ["qwen3:4b", "gemma3:4b"]) {
      for (const [window, label] of Object.entries(labels)) {
        const find = condition => report.summary.find(r => r.model === model && r.order === order && r.condition === condition && r.window === window);
        orderRows.push({model, window: label, neutral: find("neutral"), promise: find("promise")});
      }
    }
    table(id, [["Model", "model"], ["Period", "window"], ["Neutral", r => rateCount(r.neutral)], ["Promise", r => rateCount(r.promise)]], orderRows);
  }
  const c = report.counts;
  el("communication-status").textContent = `${c.complete_games}/${c.planned_games} games complete · ${c.scored_model_decisions}/${c.planned_model_decisions} model choices scored · Separate from the original pilot.`;
  const stage = node("div", undefined, "stage");
  stage.append(node("span", "Revised communication study: cooperate / defect and before / after"), node("span", c.complete_games === c.planned_games ? "Complete" : "Incomplete", "pill"));
  el("stages").insertBefore(stage, el("stages").children[5] || null);
})();
