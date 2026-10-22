"""Run one builder through the existing factory, then export its accepted attempt.
sow: software-factories-masterclass-SOW-02
"""
import argparse
import importlib.util
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
ENGINE = ROOT / 'factory_engine'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task')
    parser.add_argument('attempt', help='A fresh attempts/NAME folder.')
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--scripted', action='store_true', help='Offline teaching actions; no model call.')
    modes.add_argument('--live', action='store_true', help='One funded session, after stating its expected cost.')
    parser.add_argument('--model')
    parser.add_argument('--expected-cost-cents-min', type=int)
    parser.add_argument('--expected-cost-cents-max', type=int)
    args = parser.parse_args(argv)
    path = Path(args.attempt)
    if len(path.parts) != 2 or path.parts[0] != 'attempts' or path.parts[1].startswith('.') or path.is_absolute():
        parser.error('Use attempts/NAME with a fresh simple name.')
    if args.live and (not args.model or args.expected_cost_cents_min is None or args.expected_cost_cents_max is None):
        parser.error('Live runs need one model and an expected cost range. There is no session money cap.')
    target = ROOT / path
    evidence = ROOT / 'runs' / path.name
    teaching = ROOT / 'runs' / (path.name + '-teaching')
    if any(p.exists() for p in (target, evidence, teaching)):
        print('Choose a new attempt name; prior evidence is preserved.')
        return 2
    task = (ROOT / args.task).resolve()
    if task != ROOT / 'tasks/b-limit-currencies.json':
        parser.error('This chapter uses tasks/b-limit-currencies.json.')
    driver = load('chapter_native_driver', ENGINE / 'agent-runs/drivers/openai_factory_driver.py')
    (ROOT / 'runs').mkdir(exist_ok=True)
    if args.scripted:
        scripted = load('chapter_teaching_builder', ROOT / 'scripted_builder.py')
        code = scripted.main(task, teaching)
        if code:
            return code
        qualifier = load('chapter_native_qualifier', ENGINE / 'agent-runs/drivers/qualify_scripted_builder.py')
        code = qualifier.qualify(ROOT, evidence, task_path=task, teaching_candidate=teaching)
    else:
        evidence.mkdir()
        workspace = evidence / 'scratch'
        code = driver.module('scratch').main(task, workspace, pack_root=ROOT, instructions='AGENTS-a6.md')
        if code:
            return code
        code = driver.main([str(task), str(workspace), str(evidence / 'run'), '--pack-root', str(ROOT),
                            '--environment', str(ENGINE / 'environment-a6.json'), '--model', args.model,
                            '--no-session-cap', '--expected-cost-cents-min', str(args.expected_cost_cents_min),
                            '--expected-cost-cents-max', str(args.expected_cost_cents_max)])
    if code:
        print('The attempt was not exported: the run did not reach ACCEPT.')
        return code
    shutil.copytree(evidence / 'run/candidate', target)
    print('ACCEPT; exported checked files to ' + str(path))
    print('Mode: ' + ('SCRIPTED; zero provider calls.' if args.scripted else 'LIVE; inspect actual provider usage.'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
