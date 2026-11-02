"use strict";
(() => {
  const followup = window.FOLLOWUP_DATA;
  if (!followup || followup.phase !== "followup") return;
  const studyName = (value) => ({
    known_reward: "1 · Known reward",
    fixed_opponent_pd: "2 · Payoff table",
  }[value] || value);
  const ordered = (rows) => rows.sort((a, b) => studyName(a.study).localeCompare(studyName(b.study)) || a.model.localeCompare(b.model));
  const overview = ordered(followup.summaries.filter((r) => r.group_by === "study+model"));
  const total = followup.summaries.find((r) => r.group_by === "overall");
  el("followup-status").textContent = `${total.accepted}/${total.planned} valid responses · ${total.correct} correct · Separate from the original pilot.`;
  const stage = node("div", undefined, "stage");
  stage.append(node("span", "Known-reward and one-round payoff controls"), node("span", total.accepted === total.planned ? "Complete" : "Incomplete", "pill"));
  el("stages").insertBefore(stage, el("stages").children[4] || null);
  table("followup-summary", [
    ["Study", (r) => studyName(r.study)], ["Model", "model"],
    ["Correct / planned", (r) => `${r.correct}/${r.planned}`],
    ["Incorrect", (r) => r.accepted - r.correct], ["Invalid", "invalid"],
    ["Unresolved", (r) => r.pending + r.incomplete],
    ["Accuracy", (r) => fmt(100 * r.correct / r.planned, 2) + "%"],
  ], overview);
  const fields = {
    answer: "Which label is correct?", label_pair: "Label pair", mapping: "Reward / payoff mapping",
    prompt_order: "Order in the prompt", schema_order: "Order in the answer format",
    opponent_choice: "Given opponent action (payoff study)",
  };
  const dimension = el("followup-dimension");
  for (const [key, title] of Object.entries(fields)) {
    const option = node("option", title); option.value = key; dimension.append(option);
  }
  function groupName(row, field) {
    if (field === "mapping") return row.study === "known_reward"
      ? `${row.mapping === 0 ? "First" : "Second"} label in the pair pays 10`
      : `${row.mapping === 0 ? "A" : "B"} has the cooperative payoff role`;
    if (field === "prompt_order" || field === "schema_order") return row[field] === 0 ? "Forward label order (A/B, X/Y, K/M)" : "Reversed label order (B/A, Y/X, M/K)";
    return row[field];
  }
  function breakdown() {
    const field = dimension.value;
    const rows = ordered(followup.summaries.filter((r) => r.group_by === `study+model+${field}` && (field !== "opponent_choice" || r.study === "fixed_opponent_pd")));
    table("followup-breakdown", [
      ["Study", (r) => studyName(r.study)], ["Model", "model"],
      [fields[field], (r) => groupName(r, field)],
      ["Correct / planned", (r) => `${r.correct}/${r.planned}`],
      ["Accuracy", (r) => fmt(100 * r.correct / r.planned, 2) + "%"],
      ["Chose B / A–B answers", (r) => r.literal_B_denominator ? `${r.literal_B_count}/${r.literal_B_denominator}` : "—"],
      ["Chose first shown", (r) => pct(r.first_shown_rate)],
      ["Chose first in format", (r) => pct(r.first_schema_rate)],
    ], rows);
  }
  dimension.addEventListener("change", breakdown); breakdown();
  const select = el("followup-select");
  followup.inspection.forEach((r, i) => {
    const option = node("option", `${studyName(r.study)} · ${r.model} · ${r.case_id} · ${r.correct === 1 ? "correct" : r.status === "complete" ? "incorrect" : r.status}`);
    option.value = String(i); select.append(option);
  });
  function inspectFollowup() {
    const r = followup.inspection[Number(select.value)];
    if (!r) return;
    el("followup-prompt").textContent = r.prompt;
    el("followup-response").textContent = `Raw accepted reply: ${r.raw_accepted_reply ?? "none"}\n\nExpected choice: ${r.answer}\nRecorded choice: ${r.action ?? "none"}\nStatus: ${r.status}\n\nAllowed answer order: ${r.enum_order.join(", ")}\nDecoder seed: ${r.decoder_seed}\nSnapshot hash: ${r.snapshot_hash}\n\nThe expected choice was computed separately and was not supplied as an answer key to the model.`;
  }
  select.addEventListener("change", inspectFollowup); inspectFollowup();
})();
