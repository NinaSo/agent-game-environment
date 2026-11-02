# Payoff diagnostic: results

- 480/480 valid responses, all accepted on the first attempt; six smoke requests excluded.
- Two local models, three conditions, independently varied prompt and answer-enum order, balanced A/B payoff mappings and disclosed opponent actions.
- 80 requests per model/condition: 16 factor combinations × five sampled repeats.
- Each request uses fresh context. All needed reward information is supplied; this is not reward learning.

## Choice accuracy

These totals average the four order combinations. Inspect the order breakdown below before interpreting them.

| Model | Full information | Relevant personal rewards only | Full information + report payoffs and choose |
|---|---:|---:|---:|
| Qwen3 4B | 37/80 (46.25%) | 62/80 (77.5%) | 38/80 (47.5%) |
| Gemma3 4B | 42/80 (52.5%) | 51/80 (63.75%) | 60/80 (75%) |

- Qwen relevant-only: +31.25 percentage points; 25 matched cases improved and none worsened.
- Gemma relevant-only: +11.25 points; 20 improved and 11 worsened.
- Gemma payoff-reporting: +22.5 points; 28 improved and 10 worsened.
- Qwen payoff-reporting: +1.25 points; eight improved and seven worsened.
- These are descriptive results, not significance tests or performance guarantees.

## Separate presentation orders

Each entry is correct choices / 20 planned responses. Prompt order refers to own-action row groups (or the two relevant choices); answer order refers to the permitted A/B values in the response schema.

| Model | Prompt order | Answer order | Full | Relevant only | Report + choose |
|---|---|---|---:|---:|---:|
| Qwen | A → B | A → B | 8/20 | 18/20 | 5/20 |
| Qwen | A → B | B → A | 9/20 | 20/20 | 5/20 |
| Qwen | B → A | A → B | 10/20 | 12/20 | 15/20 |
| Qwen | B → A | B → A | 10/20 | 12/20 | 13/20 |
| Gemma | A → B | A → B | 10/20 | 10/20 | 15/20 |
| Gemma | A → B | B → A | 12/20 | 11/20 | 15/20 |
| Gemma | B → A | A → B | 10/20 | 15/20 | 15/20 |
| Gemma | B → A | B → A | 10/20 | 15/20 | 15/20 |

- Qwen payoff-reporting accuracy is 25% with A first versus 70% with B first, averaging answer-enum order within each prompt order. Its overall 47.5% hides different patterns.
- Qwen relevant-only improves over full information in all four cells, but reaches 90–100% with A first and 60% with B first.
- Gemma payoff-reporting choice accuracy is 75% in every cell. Relevant-only does not improve over full information in every cell.

## Were the reported payoffs correct?

| Model | A payoff correct | B payoff correct | Both correct | Correct choice when both correct | Correct choice despite at least one wrong payoff |
|---|---:|---:|---:|---:|---:|
| Qwen | 71/80 | 34/80 | 26/80 (32.5%) | 24/26 | 14/54 |
| Gemma | 32/80 | 59/80 | 22/80 (27.5%) | 22/22 | 38/58 |

- Qwen twice reported A = 5 and B = 3, then chose B despite the instruction to maximize its own reward. Case IDs: `6258b59e9b5135a43270e19f`, `759f9f5b0bf8d3da6144a7ce`.
- These are observable inconsistencies between reported values and choice; they do not reveal the internal cause.
- Gemma's correct choices do not imply accurate extraction: 38 correct choices accompanied incorrect reported values.
- Chosen action matched the larger reported value in 71/80 Qwen responses and 72/80 Gemma responses. No reported ties. Consistency with incorrect values is not objective accuracy.
- Gemma's exact-pair extraction is 2/40 with A-first prompts and 20/40 with B-first prompts, even though choice accuracy stays 75%. Detailed extraction counts by both order factors are in the dashboard and summary CSV.

## Interpretation and limitations

- Relevant-only presentation helps select rewards in this setup, particularly for Qwen. It also shortens text and removes opponent rewards; these changes are not isolated.
- Reporting payoffs improves Gemma's choice accuracy without establishing accurate payoff extraction. It is not proof that a reasoning process has been repaired.
- Extraction fields always appear A then B in the requested schema. Actual generated key order can differ. This is a structured output intervention, not a record of hidden reasoning or proof that extraction causally preceded the choice.
- Defection maximizes the disclosed one-round reward in every case. Opponent action changes the payoff values but not that semantic optimum; the test is not strategic adaptation.
- Common 128-token cap for all new conditions, versus 64 in the earlier diagnostic. Compare these new arms internally; older headline rates are not an exact replication target.
- Same installed model digests and Ollama version as prior experiments; small models, one payoff structure and five repeats per cell limit generalization.
- The study does not isolate architecture, training, quantization or decoding causes. It identifies behavior under controlled task presentations.

## Evidence

- [Plan](payoff_diagnostic_plan.md)
- [All cases](../results/diagnostic/cases.csv), [factor summaries](../results/diagnostic/summary.csv), [matched comparisons](../results/diagnostic/paired.csv)
- [Exact requests and replies](publication.md#full-historical-evidence)
- [Independent scientific audit](payoff_diagnostic_correctness_data_audit.json), [integrity audit](payoff_diagnostic_data_integrity.json), [supervisor scoring](payoff_diagnostic_supervisor_audit.json)
- Source snapshot: `diagnostic/source_snapshot/`; collection gate: `payoff_diagnostic_collection_gate.json`.
