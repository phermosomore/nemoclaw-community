# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Correlate a completed local CAD study with Helix Intake traces.

Raw trace files remain local. Trace text may contain private model details.
"""
import argparse
import json
from pathlib import Path
import urllib.parse
import urllib.request


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('study',type=Path)
    parser.add_argument('--base-url',default='http://127.0.0.1:9080')
    parser.add_argument('--workspace',default='default')
    args=parser.parse_args()
    base=args.base_url.rstrip('/')+'/apis/intake/v2/workspaces/'+args.workspace
    def get(path,**params):
        with urllib.request.urlopen(base+'/'+path+'?'+urllib.parse.urlencode(params),timeout=30) as response:
            return json.load(response)['data']
    records=json.loads((args.study/'measurements.json').read_text())
    traces=get('traces',page_size=1000)
    evidence=[]
    for record in records:
        matches=[t for t in traces if t.get('agent_name')==record['agent'] and t.get('ended_at')]
        if len(matches)!=1:
            raise RuntimeError(f"Expected exactly one finished trace for {record['agent']}, got {len(matches)}")
        trace=matches[0]
        spans=get('spans',page_size=1000,filter=json.dumps({'trace_id':trace['id']}))
        if len(spans)==1000:
            raise RuntimeError('Span result may be truncated; paginate before using evidence')
        (args.study/(record['agent']+'-trace.json')).write_text(json.dumps({'trace':trace,'spans':spans},indent=2))
        calls={}
        def walk(value):
            if isinstance(value,str) and value[:1] in ('{','['):
                try: walk(json.loads(value))
                except ValueError: pass
            elif isinstance(value,dict):
                if value.get('type')=='tool_call' and value.get('id'):
                    calls[value['id']]=value
                for child in value.values(): walk(child)
            elif isinstance(value,list):
                for child in value: walk(child)
        for span in spans: walk(span.get('raw_attributes'))
        actions=[{'name':c.get('name'),'args':c.get('args')} for c in calls.values()
                 if c.get('name') in ('read_file','task')]
        (args.study/(record['agent']+'-selected-actions.json')).write_text(json.dumps(actions,indent=2))
        evidence.append({'arm':record['arm'],'trial':record['trial'],'rep':record['rep'],'trace_id':trace['id'],'spans':len(spans),'total_tokens':trace.get('total_tokens'),'duration_ms':trace.get('duration_ms')})
    (args.study/'trace-evidence.json').write_text(json.dumps(evidence,indent=2))
    print(json.dumps(evidence,indent=2))


if __name__=='__main__': main()
