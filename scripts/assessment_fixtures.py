"""Explicit synthetic configuration and exports; never installed by runtime startup."""
import json
from pathlib import Path


def configuration():
    roster = {'students': [{'student_id': sid, 'cohort': 'SYNTHETIC-2026'} for sid in ('S001', 'S002', 'S003')]}
    items = [
        ('q1', ['2', '3', '4'], '4', 'numeracy', 'Practice addition with counters.'),
        ('q2', ['8', '10', '12'], '10', 'numeracy', 'Practice counting in pairs to ten.'),
        ('q3', ['input', 'output'], 'input', 'digital', 'Identify keyboard and sensor inputs.'),
        ('q4', ['yes', 'no'], 'yes', 'safety', 'Review the equipment safety checklist.'),
    ]
    key = {'assessment_id': 'synthetic-foundations', 'version': 'v1', 'items': [
        {'id': qid, 'kind': 'objective', 'choices': choices, 'accepted': [answer], 'points': 2,
         'skill': skill, 'foundation': foundation} for qid, choices, answer, skill, foundation in items]}
    qualitative = json.loads(json.dumps(key))
    qualitative['assessment_id'] = 'synthetic-reflection'
    qualitative['items'].append({'id': 'reflection', 'kind': 'interpretation', 'choices': [], 'accepted': [],
                                'points': 0, 'skill': 'reflection', 'foundation': 'Practice explaining sensor inputs using a keyboard example.'})
    return roster, {'synthetic-foundations@v1': key, 'synthetic-reflection@v1': qualitative}


def row(sid, stage, answers, key='synthetic-foundations@v1'):
    return {'student_id': sid, 'cohort': 'SYNTHETIC-2026', 'stage': stage, 'answer_key': key,
            'answers': dict(zip(('q1', 'q2', 'q3', 'q4'), answers))}


def exports():
    return {
        'baseline.json': {'submissions': [row('S001', 'baseline', ['4', '8', 'output', 'no']),
                                            row('S002', 'baseline', ['4', '10', 'output', 'yes'])]},
        'midpoint.json': {'submissions': [row('S001', 'midpoint', ['4', '10', 'input', 'no'])]},
        'final.json': {'submissions': [row('S001', 'final', ['4', '10', 'input', 'yes']),
                                         row('S002', 'final', ['4', '8', 'input', 'yes'])]},
    }


def install(root):
    root = Path(root)
    config = root / 'config'
    (config / 'keys').mkdir(parents=True, exist_ok=True)
    if (config / 'roster.json').exists() or list((config / 'keys').glob('*.json')):
        raise FileExistsError('Synthetic fixtures cannot overwrite an existing configuration')
    roster, keys = configuration()
    (config / 'roster.json').write_text(json.dumps(roster, indent=2), encoding='utf-8')
    for key_id, key in keys.items():
        (config / 'keys' / (key_id + '.json')).write_text(json.dumps(key, indent=2), encoding='utf-8')
    examples = root / 'synthetic-examples'
    examples.mkdir(parents=True)
    for name, value in exports().items():
        (examples / name).write_text(json.dumps(value, indent=2), encoding='utf-8')
    return examples


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('assessment_root', type=Path)
    args = parser.parse_args()
    print(install(args.assessment_root))
