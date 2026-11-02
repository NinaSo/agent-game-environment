# Semantic-message study integrity review

## Precollection approval

The integrity reviewer and independent correctness reviewer explicitly agree that the semantic-message collection is ready at the hashes below. The parent may run the excluded smoke study, verify replay and model identities, then run the frozen main design. Actual-data/export/dashboard approval remains pending. This reviewer made no inference calls.

The main configuration has 32 games with 30 rounds: 960 model and 960 scripted decisions. The call budget counts both kinds of attempts (2,304 total including retry allowance), with at most three attempts per decision and 7,200 active execution seconds. The four-game smoke configuration is separate and excluded. Existing runner elapsed-time accounting measures active execution, not downtime, and requests are capped to remaining runtime.

## Evidence and boundaries

- Sixteen independent integrity regressions cover full-horizon legacy behavior, semantic schema rejection, observation whitelists, counterfactual hidden state and schedule changes, context bounds, fresh provider messages, feedback timing and crash recovery.
- Semantic observations contain only task/trial/horizon, remaining rounds, legal actions, own previous actions, previous opponent rewards, and retained past/current unverified scripted messages. They contain no schedule, current opponent action, opponent identity, evaluator consistency flag, future outcome, seed, own reward or score fields.
- Counterfactual schedule/identifier/seed changes leave exact observations and prompts unchanged. Counterfactual hidden past-action, own-reward, score and promise-consistency changes also leave prompts unchanged when permitted evidence is held fixed.
- The first opponent defection occurs at round 11 but cannot enter feedback until the round-12 decision. Current messages remain unverified claims even when the scripted promise is false. Feedback permits inference of previous opponent choices through the payoff table, as disclosed in the plan.
- Legal actions are exactly cooperate and defect in the configured order. Existing strict parser rejects A/B aliases, capitalization variants, extra fields, duplicate keys and non-JSON replies. The audited actual Ollama payload builder was exercised with a stub transport: one fresh user message, literal semantic enum, no tools or previous messages.
- Both players’ observations are saved from the same completed-round history. Durable attempted/accepted records, bounded retries, lock, source/config/runtime/provider/model checks and atomic round commits reuse the unchanged audited runner/provider/store. A semantic interruption test verifies accepted choices are not requested twice and final replay/scoring remains exact.
- Original task/condition/label/reward-assignment variants were compared throughout their horizons against runs/source_snapshot/engine.py. Legal actions, observations, exact prompts, transitions, scripted messages and baseline choices remain identical. All original actual data replayed: core 3,600 actions, stress 960, baselines 48,300 and smoke 12.
- Full suite personally rerun after the final collection source: 121 tests and 19 subtests passed. No precollection integrity blocker remains.

The generator records a shuffled episode list, but the reused runner executes its existing deterministic model/episode ordering. The study’s pairing and counterbalancing do not rely on execution-list randomization. No claim of randomized execution timing is made here.

## Approved hashes

```json
{
  "communication/configs/semantic_main.json": "c5a1f04bf2a2ee449ed7405cfaa3dceabe6df4273be2a542552ff228babe1ee1",
  "communication/configs/semantic_smoke.json": "970c877efd86e374da01e143f0cc1a8f0af6dd15ef2c980a279e464252f42675",
  "communication/design.py": "90fa2a81b65c80b26ede15df41709c261ac4362dc801cd2c40c08c0baa662a09",
  "game_lab/__init__.py": "262302b9f2681aedc496dd6e8d1c8010c40e1d47698d4324719b3aa82cc1d4d9",
  "game_lab/__main__.py": "687133826cca779d4d692f905efea1cf68cf73dad35c9c9cb2cf41cf4d40aa6a",
  "game_lab/engine.py": "875143ec37c4139de2a8fe972edd44481cc2f56cb2435b608ca62593e6789e7c",
  "game_lab/provider.py": "968e0d14f8ac3c69a5296d7822ea0ef6791a401cd467f1a4e9c00bdadb82b460",
  "game_lab/runner.py": "b1b30fc39290c03d6bb630d2deef74946f06e9ddb58d27c8f3c644a9a364ee78",
  "game_lab/store.py": "e2e9d8240ed74530dc1bd00d9626525a872a023a98aead07aeaecf8d1290d162"
}
```

## Completed actual-data approval

Both reviewers explicitly approve the completed collection and numerical results. This reviewer independently audited all 1,920 accepted decisions/attempts (960 model and 960 scripted) and all 960 committed rounds across 32 complete games. Every attempt was valid and there were no retries. The four-game smoke run contributed 12 model and 12 scripted decisions and remains excluded.

Every actual observation and exact prompt was rebuilt independently from explicit permitted fields and the four hardcoded payoff outcomes. Current opponent actions, schedule, seed, consistency flags and identifiers were absent from model prompts. Own-action and opponent-reward histories contained exactly the completed prior rounds; retained messages included only past/current unverified claims. The first defection appears in feedback only at round 12. The maximum actual model prompt was 4,070 bytes, within the conservative context guard.

Every raw accepted reply matched its provider envelope and legal action. Model identities, Ollama version, settings and collection-source hashes matched the gate and original pilot. Script actions, numerical rewards and cumulative scores were independently recomputed. Exact exported trace SHA256: `b4a78501a0d1d1a1d3afb7786a1dedd4bb6c99a864bd3deb774957c993db3de9`. Main report approval was coordinated with the correctness reviewer at SHA256 prefix `5d431828`; that reviewer independently recomputed window summaries and matched-pair contrasts.

All six original authoritative SQLite databases match the previous release archive by every ordered table-row hash. No earlier evidence was altered. Machine-readable counts, source/model identities, original-table hashes and exported-file hashes are saved in `docs/communication_data_integrity.json`.

Final dashboard/figure presentation review is a separate release check; numerical-data approval is complete.

## Final presentation approval

Both independent reviewers explicitly agree on the final dashboard and figure revisions: HTML `51da5f86…`, main script `f27b45ac…`, semantic-message script `6b833c66…`, report/plot source `a8a4a40a…`, findings `9f70deea…`, and corrected before/after PNG `d6fbe7e0…`. Full hashes are recorded in the machine-readable audit. Numerical report `5d431828…` and exact trace `b4a78501…` are unchanged by the figure-label repair.

All 48 DOM IDs are unique and all script target IDs resolve. Seven figures resolve and have alternate text. Dynamic tables use the existing safe textContent helper; no new executable HTML or code-evaluation sink was introduced. Button/panel mapping and native disclosure controls remain intact. Revised-study counts and timing are separate from the original A/B pilot. Coupled prompt/schema order and evolving-history limitations remain explicit. The previously misleading SQLite-main-file fingerprint was replaced by the actual exported-trace SHA256.

The final package extension includes the communication source/configurations/results and standalone SQLite backups under their relative paths, retaining symlink, private-runtime, lock and WAL/SHM exclusions. The complete suite personally passed: 123 tests and 19 subtests. New and main dashboard scripts pass Node syntax checks. Full actual-data audit was rerun after figure metadata updates and passed; six earlier databases remain unchanged.

No outstanding actual-data or presentation integrity blocker. Parent completes the release review document, browser QA and eight-database archive extraction verification.
