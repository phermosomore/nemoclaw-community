# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Protect candidate isolation and the optimization acceptance contract."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

import yaml

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('cad_optimization', ROOT/'optimization/run_study.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OptimizationContractTests(unittest.TestCase):
    def test_high_iou_cannot_bypass_native_requirements(self):
        checks=dict(valid_solid=True,sketches=2,native_profile_features=2,
                    dimension_changes_geometry=True,restored=True,persistence=True)
        self.assertEqual(module.objective(.92,checks),.92)
        for field in checks:
            with self.subTest(field=field):
                invalid=dict(checks,**{field:False})
                self.assertEqual(module.objective(.99,invalid),0)

    def test_candidates_keep_inference_and_tools_fixed(self):
        base=yaml.safe_load((ROOT/'harness/agent_source/agent.yaml').read_text())
        original=yaml.safe_dump(base)
        with tempfile.TemporaryDirectory() as d:
            for arm in module.ARMS:
                cfg=module.candidate(base,arm,Path(d)/arm)
                for key in ('models','mcp','tools','telemetry'):
                    self.assertEqual(cfg[key],base[key])
                self.assertEqual(cfg['environment']['workspace'],'./workspace')
            self.assertEqual(yaml.safe_dump(base),original)

    def test_reviewer_instructions_limit_its_role(self):
        base=yaml.safe_load((ROOT/'harness/agent_source/agent.yaml').read_text())
        with tempfile.TemporaryDirectory() as d:
            cfg=module.candidate(base,'reviewer',Path(d))
            reviewer=cfg['harnesses']['deepagents']['settings']['deepagents']['subagents'][0]
            self.assertNotIn('tools',reviewer)  # Adapter schema rejects per-subagent tools.
            self.assertIn('Do not use FreeCAD or other tools',reviewer['system_prompt'])
            self.assertIn('Only you may modify FreeCAD',cfg['instructions']['system']['content'])
            self.assertTrue((Path(d)/'workspace/skills/native-cad/SKILL.md').is_file())


if __name__=='__main__': unittest.main()
