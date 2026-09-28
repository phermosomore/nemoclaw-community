# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Local Helix study-driver integration; not the optimize CLI's built-in evaluator.

Supply a working agent YAML and activated Helix environment. Every trial runs
serially against the live host FreeCAD and uses the immutable example scorer.
"""
from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import xmlrpc.client

import yaml

ROOT = Path(__file__).resolve().parents[1]
ARMS = ('baseline', 'prompt', 'skill', 'reviewer')


def rpc_code(code: str) -> str:
    rpc = xmlrpc.client.ServerProxy('http://127.0.0.1:9875')
    result = rpc.execute_code(code)
    if not result.get('success'):
        raise RuntimeError(f'FreeCAD RPC failed: {result}')
    return result['message']


def audit(document: str, save_dir: Path) -> dict:
    """Measure actual native objects and reversible dimension regeneration."""
    code = '''import FreeCAD as App, json
_d = App.getDocument(DOC)
_bodies = [o for o in _d.Objects if o.TypeId == 'PartDesign::Body' and o.Tip]
_sketches = [o for o in _d.Objects if o.TypeId == 'Sketcher::SketchObject']
_features = [o for o in _d.Objects if o.TypeId.startswith('PartDesign::') and o.TypeId not in ('PartDesign::Body','PartDesign::Feature','PartDesign::FeaturePython') and hasattr(o,'Profile') and o.Profile]
_a = dict(document=DOC, sketches=len(_sketches), native_profile_features=len(_features), valid_solid=False, dimension_changes_geometry=False, restored=False, persistence=False)
if len(_bodies)==1:
    _body=_bodies[0]
    _shape=_body.Tip.Shape
    _a['valid_solid']=_shape.isValid() and len(_shape.Solids)==1
    _v=_shape.Volume
    for _sk in _sketches:
        for _i,_con in enumerate(_sk.Constraints):
            if not _con.Name or _con.Type not in ('Distance','DistanceX','DistanceY','Radius','Diameter'): continue
            _q=_sk.getDatum(_i)
            if abs(_q.Value)<1e-7: continue
            _d.openTransaction('Independent dimension audit')
            _changed=False
            try:
                _sk.setDatum(_i,App.Units.Quantity(str(_q.Value*1.01)+' mm'))
                _d.recompute()
                _s=_body.Tip.Shape
                _changed=_s.isValid() and len(_s.Solids)==1 and abs(_s.Volume-_v)>max(1e-6,abs(_v)*1e-5)
            except Exception:
                pass
            finally:
                _d.abortTransaction()
                _d.recompute()
            _restored=abs(_body.Tip.Shape.Volume-_v)<max(1e-6,abs(_v)*1e-5)
            if _changed and _restored:
                _a.update(dimension_changes_geometry=True,restored=True,dimension=_con.Name)
                break
        if _a['dimension_changes_geometry']: break
    # Named parameters referenced by expressions are also valid driving dimensions.
    # Do not mistake the absence of named sketch constraints for non-parametric CAD.
    if not _a['dimension_changes_geometry']:
        _expressions = [str(expr) for obj in _d.Objects for path,expr in getattr(obj,'ExpressionEngine',[])]
        for _obj in _d.Objects:
            for _prop in _obj.PropertiesList:
                if _obj.getTypeIdOfProperty(_prop) not in ('App::PropertyLength','App::PropertyDistance','App::PropertyFloat'): continue
                _ref=_obj.Name+'.'+_prop
                _labelref='<<'+_obj.Label+'>>.'+_prop
                if not any(_ref in expr or _labelref in expr for expr in _expressions): continue
                _q=getattr(_obj,_prop)
                _num=float(_q.Value if hasattr(_q,'Value') else _q)
                if abs(_num)<1e-7: continue
                _d.openTransaction('Independent expression parameter audit')
                _changed=False
                try:
                    setattr(_obj,_prop,_num*1.01)
                    _d.recompute()
                    _s=_body.Tip.Shape
                    _changed=_s.isValid() and len(_s.Solids)==1 and abs(_s.Volume-_v)>max(1e-6,abs(_v)*1e-5)
                except Exception:
                    pass
                finally:
                    _d.abortTransaction()
                    _d.recompute()
                _restored=abs(_body.Tip.Shape.Volume-_v)<max(1e-6,abs(_v)*1e-5)
                if _changed and _restored:
                    _a.update(dimension_changes_geometry=True,restored=True,dimension=_ref)
                    break
            if _a['dimension_changes_geometry']: break
    if not _a['dimension_changes_geometry']:
        for _sheet in [o for o in _d.Objects if o.TypeId=='Spreadsheet::Sheet']:
            for _cell in _sheet.getNonEmptyCells():
                _alias=_sheet.getAlias(_cell)
                if not _alias: continue
                _ref=_sheet.Name+'.'+_alias
                _labelref='<<'+_sheet.Label+'>>.'+_alias
                if not any(_ref in expr or _labelref in expr for expr in _expressions): continue
                try:
                    _q=App.Units.Quantity(_sheet.getContents(_cell))
                except Exception:
                    continue
                if abs(_q.Value)<1e-7: continue
                _d.openTransaction('Independent spreadsheet dimension audit')
                _changed=False
                try:
                    _sheet.set(_cell,(_q*1.01).UserString)
                    _d.recompute()
                    _s=_body.Tip.Shape
                    _changed=_s.isValid() and len(_s.Solids)==1 and abs(_s.Volume-_v)>max(1e-6,abs(_v)*1e-5)
                except Exception:
                    pass
                finally:
                    _d.abortTransaction()
                    _d.recompute()
                _restored=abs(_body.Tip.Shape.Volume-_v)<max(1e-6,abs(_v)*1e-5)
                if _changed and _restored:
                    _a.update(dimension_changes_geometry=True,restored=True,dimension=_ref)
                    break
            if _a['dimension_changes_geometry']: break
    _d.recompute()
    _d.saveAs(SAVE)
    App.closeDocument(DOC)
    _re=App.openDocument(SAVE)
    _rb=[o for o in _re.Objects if o.TypeId=='PartDesign::Body' and o.Tip]
    _a['persistence']=len(_rb)==1 and _rb[0].Tip.Shape.isValid() and len(_rb[0].Tip.Shape.Solids)==1 and abs(_rb[0].Tip.Shape.Volume-_v)<max(1e-6,abs(_v)*1e-5) and len([o for o in _re.Objects if o.TypeId=='Sketcher::SketchObject'])==len(_sketches)
    App.closeDocument(_re.Name)
print('AUDIT_JSON='+json.dumps(_a))
'''
    code = 'DOC='+repr(document)+'\nSAVE='+repr(str(save_dir / (document+'.FCStd')))+'\n'+code
    return json.loads(rpc_code(code).split('AUDIT_JSON=', 1)[1].strip())


def objective(iou: float, checks: dict) -> float:
    """Do not reward geometry that bypasses the native-parametric contract."""
    passed = (checks['valid_solid'] and checks['sketches'] > 0
              and checks['native_profile_features'] > 0
              and checks['dimension_changes_geometry'] and checks['restored']
              and checks['persistence'])
    return iou if passed else 0.0


def candidate(base: dict, arm: str, directory: Path) -> dict:
    if arm not in ARMS:
        raise ValueError(arm)
    cfg = copy.deepcopy(base)
    cfg['name'] = 'cad-study-'+uuid.uuid4().hex[:12]
    cfg['environment']['workspace'] = './workspace'
    cfg['environment']['artifacts'] = './artifacts'
    (directory/'workspace').mkdir(parents=True)
    if arm != 'baseline':
        cfg['instructions']['system']['content'] = (ROOT/'optimization/native-prompt.txt').read_text()
    if arm in ('skill', 'reviewer'):
        shutil.copytree(ROOT/'optimization/skills', directory/'workspace/skills')
        cfg['instructions']['system']['content'] += '\nBefore construction, read /skills/native-cad/SKILL.md and follow it.'
    if arm == 'reviewer':
        cfg['harnesses']['deepagents']['settings']['deepagents']['subagents'] = [{
            'name': 'cad-plan-reviewer',
            'description': 'Review measured mesh dimensions and a proposed native feature construction plan before the main agent builds it.',
            'system_prompt': 'You are a CAD plan reviewer. Use only the measurements and plan supplied by the parent. Do not use FreeCAD or other tools. Check native sketch-driven construction, editable named constraints, independent X/Y contours, wall/base thickness and single-solid handle attachments. Return concise actionable corrections; do not claim to have built or verified geometry.',
        }]
        cfg['instructions']['system']['content'] += '\nAfter measuring the mesh and before building, call cad-plan-reviewer once with the measurements and native feature plan. Incorporate its feedback. Only you may modify FreeCAD.'
    return cfg


class CadEvaluator:
    def __init__(self, args):
        self.args = args
        self.base = yaml.safe_load(args.agent_config.read_text())
        self.records = []
        self.protected = [ROOT/'meshes/reference_mug.obj', ROOT/'harness/dataset/train/parametric-mug/instruction.md', *sorted((ROOT/'scorer').glob('*.py')), Path(__file__).resolve()]
        self.hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.protected}

    def evaluate(self, *, trial_number, suggestions, trial_overlay, rep):
        from nemo_optimization.candidate import CandidateEvaluationResult
        arm = suggestions['metadata.name']
        folder = self.args.output / f'trial-{trial_number}-rep-{rep}-{arm}'
        folder.mkdir(parents=True, exist_ok=False)
        cfg = candidate(self.base, arm, folder)
        import jsonschema
        descriptor = Path(sys.prefix)/'share/nemo-fabric/adapters/deepagents/deepagents.fabric-adapter.json'
        schema = json.loads(descriptor.read_text())['settings_schema']
        jsonschema.validate(cfg['harnesses']['deepagents']['settings'], schema)
        (folder/'agent.yaml').write_text(yaml.safe_dump(cfg, sort_keys=False))
        doc = 'OptCAD'+uuid.uuid4().hex[:10]
        if 'EXISTS False' not in rpc_code(f'import FreeCAD as App\nprint("EXISTS", {doc!r} in App.listDocuments())'):
            raise RuntimeError('Refusing to overwrite an existing document')
        prompt = self.protected[1].read_text().replace('@MESH_PATH@',str(self.protected[0])).replace('`EvalMug`',f'`{doc}`')
        (folder/'instruction.md').write_text(prompt)
        print(f'START trial={trial_number} rep={rep} arm={arm} document={doc}', flush=True)
        start = time.monotonic()
        with (folder/'invoke.log').open('w') as log:
            result = subprocess.run([self.args.nemo, 'agents','invoke','--agent-config',str(folder/'agent.yaml'),'--input',prompt,'--no-progress'], cwd=folder, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            # Abort rather than silently selecting among infrastructure failures.
            raise RuntimeError(f'Invocation failed; inspect {folder}/invoke.log')
        scored = subprocess.run([sys.executable,str(ROOT/'scorer/score.py'),doc,str(self.protected[0])],capture_output=True,text=True)
        (folder/'score.log').write_text(scored.stdout+scored.stderr)
        if scored.returncode:
            raise RuntimeError(f'Scorer failed; inspect {folder}/score.log')
        iou = float(scored.stdout.strip())
        checks = audit(doc, folder)
        record = dict(trial=trial_number,rep=rep,arm=arm,agent=cfg['name'],document=doc,iou=iou,objective=objective(iou,checks),seconds=round(time.monotonic()-start,2),checks=checks)
        for p in self.protected:
            if hashlib.sha256(p.read_bytes()).hexdigest() != self.hashes[str(p.relative_to(ROOT))]:
                raise RuntimeError(f'Immutable evaluation input changed: {p}')
        (folder/'result.json').write_text(json.dumps(record,indent=2))
        self.records.append(record)
        (self.args.output/'measurements.json').write_text(json.dumps(self.records,indent=2))
        print('RESULT '+json.dumps(record),flush=True)
        return CandidateEvaluationResult(aggregate_metrics={'native_iou':record['objective']})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--agent-config',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--nemo',default='nemo')
    parser.add_argument('--repeats',type=int,default=1)
    parser.add_argument('--arms',nargs='+',choices=ARMS,default=list(ARMS))
    args=parser.parse_args()
    if args.repeats < 1: parser.error('--repeats must be positive')
    args.output=args.output.resolve()
    args.output.mkdir(parents=True,exist_ok=False)
    # Same host-wide lock used by the Harbor wrapper: verify its path before changing.
    with open(os.environ.get('CAD_TRIAL_LOCK', str(Path(tempfile.gettempdir()) / 'cad-harness-trial.lock')),'w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        from nemo_optimization.backends.optuna.study_driver import run_numeric_study
        payload={'metadata':{'name':'cad-candidate-study'},'optimizer':{
            'numeric':{'enabled':True,'sampler':'grid','n_trials':len(args.arms)},
            'reps_per_param_set':args.repeats,
            'eval_metrics':{'native_iou':{'direction':'maximize','weight':1.0}},
            'search_space':{'candidate':{'type':'fabric','path':'metadata.name','values':args.arms}},
        }}
        evaluator=CadEvaluator(args)
        (args.output/'immutable-inputs.json').write_text(json.dumps(evaluator.hashes,indent=2))
        study=run_numeric_study(payload,args.output/'study',evaluator,seed=17)
        best=study.best_trial.params['candidate']
        summary={'best_candidate':best,'eligible_candidate':best if study.best_trial.value > 0 else None,'best_value':study.best_trial.value,'executed_trials':study.executed_trials,'repeats':args.repeats,'promoted':False,'integration':'Helix internal run_numeric_study with custom CAD CandidateEvaluator; candidate IDs map to materialized configs'}
        (args.output/'summary.json').write_text(json.dumps(summary,indent=2))
        print(json.dumps(summary),flush=True)


if __name__=='__main__': main()
