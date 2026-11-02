# Offline replay fixture

`synthetic_replay.json` is a hand-specified, synthetic engineering fixture. It contains two three-round Prisoner's Dilemma games played by deterministic programmed strategies. It contains no model-generated responses and contributes no observations to the research results.

Run `python scripts/replay_fixture.py` from the repository root. The command creates a temporary SQLite journal, runs the ordinary collector with a provider that raises on any attempted inference, replays the journal, checks the hand-calculated scores, then removes the temporary files. The command tests collection and replay; it does not reproduce the historical model findings.

The clean source distribution also retains `runs/source_snapshot/engine.py`, the small original engine used by existing regression tests. It is historical source code, not a database or synthetic model output.
