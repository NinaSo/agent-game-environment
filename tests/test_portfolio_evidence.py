"""The public decision walkthrough must agree with replayable recorded evidence."""
import json
from pathlib import Path

from game_lab.engine import digest, observation, parse_action, prompt, transition


def test_recorded_walkthrough_reconstructs_observation_prompt_and_score():
    path = Path(__file__).resolve().parents[1] / 'results/portfolio_example.json'
    evidence = json.loads(path.read_text())
    episode = evidence['config']
    decision = evidence['decision']
    prior = evidence['prior_round']['result']
    scored = evidence['scored_round']['result']
    assert transition(episode, [], prior['actions']) == prior
    observed = observation(episode, [prior], decision['player'])
    rendered = prompt(episode, observed)
    assert observed == decision['observation']
    assert rendered == decision['prompt']
    assert digest({'observation': observed, 'prompt': rendered}) == decision['snapshot_hash']
    assert parse_action(evidence['raw_response'], observed['legal_actions']) == decision['action']
    assert scored['actions'][decision['player']] == decision['action']
    assert transition(episode, [prior], scored['actions']) == scored
