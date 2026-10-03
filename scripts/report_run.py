"""Render a saved run or merge compatible runs without another model call."""
import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from datascr.contracts import Field
from datascr.validation import resolve
from datascr.pipeline import coverage
from datascr.storage import save

def merge(runs):
    first=runs[0]
    if any(r['entity'] != first['entity'] or r['schema'] != first['schema'] for r in runs):
        raise ValueError('Runs must have the same entity and schema')
    result={**first, 'run_id':uuid4().hex, 'merged_from':[r['run_id'] for r in runs]}
    for key in ('documents','attempts','source_attempts','discovery','issues','rejected_claims'):
        result[key]=[]
        for run in runs:
            for item in run.get(key,[]):
                if item not in result[key]: result[key].append(item)
    claims=[]
    for run in runs:
        for field in run['fields'].values():
            for claim in field['candidates']:
                if claim not in claims: claims.append(claim)
    fields=[Field(**f) for f in first['schema']]
    result['fields']=resolve(claims,fields)
    result['model_calls']=sum(r['model_calls'] for r in runs)
    result['coverage']=coverage(result,fields)
    result['needs_review']=any(f['status']!='observed' for f in result['fields'].values())
    result['status']='failed' if not claims else 'partial' if result['needs_review'] or result['issues'] else 'completed'
    return result

def render(result):
    cov=result['coverage']
    lines=['# '+result['entity'],'',
           f"Status: {result['status']}. Evidence for {cov['fields_with_evidence']}/{cov['total_fields']} fields; "
           f"{cov['documents']} documents; {cov['accepted_claims']} accepted claims; "
           f"{cov['rejected_claims']} rejected claims/properties.",'',
           'Observed means evidence passed structural validation; it is not independent factual verification.',
           'Class and individual-ship data remain separate. Missing values are not zero.','']
    for name,field in result['fields'].items():
        lines.extend(['## '+name+' — '+field['status'],''])
        for claim in field['candidates']:
            value=json.dumps(claim['value'],ensure_ascii=False)
            source=claim['source_url']
            page=f", page {claim['page']}" if claim.get('page') else ''
            lines.append(f"- {value} {field['unit']} — [{claim.get('publisher') or source}]({source})"
                         f"{page}; scope: {claim.get('source_scope') or 'unspecified'}")
        if not field['candidates']: lines.append('No accepted evidence.')
        lines.append('')
    lines.extend(['## Collection and validation issues',''])
    lines.extend('- '+json.dumps(i,ensure_ascii=False) for i in result['issues'])
    return '\n'.join(lines)+'\n'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('runs',nargs='+',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    runs=[json.loads(p.read_text(encoding='utf-8')) for p in args.runs]
    result=merge(runs) if len(runs)>1 else runs[0]
    args.output.mkdir(parents=True,exist_ok=True)
    if len(runs)>1: save(result,args.output)
    target=args.output/(result['run_id']+'.md')
    target.write_text(render(result),encoding='utf-8')
    print(target.resolve())

if __name__=='__main__': main()

