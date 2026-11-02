# Supervising review

The collection architecture was reviewed before the real pilot. One agent implemented the core; two independent agents tested it, exchanged findings, verified repairs, and reached explicit agreement. Their exact scopes and source hashes are recorded in the separate review documents. The supervising agent inspected the architecture, ran the checks, verified actual local-model smoke results, and froze the collection configuration before starting the real pilot.

## Architecture accepted

- Pure game mechanics and permitted observation construction are separate from the Ollama transport.
- All tested model calls are stateless, local, action-only requests with no tools.
- Both current decisions use the same previous-round state. Valid actions are individually durable; the scored round and its completion status commit atomically.
- A unique logical decision can have multiple logged transport attempts, but at most one accepted action and one scored outcome.
- Keyed random draws and source/configuration/model checks make request order and retries irrelevant to recorded rewards.
- The analysis opens read-only SQLite snapshots and verifies replay. It does not call models or alter experiments.
- Dashboard exports separate permitted features from targets and show explicit unrun inference gates.

## Material defects found and repaired

1. An interrupted final request could exhaust retries without marking the episode incomplete, allowing a loop without progress. A regression test now checks termination.
2. Replay initially did not reject missing/null committed decisions, inconsistent SQL trial keys, or changed per-episode configuration. Conservation and manifest checks now reject these cases.
3. Malformed provider envelopes could escape the intended error path. They are now recorded as invalid responses.
4. The original moral passage included an imperative to consider fairness. It was replaced before collection with descriptive framing while preserving the own-points objective.
5. Dashboard validity initially used one minus the invalid rate, which would incorrectly count transport-only failures as valid. It now uses distinct accepted decisions over attempted decisions.
6. The dashboard server’s inherited HEAD handler bypassed its asset allowlist. GET and HEAD now share validation, including traversal, symlink and foreign-Host rejection.
7. An internal homepage rewrite broke relative assets. A redirect to the actual dashboard path fixes browser resolution while preserving offline viewing.
8. Browser caching mixed an old reporting script with renamed CSV fields, displaying `NaN` for regret. The server now sends `no-store` and ignores conditional timestamp caching; a versioned script URL invalidates the older cached asset. Browser checks then matched the independently verified values.
9. SQLite backups inherited WAL journal mode, so an extracted database could fail its first read-only query without journal sidecars. Packaging now converts only the temporary backup to DELETE journal mode before archiving. The authoritative experiment databases remain untouched; the packaging regression opens the extracted copy read-only first.

## Verification evidence

The complete test suite passes in both the working runtime and a freshly installed project-local virtual environment. See `test_results.txt` and `clean_environment_tests.txt`. Collection code is frozen in `runs/source_snapshot/`; presentation edits occur outside that package.

The game smoke batch completed 12/12 valid decisions and replayed exactly. All 405 scripted baseline episodes completed; 48,300 actions replayed exactly. Random bandit expected-point regret was approximately 0.2004 per pull against a theoretical 0.2; the privileged highest-mean reference had zero expected-point regret.

Full 60-trial permitted bandit histories fit the conservative context guard in checks across every frozen mean permutation and seat. No history truncation is implemented. Actual prompt/token usage remains in attempts for inspection.

Browser testing verifies that result tabs and the snapshot selector work, raw text is rendered safely, numeric tables are visible, and live status is independent of result rebuilding. The final suite passes 63 tests and 14 subtests in both runtimes.

All 64 real pilot episodes completed: 3,600 model decisions in the core batch and 480 model plus 480 scripted decisions in the communication batch. Every attempt was valid. Recorded-action replay verifies all 4,560 pilot actions. Both reviewers independently audited the completed traces and agreed with the reported observations, scores, denominators, and contrasts. Their audit JSON files preserve the exact counts and checks.

The supervising agent separately recomputed core bandit wins, scores, port counts, regret and repetitions from SQLite, and recomputed post-switch communication outcomes. Two separate analysis builds reproduced all 15 CSV checksums, dashboard data and bootstrap indices; see `analysis_reproducibility.json`. Core and configuration hashes remain identical to the pre-collection gate. Findings and limits are in `findings.md`; runtime/token evidence is in `runtime_summary.json`.

## Claim limits

Review and passing tests provide evidence for the specified invariants; they are not a guarantee that all possible bugs have been eliminated. This is a behavioral pilot, not a validated measurement of internal cognition. Section 10 model recovery, controlled-history probes, held-out candidate selection, and parameter inference are not implemented or executed in this delivery. No claims requiring those stages are made.
