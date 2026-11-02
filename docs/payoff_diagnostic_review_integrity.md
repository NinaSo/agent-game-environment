# Payoff diagnostic: independent integrity review

Status: **approved for separate smoke and main collection**, tied to the collection hashes and configuration digests in `payoff_diagnostic_integrity_gate.json`. Real-data verification also passed; see below.

## Scope and evidence

- Read new `diagnostic/design.py` and `diagnostic/collection.py`; inspected the reused prompt construction, SQLite helper, and Ollama transport.
- All 480 payloads contain one fresh user message, explicit permitted task evidence, settings, and output schema. No history, answer key, correct-value schema constraints, tools, or code execution reaches inference.
- Ollama requests are restricted to a literal loopback HTTP endpoint with ambient proxies and redirects disabled. Request counts, attempts, wall-clock time, output, context, and transport timeouts are bounded.
- Cases and attempts are separate. An attempt is persisted before transport; accepted response and correctness are committed atomically. Completed cases are skipped on resume; interrupted requests become ambiguous and consume budget.
- Only transient transport errors retry. Incorrect choices and incorrect integer payoff reports remain accepted observations. Malformed responses terminate that case. Strict parsing rejects duplicate/extra keys, booleans, fractional values, nonfinite values, and invalid choices.
- Resume checks configuration, critical source hashes, Python version, Ollama version, model digests, and deterministic replay. Every request and full response envelope are logged; replay reconstructs request, evidence, parsing, and scoring.
- Initial review found sorted JSON logging lost schema property order. Fixed before inference: order-preserving request logging, fixed inference option construction, and exact ordered request replay. Independent regression check confirms changed schema order is rejected.
- **23 diagnostic tests passed**, including **10 independently written integrity tests**. Tests use mocks in temporary directories; no inference was conducted by this reviewer.
- All **12 prior source files** and **8 existing databases** retain their original content/logical hashes. The new journal is separate.

## Interpretation safeguards

- The two numeric extraction fields are always presented A then B. This is a recorded design limitation, not a claim of observed internal reasoning order.
- A schema-valid but false extraction is scored as false without requerying. Numeric extraction and correct final choice are separate outcomes.
- Matched seed values across condition arms do not guarantee identical sampling paths.

## Real-data review

**Approved:** all 480 main cases and all 6 separately excluded smoke cases were valid on their first attempt. Independent audit code did not call the production scorer, prompt builder, or report function.

- Reconstructed every disclosed full-game payoff sentence or relevant-reward sentence from a separate explicit four-outcome payoff dictionary. Recomputed every correct action and saved score.
- Checked all requests against recorded case factors: single fresh user message, fixed disclosed opponent action, independent prompt and enum orders, no answer-key metadata or value-constrained schema, settings, model identity, and matched condition seeds.
- Verified raw accepted JSON equals the response envelope content and stored response. Checked extraction field types and order-preserving request schema logs. Every generation ended normally; maximum observed input count was 175 tokens.
- Reconfirmed frozen collection source/configuration hashes, all 12 prior source files unchanged, and all 8 earlier databases logically unchanged.
- Gemma choice counts: full 42/80, relevant 51/80, extraction 60/80. Both extracted rewards were correct in 22/80 cases, all 22 with a correct choice.
- Qwen choice counts: full 37/80, relevant 62/80, extraction 38/80. Both extracted rewards were correct in 26/80 cases, 24 with a correct choice.
- Incorrect extracted values remained accepted observations. Correct choices despite incorrect reported rewards must not be described as successful extraction.

Machine-readable evidence: `payoff_diagnostic_data_integrity.json`. These checks concern data integrity, not proof of any internal reasoning mechanism.


## Final presentation review

Approved dashboard HTML, diagnostic JavaScript, browser summary data, crossed-order figure, and findings document at the exact hashes in `payoff_diagnostic_presentation_integrity.json`.

- Browser summary payload exactly matches the saved report; no prompt/reply payload is embedded in it.
- Dashboard explicitly labels the overall summary as an average over order combinations and presents a figure with separate order panels plus exact breakdown tables.
- Payoff correctness, choice correctness, and consistency with reported values remain separate. Visible claims retain the fixed-output-order, small-sample, no-learning, and no-architectural-cause limitations.
- Every dashboard local resource/download target exists. Frozen collection sources remain unchanged.
- Scientific and integrity reviewers agree on accepted data/analysis at report SHA-256 `c35e007951fb3973c87f4de420f67befdfcc7b455d13ee68c68e45625d1bb134`. Root browser/visual and release-bundle checks are supervised separately.

Final readability revision: compact summary now uses two model rows and three condition columns. Verified every cell still reads the same model/condition summary and correct/planned denominator. Updated JavaScript SHA-256: `459119d06a4bb3364352eecb85153f6ee90ae1d823e98478d2e4ffd14dd81c68`. No other presentation or collection/data hashes changed. Approved.
