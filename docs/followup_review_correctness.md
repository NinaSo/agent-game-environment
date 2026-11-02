# Independent scientific correctness review: follow-up diagnostics

Reviewed on 28 October 2026. Collection and analysis source SHA256: `590f7983fbeea70288f044671f7a61e70a881ac8e59562f420b740d575e73083`. Reviewed report SHA256: `171e64b73cc9a34a8b2126ebd7ad429c6066c41678c4775c312dc1c040768751`.

**Decision: approve the completed diagnostic results and final scientific presentation.** No scientific correctness blocker remains.

## Scope and verification

Before collection, checked the balanced factorial design, independently ordered prompt options and response enums, unique optimal actions, fresh question contexts, and distinction between disclosed reward rules and evaluator answer keys. Both reviewers agreed on the frozen source before the supervisor initiated inference. The full suite passed 93 tests and 14 subtests; this reviewer added a partial-budget regression covering correct, incorrect, invalid, attempted-pending, and unattempted cases.

After collection, independently read the SQLite journal and parsed the actual prompt text with regular expressions, without calling the question builder. Recomputed the reward-maximizing answer and correctness for all 400 questions. Verified all 63 exported summary rows against individual records, including every factor breakdown, accepted/planned denominator, missing-response count, literal-B eligibility, and position metric. Both CSV files match their corresponding report records field for field.

There are 400 completed questions and exactly 400 valid attempts, with no invalid outputs, retries, or unattempted questions. The four smoke questions are excluded. The main design comprises 20 distinct question texts per model, crossed with two enum orders and five seeded responses; 400 responses are not 400 independent problem instances.

## Verified outcomes

| Study | Gemma3:4b correct | Qwen3:4b correct |
|---|---:|---:|
| Disclosed reward, 10 versus 1 | 120/120 (100%) | 112/120 (93.3%) |
| Single-round PD, given opponent action | 40/80 (50%) | 41/80 (51.25%) |

Qwen's eight known-reward errors all occur with A worth 10, B worth 1, and B displayed first: four of five responses under each enum order. It answers all 80 X/Y and K/M questions correctly. It selects B on 28/40 A/B known-reward questions; Gemma selects B on 20/40, exactly tracking the balanced reward mapping.

In PD, Qwen selects B on 73/80 questions. It is correct on 37/40 questions where B maximizes its reward and 4/40 where A does. Gemma selects B on 20/80: all 20 questions with opponent A and the A action group displayed first; it selects A on the other 60. These are descriptive response patterns, not inferred algorithms.

First-displayed selections are Gemma 60/120 and Qwen 68/120 in known reward, and Gemma 20/80 and Qwen 47/80 in PD. First-enum selections are 60/120 for each model in known reward, and Gemma 40/80 and Qwen 39/80 in PD. Marginal rates alone can conceal conditional label/order patterns; they do not establish absence of a schema influence.

## Interpretation limits

Both models can follow directly disclosed rewards on these simple prompts, so a blanket inability to select higher numeric rewards is unsupported. Performance is substantially weaker on the four-row PD format despite a known opponent action and unique own-reward optimum. This localizes a task-format difficulty; it does not distinguish parsing, attention, instruction following, answer-label preference, or an internal reasoning mechanism.

These follow-ups were motivated by pilot observations. They do not establish that the observed PD label pattern causes the original repeated-game behavior, and they do not measure uncertainty-driven exploration, cooperation, morality, or competitive adaptation. Five samples per configuration and two quantized local models support narrow descriptive conclusions, not broad model rankings. No new model inference was performed by this reviewer.

## Final presentation check

Read the final dashboard narrative, factor-table and inspector mappings, and detailed findings; visually inspected the standalone accuracy plot. All displayed counts and percentages match the independently audited records. The distinction between 20 question texts and 400 responses, post-collection inspection of detailed error patterns, and the proposed but unrun next study are explicit. No scientific presentation blocker remains.

Reviewed versions (SHA256 prefixes): dashboard HTML `92614570`, main JavaScript `fd878426`, follow-up JavaScript `63975fd2`, detailed findings `0f727929`, plot script `96b27bdf`, accuracy PNG `7f6ea101`. The report remains `171e64b7` and collection source remains `590f7983`.
