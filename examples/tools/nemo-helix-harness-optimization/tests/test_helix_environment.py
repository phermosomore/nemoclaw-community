# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Check the retained trial adapter selects the same Helix as the CLI."""

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


class HelixEnvironment(unittest.TestCase):
    def connection(self, **overrides):
        env = dict(os.environ)
        for key in ('NHX_BASE_URL', 'NHX_WORKSPACE', 'NMP_BASE_URL', 'NMP_WORKSPACE'):
            env.pop(key, None)
        env.update(overrides)
        wrapper = Path(__file__).resolve().parents[1] / 'harness' / 'agent_source'
        result = subprocess.run(
            [sys.executable, '-c',
             'import json, harbor_wrapper as h; print(json.dumps([h.BASE, h.WORKSPACE]))'],
            cwd=wrapper, env=env, check=True, capture_output=True, text=True,
        )
        return json.loads(result.stdout)

    def test_local_defaults(self):
        self.assertEqual(self.connection(), ['http://localhost:8080', 'default'])

    def test_helix_overrides_stale_installation(self):
        self.assertEqual(self.connection(
            NHX_BASE_URL='http://127.0.0.1:9080', NHX_WORKSPACE='cad-tests',
            NMP_BASE_URL='http://127.0.0.1:9999', NMP_WORKSPACE='old-workspace',
        ), ['http://127.0.0.1:9080', 'cad-tests'])
