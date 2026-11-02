"use strict";
(() => {
  const report = window.DIAGNOSTIC_DATA;
  if (!report) return;
  const names = {full_direct: "Full information", relevant_direct: "Relevant rewards only", full_extract_choose: "Report payoffs + choose"};
  const model = r => r.model === "qwen3:4b" ? "Qwen" : "Gemma";
  const main = report.summaries.filter(r => r.group_by === "model+condition");
  const fraction = (a, b) => b ? `${a}/${b}` : "— (no eligible responses)";
  const score = r => `${r.correct}/${r.planned} (${fmt(100*r.accuracy_planned, 2)}%)`;
  const models = [...new Set(main.map(r => r.model))].map(model => ({model}));
  table("diagnostic-summary", [["Model", model], ...Object.entries(names).map(([condition, name]) =>
    [name, r => score(main.find(s => s.model === r.model && s.condition === condition))])], models);
  table("diagnostic-extraction", [["Model", model], ["A payoff correct", r => `${r.points_A_correct}/${r.planned}`],
    ["B payoff correct", r => `${r.points_B_correct}/${r.planned}`], ["Both correct", r => `${r.extraction_exact}/${r.planned}`],
    ["Choice correct when both payoffs correct", r => fraction(r.exact_extraction_correct_choice, r.extraction_exact)]],
    main.filter(r => r.condition === "full_extract_choose"));
  table("diagnostic-consistency", [["Model", model],
    ["Both payoffs correct, choice wrong", "exact_extraction_wrong_choice"],
    ["At least one payoff wrong, choice correct", "wrong_extraction_correct_choice"],
    ["Chose larger reported payoff (ties excluded)", r => fraction(r.choice_agrees_extracted_max, r.extraction_unique_max)],
    ["Reported ties", "extraction_ties"]], main.filter(r => r.condition === "full_extract_choose"));
  table("diagnostic-extraction-orders", [["Model", model], ["Prompt order", r => r.prompt_order ? "B → A" : "A → B"],
    ["Allowed-answer order", r => r.schema_order ? "B → A" : "A → B"],
    ["Both payoffs correct", r => `${r.extraction_exact}/${r.planned}`],
    ["Choice correct when both payoffs correct", r => fraction(r.exact_extraction_correct_choice, r.extraction_exact)]],
    report.summaries.filter(r => r.group_by === "model+condition+prompt_order+schema_order" && r.condition === "full_extract_choose"));
  table("diagnostic-orders", [["Model", model], ["Condition", r => names[r.condition]],
    ["Prompt order", r => r.prompt_order ? "B → A" : "A → B"],
    ["Allowed-answer order", r => r.schema_order ? "B → A" : "A → B"],
    ["Correct / planned", score]], report.summaries.filter(r => r.group_by === "model+condition+prompt_order+schema_order"));
  table("diagnostic-paired", [["Model", model], ["Compared with full information", r => names[r.comparison]],
    ["Matched cases", "planned_pairs"], ["Not correct → correct", "improved"], ["Correct → not correct", "worsened"],
    ["Accuracy change", r => fmt(100*r.accuracy_difference_planned, 1)+" pp"]], report.paired);
  const planned = main.reduce((n, r) => n + r.planned, 0);
  const accepted = main.reduce((n, r) => n + r.accepted, 0);
  el("diagnostic-status").textContent = `${accepted}/${planned} valid responses · Summary below averages the four order combinations; the figure separates them.`;
  el("diagnostic-figure").hidden = false;
  const stage = node("div", undefined, "stage");
  stage.append(node("span", "Payoff diagnostic: full / relevant / extraction"), node("span", accepted === planned ? "Complete" : "See results", "pill"));
  el("stages").insertBefore(stage, el("stages").children[6] || null);
})();
