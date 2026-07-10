#!/usr/bin/env python3
import json, os, glob, sys

results_dir = '/Users/tanzsongsen/auto_test/reports/allure-results'
files = sorted(glob.glob(os.path.join(results_dir, '*-result.json')), key=os.path.getmtime)
passed = failed = broken = 0
failed_details = []
all_cases = []
for f in files:
    try:
        with open(f) as fp:
            d = json.load(fp)
    except Exception:
        continue
    status = d.get('status', 'unknown')
    name = d.get('name', 'unknown')
    tc_id = ''
    if 'parameters' in d:
        for p in d['parameters']:
            if p.get('name') == 'tc_id':
                tc_id = p.get('value', '')
    if status == 'passed':
        passed += 1
    elif status == 'failed':
        failed += 1
        status_msg = d.get('statusDetails', {}).get('message', '')[:200] if 'statusDetails' in d else ''
        failed_details.append(f'{tc_id} | {name} | {status_msg}')
    elif status == 'broken':
        broken += 1
        status_msg = d.get('statusDetails', {}).get('message', '')[:200] if 'statusDetails' in d else ''
        failed_details.append(f'BROKEN: {tc_id} | {name} | {status_msg}')
    all_cases.append(f'{tc_id} | {name} | {status}')

total = passed + failed + broken
print(f'Total: {total} | Passed: {passed} | Failed: {failed} | Broken: {broken}')
print('---ALL CASES---')
for c in all_cases:
    print(c)
print('---FAILED/BROKEN---')
for fd in failed_details:
    print(fd)
