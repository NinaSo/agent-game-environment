"""Frozen factorial design; answer keys never enter inference payloads."""
import itertools
import json

from followups.studies import build_case as original_case, MODELS
from game_lab.engine import canonical, digest, seed_for
from game_lab.models import select_models

CONDITIONS = ('full_direct', 'relevant_direct', 'full_extract_choose')
OPTIONS = {'temperature': 0.7, 'top_p': 0.9, 'num_ctx': 8192, 'num_predict': 128}


def generate_config(smoke=False, models=None):
    custom = models is not None
    models = select_models(models)
    cases = []
    for model, mapping, opponent, prompt, schema, repeat in itertools.product(
        models, range(2), 'AB', range(2), range(2), range(5)
    ):
        factors = dict(model=model, mapping=mapping, opponent_choice=opponent,
                       prompt_order=prompt, schema_order=schema, repeat=repeat)
        block = digest(factors)[:24]
        for condition in CONDITIONS:
            case = dict(**factors, condition=condition, block_id=block,
                        decoder_seed=seed_for(20261029, 'diagnostic_decoder', block) % 2**31)
            case['id'] = digest(case)[:24]
            cases.append(case)
    cases.sort(key=lambda c: (c['model'], seed_for(20261029, 'diagnostic_order', c['id'])))
    if smoke:
        cases = [next(c for c in cases if c['model'] == m and c['condition'] == cond)
                 for m in models for cond in CONDITIONS]
    return dict(version=2 if custom else 1, **({'models': models} if custom else {}),
                run_id='payoff_diagnostic_smoke' if smoke else 'payoff_diagnostic',
                phase='excluded_smoke' if smoke else 'diagnostic', inference=OPTIONS.copy(),
                max_calls=(9 if smoke else 288) * len(models),
                max_seconds=(300 if smoke else 1800) * len(models),
                max_attempts=3, timeout_seconds=120, cases=cases)


def validate_config(config):
    if not isinstance(config, dict) or config.get('phase') not in ('excluded_smoke', 'diagnostic'):
        raise ValueError('Unknown diagnostic configuration')
    expected = generate_config(config['phase'] == 'excluded_smoke', models=config.get('models'))
    if set(config) != set(expected):
        raise ValueError('Unknown/missing configuration fields')
    for key in expected:
        if key in ('max_calls', 'max_seconds', 'max_attempts', 'timeout_seconds'):
            if type(config[key]) is not int or not 1 <= config[key] <= expected[key]:
                raise ValueError('Invalid bounded budget: ' + key)
        elif config[key] != expected[key]:
            raise ValueError('Frozen design mismatch: ' + key)


def build_case(case):
    base = original_case(dict(case, study='fixed_opponent_pd', label_pair='AB'))
    prompt = base['prompt'].split('\nReturn only a JSON object')[0]
    if case['condition'] == 'relevant_direct':
        shown = 'AB' if case['prompt_order'] == 0 else 'BA'
        prompt = 'This game lasts exactly one round. Maximize YOUR points THIS ROUND.\n'
        prompt += '\n'.join(f"If you choose {a}, you receive {base['available_points'][a]} points."
                            for a in shown)
        prompt += f"\nThe opponent's choice this round is fixed to {case['opponent_choice']}. Your choice cannot change it."
    schema = {'type': 'object', 'properties': {}, 'required': [], 'additionalProperties': False}
    if case['condition'] == 'full_extract_choose':
        prompt += ('\nReport your points for A and B given the fixed opponent choice, then choose the option '
                   'that maximizes your points. Return only JSON with integer fields "points_A", '
                   '"points_B", and string field "choice". No explanation.')
        schema['properties'].update(points_A={'type': 'integer'}, points_B={'type': 'integer'})
        schema['required'].extend(['points_A', 'points_B'])
    elif case['condition'] in ('full_direct', 'relevant_direct'):
        prompt += '\nReturn only a JSON object with exactly one field, "choice", set to your chosen option. No explanation.'
    else:
        raise ValueError('Unknown condition')
    schema['properties']['choice'] = {'type': 'string', 'enum': base['enum_order']}
    schema['required'].append('choice')
    return dict(base, prompt=prompt, schema=schema)


def payload_for(case, inference):
    evidence = build_case(case)
    if len(evidence['prompt'].encode()) + 256 + inference['num_predict'] > inference['num_ctx']:
        raise ValueError('Context guard: no truncation allowed')
    payload = dict(model=case['model'], messages=[{'role': 'user', 'content': evidence['prompt']}],
                   stream=False, format=evidence['schema'], options={**{key: inference[key] for key in OPTIONS}, 'seed': case['decoder_seed']},
                   keep_alive='10m')
    if case['model'].startswith('qwen3'):
        payload['think'] = False
    return payload


def parse_response(raw, condition):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=unique)
    keys = {'choice', 'points_A', 'points_B'} if condition == 'full_extract_choose' else {'choice'}
    if not isinstance(value, dict) or set(value) != keys or value['choice'] not in ('A', 'B'):
        raise ValueError('Invalid response fields or choice')
    if keys != {'choice'} and any(type(value[k]) is not int for k in ('points_A', 'points_B')):
        raise ValueError('Extracted points must be integers')
    return value
