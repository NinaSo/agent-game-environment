"""Read-only diagnostic analysis, counting all planned requests in primary accuracy."""
from contextlib import closing
import csv
import json
from pathlib import Path
from followups.studies import connect, metadata
from .collection import replay


def report(path, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    with closing(connect(path, readonly=True)) as db:
        db.execute('BEGIN')
        verification = replay(db)
        manifest = metadata(db)
        cases, inspection = [], []
        for row in db.execute('SELECT * FROM cases ORDER BY id'):
            spec, evidence = json.loads(row['spec']), json.loads(row['evidence'])
            value = json.loads(row['response']) if row['response'] else {}
            accepted = row['status'] == 'complete'
            extraction = accepted and spec['condition'] == 'full_extract_choose'
            unequal = extraction and value['points_A'] != value['points_B']
            cases.append(dict(spec, status=row['status'], choice=value.get('choice'), answer=evidence['answer'],
                              correct=row['correct'], first_shown=evidence['first_shown'],
                              first_schema=evidence['first_schema'], points_A=value.get('points_A'),
                              points_B=value.get('points_B'), true_points_A=evidence['available_points']['A'],
                              true_points_B=evidence['available_points']['B'],
                              points_A_correct=int(value['points_A'] == evidence['available_points']['A']) if extraction else None,
                              points_B_correct=int(value['points_B'] == evidence['available_points']['B']) if extraction else None,
                              extraction_exact=int(all(value['points_'+a] == evidence['available_points'][a] for a in 'AB')) if extraction else None,
                              extracted_unique_max=int(unequal) if extraction else None,
                              choice_agrees_extracted_max=int(value['choice'] == ('A' if value['points_A'] > value['points_B'] else 'B')) if unequal else None))
            inspection.append(dict(row))
        attempts = [dict(r) for r in db.execute('SELECT * FROM attempts ORDER BY case_id,attempt')]
    summaries = []
    groupings = [('model', 'condition')] + [('model', 'condition', f) for f in
                 ('mapping', 'opponent_choice', 'prompt_order', 'schema_order')]
    groupings += [('model', 'condition', 'prompt_order', 'schema_order')]
    for fields in groupings:
        groups = {}
        for case in cases:
            groups.setdefault(tuple(case[f] for f in fields), []).append(case)
        for key, rows in sorted(groups.items()):
            valid = [r for r in rows if r['status'] == 'complete']
            extracted = [r for r in valid if r['extraction_exact'] is not None]
            unique = [r for r in extracted if r['extracted_unique_max']]
            correct = sum(r['correct'] for r in valid)
            item = dict(zip(fields, key), group_by='+'.join(fields), planned=len(rows), accepted=len(valid),
                        correct=correct, incorrect=len(valid)-correct,
                        invalid=sum(r['status'] == 'invalid' for r in rows),
                        incomplete=sum(r['status'] == 'incomplete' for r in rows),
                        pending=sum(r['status'] == 'pending' for r in rows),
                        accuracy_planned=correct/len(rows), accuracy_accepted=correct/len(valid) if valid else None,
                        extraction_accepted=len(extracted),
                        points_A_correct=sum(r['points_A_correct'] for r in extracted),
                        points_B_correct=sum(r['points_B_correct'] for r in extracted), extraction_exact=sum(r['extraction_exact'] for r in extracted),
                        extraction_unique_max=len(unique),
                        choice_agrees_extracted_max=sum(r['choice_agrees_extracted_max'] for r in unique),
                        extraction_ties=len(extracted)-len(unique),
                        exact_extraction_correct_choice=sum(r['extraction_exact'] == 1 and r['correct'] == 1 for r in extracted),
                        exact_extraction_wrong_choice=sum(r['extraction_exact'] == 1 and r['correct'] == 0 for r in extracted),
                        wrong_extraction_correct_choice=sum(r['extraction_exact'] == 0 and r['correct'] == 1 for r in extracted),
                        wrong_extraction_wrong_choice=sum(r['extraction_exact'] == 0 and r['correct'] == 0 for r in extracted))
            item['extraction_accuracy_planned'] = item['extraction_exact']/len(rows) if key[1] == 'full_extract_choose' else None
            item['extraction_accuracy_accepted'] = item['extraction_exact']/len(extracted) if extracted else None
            item['choice_agreement_given_unique_extraction'] = item['choice_agrees_extracted_max']/len(unique) if unique else None
            for metric in ('literal_B', 'first_shown', 'first_schema'):
                count = sum(r['choice'] == ('B' if metric == 'literal_B' else r[metric]) for r in valid)
                item[metric+'_count'], item[metric+'_rate'] = count, count/len(valid) if valid else None
            summaries.append(item)
    paired = []
    blocks = {}
    for case in cases:
        blocks.setdefault(case['block_id'], {})[case['condition']] = case
    for model in sorted({c['model'] for c in cases}):
        for condition in ('relevant_direct', 'full_extract_choose'):
            pairs = [(rows['full_direct'], rows[condition]) for rows in blocks.values()
                     if 'full_direct' in rows and condition in rows and rows['full_direct']['model'] == model]
            if not pairs:
                continue
            paired.append(dict(model=model, reference='full_direct', comparison=condition,
                               planned_pairs=len(pairs), both_accepted=sum(a['status'] == b['status'] == 'complete' for a, b in pairs),
                               improved=sum(a['correct'] != 1 and b['correct'] == 1 for a, b in pairs),
                               worsened=sum(a['correct'] == 1 and b['correct'] != 1 for a, b in pairs),
                               both_correct=sum(a['correct'] == b['correct'] == 1 for a, b in pairs),
                               neither_correct=sum(a['correct'] != 1 and b['correct'] != 1 for a, b in pairs),
                               accuracy_difference_planned=sum(int(b['correct'] == 1)-int(a['correct'] == 1) for a, b in pairs)/len(pairs)))
    result = dict(manifest=manifest, verification=verification, cases=cases, summaries=summaries, paired=paired,
                  limitations=['Descriptive fresh-context diagnostic; no learning or internal mechanism identified.',
                               'Five sampled repeats per factorial cell; not five independently trained models.',
                               'Extraction changes the requested output structure and length; it does not isolate hidden reasoning.',
                               'Extraction fields always presented points_A, points_B, choice; actual generated key order is not guaranteed.',
                               'Primary accuracy counts every planned case; conditional accepted accuracy is also reported.'])
    for name, rows in (('cases', cases), ('summary', summaries), ('paired', paired)):
        fields = list(dict.fromkeys(k for row in rows for k in row))
        with (out / (name+'.csv')).open('w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    (out/'report.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    (out/'evidence.json').write_text(json.dumps(dict(manifest=manifest, cases=inspection, attempts=attempts), indent=2, allow_nan=False)+'\n')
    browser = {key: result[key] for key in ('verification', 'summaries', 'paired', 'limitations')}
    safe = json.dumps(browser, allow_nan=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    (out/'data.js').write_text('window.DIAGNOSTIC_DATA = '+safe+';\n')
    return result
