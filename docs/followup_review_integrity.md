# Follow-up integrity review

Scope: separate known-reward and fixed-opponent Prisoner’s Dilemma checks. Original experiment core, configurations and collected data remain frozen. No inference requests were made by this reviewer.

## Precollection decision

Approved for the excluded four-case smoke check, followed by the 400-case frozen collection if smoke validation passes. The independent correctness reviewer explicitly concurred on the same studies.py hash. Final data and dashboard approval remain pending completion and independent inspection.

The design produces 400 sampled decisions from 20 unique question texts, with schema order, model and decoder repetitions crossed as recorded in the configuration. These are not 400 independent reasoning problems.

## Integrity evidence

- Actual Ollama payload construction was exercised with a stub transport: each request contains one fresh user message with the exact frozen prompt, the permitted choice schema and decoder options. Grading answers, case identifiers, previous replies and cross-case memory are not sent.
- Existing literal-loopback transport, proxy/redirect restrictions, response bounds, strict one-field parser and context guard are reused without modification. Models receive no tools or executable capability.
- Initialization commits schema, manifest and case bank together. Attempt start is durable; accepted response and case score commit together. Resume checks configuration, source hashes, runtime, Ollama version and model digests, never re-requests accepted cases, and counts ambiguous attempts against the persisted budget.
- Call, per-case attempt and elapsed-time limits are bounded. Elapsed time includes downtime. The timeout is capped to remaining time. Exclusive database locking prevents concurrent collectors.
- Replay reconstructs every prompt, permitted enum and grading answer and verifies snapshot hashes, raw accepted action, score and case conservation. It rejects orphan attempts, unknown statuses, attempts after terminal responses and impossible terminal records.
- Reporting uses a read-only connection, explicit read transaction and closing cleanup. A concurrent-writer regression proves all exported tables/inspection records share one read snapshot. Browser data escapes script-sensitive characters.
- Packaging includes follow-up source/config/results and SQLite backups under their original relative paths. Model weights, runtimes, private paths, symlinks, live locks and WAL/SHM sidecars remain excluded. Standalone backup files are converted to DELETE journal mode and tested with a first read-only open.

Independent verification: 15 focused integrity tests added in tests/test_followups_integrity.py; full suite personally rerun: 93 tests and 14 subtests passed. No outstanding precollection integrity blocker.

## Approved source/config hashes

```json
{
  "followups/__init__.py": "99c20398544631bb2efd8db3a9cefe633e6fdbb13d872bfb97e99cc88f7fca77",
  "followups/__main__.py": "8e496aec01265c6dd7f666d99c28b0f7bb416274ccc1c8806d286374e2b6df07",
  "followups/configs/payoff_checks.json": "5e07929a60bee7860fb47b659750f875aa00b61ce8b99964efc55cd184fe55c1",
  "followups/configs/payoff_checks_smoke.json": "bacf2884f40f66bf14b00b71ad47e6a551558e79965b9735651dc3edae9d6d19",
  "followups/studies.py": "590f7983fbeea70288f044671f7a61e70a881ac8e59562f420b740d575e73083",
  "game_lab/engine.py": "3932965279f222e4bc61615fd43d585f66f1d1ed4c0d23a5aa50eec338c187c4",
  "game_lab/provider.py": "968e0d14f8ac3c69a5296d7822ea0ef6791a401cd467f1a4e9c00bdadb82b460",
  "package_review.py": "3cc8a8a6d98c85e01a27b2bbc2cfb4b0b15927fc9b7c6001895506e0280a5bc0"
}
```

## Completed actual-data audit

Approved: all 400 frozen follow-up cases completed with exactly one valid attempt each, with no retries, invalid outputs or missing responses. The four-case smoke run is separate and marked excluded. The correctness reviewer and integrity reviewer explicitly concurred on the completed-data approval at report SHA256 `171e64b73cc9a34a8b2126ebd7ad429c6066c41678c4775c312dc1c040768751` and unchanged collection-source SHA256 `590f7983fbeea70288f044671f7a61e70a881ac8e59562f420b740d575e73083`.

This reviewer independently checked every stored prompt, enum, evidence hash, accepted raw reply, provider envelope/model identity, recorded score, exported evidence record and dashboard inspection entry. A separate regular-expression parser read disclosed numerical rewards directly from each prompt and recomputed all 400 correct answers. The 400 cases contain 20 unique prompt texts; the grading answer remains evaluator-side. The reviewed provider constructs only the fresh disclosed prompt and choice schema, with no prior-case messages or tools.

Verified scores: Gemma 120/120 known-reward and 40/80 fixed-opponent payoff checks; Qwen 112/120 and 41/80 respectively. Ollama version and both model digests match the original experiment. All 27 previously frozen source/configuration/result files still match recorded original hashes. Every SQLite table in the original core and stress databases also matches its original delivery archive by ordered row hashes; follow-up collection did not alter original evidence.

Machine-readable audit evidence and export hashes: `docs/followup_integrity_data_audit.json`. Final dashboard wording and portable archive verification are separate release checks.

## Final presentation agreement

Both independent reviewers approve the final follow-up narrative and dashboard at the hashes recorded in `docs/followup_integrity_data_audit.json`: HTML `92614570…`, main script `fd878426…`, follow-up script `63975fd2…`, findings `0f727929…`, plotting script `96b27bdf…`, packaging script `cb9da78c…`. All literal script target IDs are present and unique. Raw replies and exact prompts render through textContent, with no executable HTML insertion. Answer keys are clearly marked as evaluator calculations. The follow-up sample remains separate from the original pilot. The added plot reads only the saved report; packaging retains the reviewed SQLite snapshot isolation. The full suite was rerun: 93 tests and 14 subtests passed.

No outstanding actual-data or presentation integrity blocker. Parent performs browser QA and final portable-archive release verification.
