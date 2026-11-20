# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Every task defers to the shared images (evals/environment, evals/verifier), and grade.sh lists every check."""

import json
import re
import unittest
from pathlib import Path

EVALS = Path(__file__).resolve().parents[1] / 'evals'
TASKS = sorted(p.parents[1] for p in EVALS.glob('*/*/tests/test.sh'))  # evals/<split>/<task>


class EvalsInSyncTest(unittest.TestCase):
    def test_tasks_use_the_shared_images(self):
        for task in TASKS:
            for folder, files in {'tests': {'Dockerfile': 'FROM cad-verifier', 'test.sh': 'exec bash /grader/grade.sh'},
                                  'environment': {'Dockerfile': 'FROM cad-env'}}.items():
                names = {p.name for p in (task / folder).iterdir() if not p.name.startswith('.')}  # e.g. .DS_Store
                self.assertEqual(names, {*files, 'reference.obj.gz'}, task.name)
                for name, line in files.items():
                    self.assertIn(line, (task / folder / name).read_text(), task.name)

    def test_grade_sh_lists_every_check(self):
        verifier = EVALS / 'verifier'
        rows = set(re.findall(r'row\("([\w-]+)"', (verifier / 'check_model.py').read_text()))
        listed = re.search(r'for id in ([\w\s-]+); do', (verifier / 'grade.sh').read_text())
        self.assertEqual(set(listed.group(1).split()), rows)

    def test_ref_faces_matches_the_oracle(self):
        manifest = json.loads((EVALS / 'manifest.json').read_text())
        oracle = {t['path']: t['controls']['oracle']['faces'] for t in manifest['tasks']}
        oracle |= manifest['generated']['oracle_faces']  # every task, by evals/<split>/<task>
        self.assertEqual(set(oracle), {str(t.relative_to(EVALS)) for t in TASKS})
        for path, expected in oracle.items():
            test_sh = (EVALS / path / 'tests' / 'test.sh').read_text()
            faces = int(re.search(r'REF_FACES=(\d+)', test_sh).group(1))
            self.assertEqual(faces, expected, path)


if __name__ == '__main__':
    unittest.main()
