<!-- SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Live Helix validation — 2026-09-24

This record covers execution of the migrated example, not an improvement claim.
The three CAD baseline runs completed, were scored independently, and produced
Intake traces. The standalone Analyst found four problems in those traces.
All three CAD outputs failed the full task criteria despite successful agent
invocations. Eval Author and automatic candidate generation remain unavailable.

## Environment and installation

| Component | Observed version or configuration |
| --- | --- |
| Host | macOS 26.5.2, ARM64 |
| FreeCAD | 1.1.3 GUI, local RPC |
| MCP client | freecad-mcp 0.1.24, text feedback |
| Helix source | `b6ff571721eadd2b85c939c9c8e3405ab9b3ae44`, clean checkout |
| Source lock SHA-256 | `642bfc5cb3d0db57b7f614d1f6dd5da7fcd45725fd2b458c925372347dd2404a` |
| Helix CLI | `0.0.0.post1.dev0+b6ff571` (source build, not a released version) |
| Python | 3.12.12 for Helix; 3.13.12 for standalone Analyst |
| Fabric / Deep Agents / Relay | 0.3.0 / 0.7.9 / 0.7.3 |
| Harbor | 0.20.0 |
| Standalone Analyst source | `3a06bce1298190cd143a96880d6999052086632d` |
| Helix's Analyst dependency | `cd639d223e06ee9d27783df6b461d302ceb09137` |
| Build tools | uv 0.12.18, Node.js 22.23.2, pnpm 10.34.5 |
| Service isolation | Separate state and client config, loopback port 9080 |
| Inference | Existing configured provider registered in the new instance; fixed CAD model across baseline runs. Provider credentials and private endpoint details are omitted. |

The existing service on port 8080 and pre-existing FreeCAD documents were left
in place. Test documents used the unique names below. Raw traces, logs, runtime
configs, and responses are retained locally under the ignored
`results/runs/helix-validation/` directory; they are not publication artifacts.

Both source bootstrap targets completed against the committed lock. The
standalone Analyst installed at its pinned revision and accepted `analyst.yaml`
through its actual configuration model. Its Intake loader successfully read
the selected live trace window.

Installation and startup issues discovered and resolved:

1. The advertised `nemo-helix[all]` package had no available version on the
   configured package index. Use the pinned source bootstrap in the README.
2. The host's uv 0.10.8 did not meet Helix's minimum. The build used isolated
   uv 0.12.18 instead.
3. Starting services via the venv executable without activation made Fabric
   select the system interpreter. Setting PATH alone did not fix it. Activating
   the venv, including `VIRTUAL_ENV`, fixed the missing adapter import.
4. Studio returned 503 before its assets were built and loaded. After building
   and restarting, the dashboard returned 200 and rendered in Chromium without
   page errors.
5. The exported HTTP client assumed port 8080. It now takes the selected Helix
   URL and workspace from arguments or `NHX_*` settings; the live export returned
   `READY` from the test deployment on port 9080.

## Baseline results

The agent ran the unchanged mesh reconstruction instruction in three separate
invocations, serially against one FreeCAD GUI. The document name and absolute
mesh path were the only task substitutions. The scorer ran afterward, outside
the agent. Each invocation exited 0 with a nonempty response; each scorer exited
0 with the reported IoU.

| Document | Agent wall time | IoU | Intake spans | Tokens |
| --- | ---: | ---: | ---: | ---: |
| EvalHelix1 | 225.67 s | 0.8436 | 151 | 447,195 |
| EvalHelix2 | 177.36 s | 0.4911 | 135 | 306,266 |
| EvalHelix3 | 241.10 s | 0.2872 | 191 | 521,905 |

The mean IoU is 0.5406. Three runs on one mesh do not establish a general success
rate. No baseline reached the 0.85 geometric target.

Independent FreeCAD inspection found one valid solid in each document, but
**zero native `Sketcher::SketchObject` objects** in all three. Objects named
like sketches and operations were generic `PartDesign::Feature` objects.
There were consequently no native named sketch dimensions to exercise with
the planned change/recompute/restore test. Custom properties are not evidence
of an editable sketch-driven model. These are CAD task failures, not passing
results hidden behind successful process exit codes.

## Analysis

Standalone `insight-agent` queried Helix Intake for only the three baseline
traces between 08:48:31 and 08:59:20 UTC, with the example's ethos and sentiment
analysis disabled. It exited 0 and saved four trace-linked findings:

- Models use generic features instead of native sketch-driven PartDesign.
- Named dimensions do not reliably demonstrate regeneration.
- Save/reopen persistence was not tested.
- Mesh characterization was incomplete before choosing dimensions.

The native-sketch finding agrees with the independent object-type inspection.
The persistence finding describes missing evidence; it does not prove that
saving or reopening would fail. Review generated findings against the actual
task before turning them into evaluation requirements.

The first Helix-integrated analysis job completed and reported three traces
analyzed, with zero new Insights. It used a different, faster model for evidence
analysis. That is successful job execution, not proof that the baseline has no
problems. A second run using the stronger model for both stages completed and persisted
three Insights in Helix: native PartDesign construction, dimension-driven
regeneration, and unverified persistence. It analyzed four traces: the three
CAD runs plus the later tool-free HTTP export readiness check. The findings
reference only the CAD traces. Model settings and the extra trace differ, so
this comparison does not isolate why the first run returned no findings.

## Harbor and exports

The first standalone Harbor trial executed the agent, found its unique Intake
trace, and measured IoU 0.6149. Its container verifier then failed because
`TRACE_DIR` was absent: the retired optimizer used to provide it. All three
verifier entry points now default it to `/app/traces`, preserving an explicit
override. A fresh full trial after the fix completed in about four minutes: one
completed trial, zero errors, and reward `{"eval_iou": 0.5705}` matching the
host score in the agent metadata. This verifies measurement plumbing; 0.5705
does not meet the geometric target.

Harbor returned process exit code 0 even with an errored trial. Always inspect
its `result.json`: a successful verification requires zero errored trials,
a completed trial, and the expected `eval_iou` reward.

The exported HTTP client and standalone SDK runner both returned `READY`.
The SDK runner connected to the live FreeCAD MCP server and discovered 17 tools.
The dcode files were generated and their shell syntax checked; its interactive
TUI was not exercised.


## Repository checks after the fixes

- Example unit suite: 95 tests passed, no skips.
- Catalog metadata validation, generation, and generated-source checks: passed for 26 examples.
- Repository suites: 74 Python tests and 14 JavaScript tests passed.
- License headers: all 905 publication source files passed (tracked and nonignored new files). The unrestricted scanner also traverses ignored local environments and generated run artifacts, which are excluded from this publication check.
- Staged and unstaged whitespace checks passed. All three verifier scripts are identical and pass Bash syntax checks.
- Final live health check: both existing and isolated service endpoints responded HTTP 200; Studio responded HTTP 200. FreeCAD retained the two original documents and all three baseline documents.

The remaining end-to-end gap is the unavailable Eval Author and replacement
proposal skill. No authored behavioral suite or automatic improvement claim is
made. The baseline's CAD failures are observed and diagnosed. A subsequent
[candidate optimization experiment](optimization-validation.md) implements a
local study-driver alternative and records the measured trade-offs.
