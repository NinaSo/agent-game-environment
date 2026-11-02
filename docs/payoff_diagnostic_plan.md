# Payoff diagnostic: frozen collection plan

## Question

Does choice accuracy change when the model receives only the relevant personal rewards, or is asked to report those rewards alongside its choice?

## Conditions

| Condition | Information | Required answer |
|---|---|---|
| Full information | Four joint outcomes, both players' rewards, fixed disclosed opponent action | Choice A or B |
| Relevant rewards only | Two personal rewards for the same disclosed opponent action | Choice A or B |
| Extract and choose | Same four outcomes as full information | Personal reward for A, personal reward for B, choice |

All decisions last one round and explicitly maximize the model's own points. The known opponent action is fixed; the model's choice cannot change it. Original Prisoner's Dilemma payoffs apply. No messages, moral wording, hidden opponent actions, history, or reward feedback. Each case starts a fresh request.

The extraction condition asks for numeric answers, not unrestricted private reasoning. Numeric fields appear A then B in the schema and instruction; their order is not separately manipulated. Output order is not evidence that a particular reasoning sequence occurred. Incorrect reported rewards are valid observations and never trigger a retry. Schemas specify types, not the correct reward values.

## Balanced factors and budget

- Qwen3:4b and Gemma3:4b, existing installed local Ollama models.
- Three conditions × two label-to-action mappings × two disclosed opponent actions × two prompt orders × two answer-enum orders × five sampling repeats × two models = **480 requests**.
- Each model and condition has 80 planned answers; five repetitions of 16 factor combinations, not 80 distinct reasoning problems.
- Conditions share a decoder seed within each model/factor/repeat block. This matches settings; it does not guarantee identical random generation paths across prompts.
- Order randomized deterministically within model to limit loading overhead.
- Temperature 0.7, top-p 0.9, context 8,192, output cap **128 for all conditions**, Qwen thinking disabled. The larger cap means this is a new experiment, not an exact replication of the earlier 64-token diagnostic.
- At most three attempts per case, 576 calls overall, 3,600 seconds total; transport/format failures logged. Six separate smoke cases (one per model/condition) are excluded from the main study.

## Outcomes fixed before collection

- Primary: correct choices / all planned cases per model and condition; unfinished/invalid cases are not silently removed.
- Also report valid responses and accuracy conditional on validity.
- Extraction: both personal rewards correct; A and B separately correct; choice accuracy when both are correct versus incorrect; whether the chosen action maximizes the model's reported rewards, with reported ties listed separately.
- Show prompt-order × answer-enum-order breakdowns, alongside reward-mapping and opponent-action breakdowns. Do not hide conflicting order patterns behind a pooled score.
- Compare matched full-information versus relevant-reward cases, and matched full-information versus extraction cases. Report descriptive percentage-point changes and paired improvements/worsenings; no significance claims.
- Retain exact prompts, schema, request settings, replies, identities and raw envelopes in a separate SQLite journal. Deterministic replay must reproduce stored scoring.

## Interpretation rules

- Better relevant-reward performance supports sensitivity to information selection/presentation, but shorter inputs and removal of opponent rewards change together.
- Better extraction-condition performance supports an effect of the requested output procedure; it does not prove faithful internal reasoning or architectural repair.
- Correct extraction plus wrong choice localizes an observable disconnect between reported payoffs and choice. Incorrect extraction alone cannot distinguish parsing, attention, instruction-following, or output effects.
- Answer consistency with incorrect extracted values does not make the final choice objectively correct.
- There is no reward learning or exploration in these one-shot tasks: all needed reward information is disclosed.
- These results concern two model configurations and a small set of payoff structures. They cannot isolate architecture from training, quantization, decoding, or prompting.

## Verification before and after collection

- Two independent reviewers inspect scientific correctness and data integrity and exchange findings.
- Hand-scored factor cases, strict parsing, hidden-key/schema checks, recovery, budgets and replay tests before inference.
- Smoke first, then frozen code/configuration and main collection.
- Independently recompute actual outcomes from raw responses; inspect factor results before writing conclusions.
- Add concise results and limitations to the existing dashboard, preserving earlier datasets.
