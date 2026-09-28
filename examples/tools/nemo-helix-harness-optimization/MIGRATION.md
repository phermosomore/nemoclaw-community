<!-- SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Helix migration progress

Reviewed 2026-09-24. This is an incremental migration, not a claim that the
complete optimization loop runs on Helix. The CAD use case, Deep Agents harness,
reference mesh, scorer, and candidate change boundaries remain the same.

## Branch and publication order

This work branches from `feat/nemo-platform-harness-optimization` into
`feat/nemo-helix-harness-optimization`. The original review remains
[PR #190](https://github.com/NVIDIA/nemoclaw-community/pull/190). No PR was changed
or published for this migration. If #190 merges first, merge the resulting main
branch into this branch before submitting the rename; do not restore the old
folder during conflict resolution. Maintainers must coordinate an alternative
order if this work supersedes #190.

| Old path | New path |
| --- | --- |
| `examples/tools/nemo-platform-harness-optimization` | `examples/tools/nemo-helix-harness-optimization` |

No submodules move. Existing clones only need the new `cd` path. External links
in #190 or downstream walkthroughs will need updating after merge. Catalog
indexes and third-party notices are updated in this change.

## Upstream evidence

The comparison uses the original example's pinned NeMo Platform 0.6.0 workflow
and these public sources, inspected on the review date:

- [Helix source](https://github.com/NVIDIA-NeMo/nemo-helix/tree/b6ff571721eadd2b85c939c9c8e3405ab9b3ae44),
  current default-branch revision at inspection.
- [Helix setup](https://docs.nvidia.com/nemo-helix/documentation/get-started/setup/),
  [agent deployment](https://docs.nvidia.com/nemo-helix/documentation/agents/deploy-agents/),
  and [Intake](https://docs.nvidia.com/nemo-helix/documentation/agents/observe-agents/).
- [Insights plugin dependencies](https://github.com/NVIDIA-NeMo/nemo-helix/blob/b6ff571721eadd2b85c939c9c8e3405ab9b3ae44/plugins/nemo-insights/pyproject.toml)
  and its Analyst implementation. The plugin pins `labs-trace-intel` at
  `cd639d223e06ee9d27783df6b461d302ceb09137`; do not replace that dependency
  in a Helix environment with standalone HEAD.
- [Standalone Analyst](https://github.com/NVIDIA-NeMo/labs-trace-intel/tree/3a06bce1298190cd143a96880d6999052086632d),
  including its Intake, configuration, evidence-stream, and model-access guides.
- [Current optimizer](https://docs.nvidia.com/nemo-helix/documentation/agents/optimize-agents/run-the-agent-optimizer/).

The standalone instructions pin the inspected Analyst revision. Live validation
confirmed that `nemo-helix[all]` has no available package version on the configured
index. The walkthrough now uses the source revision above and its committed
`uv.lock`, with `make TOOLCHAIN=system bootstrap-python` and
`bootstrap-studio`. Both completed. Build tools were isolated: uv 0.12.18,
Node.js 22.23.2, and pnpm 10.34.5. The source environment uses Python 3.12.12,
Fabric 0.3.0, Deep Agents 0.7.9, and Relay 0.7.3.

Startup requires activating the environment, including `VIRTUAL_ENV`. Calling
its `nemo` executable directly (even with an updated PATH) launched Fabric's
adapter with the system interpreter and failed. Full activation fixed the
smoke test. Studio returned HTTP 200 after building its assets and restarting
the isolated test service.

## What changed

| Area | Previous workflow | Current migration |
| --- | --- | --- |
| Install | `nemo-platform[all]==0.6.0` | Pinned source bootstrap and upstream `uv.lock`; CLI remains `nemo`. |
| Connection | `NMP_BASE_URL`, `NMP_WORKSPACE` | Trial adapter reads `NHX_BASE_URL`, `NHX_WORKSPACE`; CLI receives the same settings explicitly. |
| CAD runtime | Agent spec, Deep Agents, local FreeCAD MCP | Same architecture and task; example model values are placeholders. |
| Traces | Intake and Studio | Keep Helix Intake; do not switch to Langfuse or local files. |
| Analyst | `nemo agents analyst run` | Helix `nemo insights analysis-runs create`, or standalone `insight-agent` with the Intake connector. |
| Findings | Persistent Insights | Integrated path persists in Helix; standalone path writes local YAML only. |
| Ethos | Strict parser from the agents plugin | Retain domain requirements as explicit Analyst input. No import of the removed parser or promise of automatic upload. |
| Eval Author | Phase of Experimentalist | Repository/API unavailable for this migration; integration pending. |
| Experimentalist | Automatic proposals and scoring | Removed from active instructions. Current Helix optimization APIs are not assumed to replace this CAD loop. |
| Old profiles | Discovered `harness/optimizer.yaml` and `experiment-config.yaml` | Archived as `.yaml.txt` under `results/legacy-config/`; not discoverable as active profiles. |
| Measurements | Live results from the previous version | Preserved with historical labels; not advertised as Helix evidence. |

`NMP_ACCESS_TOKEN` remains intentionally in the standalone connector settings:
that is the name currently documented upstream. Persistent `cad-agent` and
`cad-agent-deployment` names are unchanged. Historical result files retain old
version names and optimizer terminology for provenance. Neither is a current
runtime dependency.

The Analyst accepts other trace providers, but that flexibility is separate
from the selected trace source. The integrated route also has Helix-owned job
execution, model access, and insight persistence around the Analyst library.
The standalone route needs its own inference credentials and an explicit,
time-bounded Intake query. It cannot create missing evaluation scores.

## Progress and remaining gates

- [x] Create a branch from the original review branch and rename the example.
- [x] Review public Helix and Analyst contracts and document their differences.
- [x] Rewrite the walkthrough through baseline scoring and trace analysis.
- [x] Provide a bounded Intake Analyst configuration with ethos input.
- [x] Preserve CAD assets, scorer, Harbor tasks, candidate checks, and attribution.
- [x] Remove obsolete orchestration from the active path and label old evidence.
- [x] Update connection settings, local tests, notices, and catalog references.
- [x] Install Helix from the pinned source lock with its runtime extras and build Studio.
- [x] Execute three CAD baseline runs and verify their matching Intake traces on Helix.
- [x] Execute integrated and standalone analysis; record results and versions in [the live validation record](results/helix-validation.md).
- [x] Exercise the retained Harbor adapter and Docker verifier in a full live trial.
- [x] Verify the HTTP and SDK exports and render Studio in a browser.
- [ ] Obtain Eval Author access and its ethos/schema contract.
- [x] Manually author and calibrate independent native-feature, dimension-regeneration, and persistence checks from the findings; retain the original IoU scorer. This does not claim Eval Author integration.
- [x] Implement a local candidate-search alternative using Helix’s Optuna study driver and a CAD evaluator adapter.
- [x] Integrate serial candidate evaluation with independent scoring and trace collection.
- [ ] Promote a candidate only after repeatability and quality evidence justify it.

A local candidate-search adapter now reuses the implemented Helix Optuna
study driver; see [optimization](optimization/README.md). Eval Author and the
old Experimentalist are not prerequisites for this alternative. The genetic
prompt backend is currently a stub; the stock skill loop also needs adaptation
for CAD traces and IoU rewards.

The unavailable Eval Author and replacement skill remain explicit handoff points for their original workflow,
not stubbed implementations. No guessed repository, import, CLI, or claim of
compatibility is provided for either. The retained Harbor wrapper
has passed its invoke, trace-query, conversion, and verifier paths against the
selected Helix revision. Its authored-evaluation integration remains pending.

Candidate evaluation must preserve the original invariants: only instructions,
skills, and subagents change; reference geometry, model choice, scorer, wrapper,
and task stay fixed. Check candidates outside their own directory using
`scorer/verify_candidates.py`. Repeat runs, serialize access to FreeCAD, measure
IoU independently, and reject proxy-score improvements that degrade geometry or
editability. The current same-mesh validation split measures repeatability only.

## Verification record

Local checks use Python 3.13.12 in a temporary environment with NumPy 2.5.3,
PyYAML 6.0.3, and the hash-locked repository catalog dependencies.

- Example: `python -m unittest discover -s examples/tools/nemo-helix-harness-optimization/tests`
  — 95 tests passed, no skips. Includes connection-selection and exported
  HTTP target tests.
- `python scripts/fetch_catalog_assets.py` — Mermaid asset available.
- `python scripts/build_catalog.py --validate-metadata` — 26 examples valid.
- `python scripts/build_catalog.py --write` followed by `--check` — generated
  catalog and links pass.
- `python -m unittest discover -s scripts/tests -p 'test_*.py'` — 74 tests pass.
- `node --test scripts/tests/*.test.mjs` — 14 tests pass.
- `python3 scripts/check_license_headers.py --check` — passes.
- `git diff --check` and `git diff --cached --check` — pass.
- All example Python files parse; the three Harbor verifier copies match.

No commit or remote update was requested. The post-commit `upstream/main...HEAD`
check is not applicable to this uncommitted work; this checkout has `origin`
and `fork` remotes rather than `upstream`.

Live validation completed for deployment, three CAD baselines, scoring, Intake,
both Analyst routes, Studio rendering, the retained Harbor verifier, and the HTTP
and SDK exports. See [results/helix-validation.md](results/helix-validation.md).
The baseline's valid solids failed the native-sketch and fidelity requirements;
its process success is not a CAD quality pass.

The tests exposed and fixed two example issues: the verifier's missing
`TRACE_DIR` default and the HTTP export's hardcoded service target. They also
established the source-install and virtual-environment activation requirements.
Current sample configs use the isolated walkthrough's loopback port 9080.
A human contributor should review the revised tutorial before submission.
