<!-- SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# CAD candidate optimization with Helix

This local integration reuses Helix's Optuna `run_numeric_study` and
`CandidateEvaluator` interface. It invokes the existing Deep Agents CAD agent
through Helix, evaluates geometry with the unchanged `scorer/score.py`, and
checks native parametric construction independently through FreeCAD RPC.
It does not patch Helix or claim that its built-in optimize CLI accepts CAD IoU.
The integration depends on internal APIs at Helix commit
`b6ff571721eadd2b85c939c9c8e3405ab9b3ae44`.

See [live measurements](../results/optimization-validation.md) for the tested
candidates and compatibility probes.

## What is currently usable

| Surface | Current support and this example's approach |
| --- | --- |
| System prompt | Compare fixed prompt candidates using categorical search. Helix's separate genetic prompt backend is a stub returning `failed`, not a working prompt generator. |
| Skills | Compare actual skill files staged into each candidate workspace. The stock `optimize-skills` workflow assumes Claude Code traces and a `reward` field; our Harbor output uses `eval_iou`. Its unmodified parser marks our successful Harbor trial as an error. |
| Sub-agents | Deep Agents accepts configured sub-agents. The reviewer candidate instructs one sub-agent to review plans without calling tools. The current adapter forbids a per-subagent `tools` override, so it inherits parent tools; this role is prompt-guided, not an enforced isolation boundary. Inspect traces to verify behavior. |
| Middleware | Arbitrary middleware objects are rejected by the current Fabric Deep Agents configuration adapter. This sweep does not claim to optimize custom middleware. |
| Model/parameters | The adapter supports model selection and temperature. They are held fixed in this first experiment to isolate instruction and architecture changes. |
| Objective | The built-in optimizer evaluator supports judge and tool-use metrics, not external CAD IoU. Our local `CandidateEvaluator` supplies measured CAD scores to the existing study driver. |

## Candidates and objective

The four candidates form a progressive comparison, not a factorial experiment:

1. `baseline`: the original instructions, no added skill or reviewer.
2. `prompt`: explicit native sketch/feature and dimension requirements.
3. `skill`: the prompt plus a native-CAD construction skill.
4. `reviewer`: the skill candidate plus one planning sub-agent.

These candidates were authored from the Analyst findings; Helix searches among
them. It does not generate their content. The categorical search path
`metadata.name` is a candidate identifier interpreted by this adapter. The
study's `optimized_config.yml` contains that selection, **not a deployable agent
package**. Each trial directory contains the full materialized `agent.yaml` and
workspace that were actually executed.

Raw IoU is always recorded. The selection objective is IoU only when all of
these independently checked conditions pass; otherwise it is zero:

- one valid body solid;
- at least one real `Sketcher::SketchObject` and native profile-based feature;
- a named sketch dimension, expression-linked property, or spreadsheet alias can change final solid volume and restore it;
- the model survives saving and reopening with the same volume and sketch count.

These are concrete behavioral checks, not a complete proof of editability.
The dimension test checks named length/radius constraints and expression-linked
length, distance or float properties and literal spreadsheet aliases for volume changes; it does not prove every
dimension is functional or cover edits that preserve volume.
Volume comparisons use a relative tolerance of `1e-5` (absolute floor `1e-6`)
to distinguish changes from OpenCascade recomputation noise. A candidate can still fail the geometric target of 0.85 despite passing these
structural checks. Never select a zero-score tie as an improvement.

## Run

Start FreeCAD RPC and the configured Helix instance as described in the parent
README. Activate the tested Helix source virtual environment. Supply a working
copy of `harness/agent_source/agent.yaml` with your model, MCP executable and
Intake endpoint configured. Use the supplied empty-workspace baseline: the runner
creates fresh workspaces and does not import an arbitrary agent’s existing files.
Keep credentials outside the file.

```bash
export NEMO_AGENTS_IGW_API_KEY=local-no-auth  # only for an unauthenticated local gateway
python optimization/run_study.py \
  --agent-config /absolute/path/to/configured/agent.yaml \
  --output /absolute/path/to/new-study-directory \
  --repeats 1
```

Use `--arms baseline skill --repeats 3` for a fresh repeated comparison after
screening. Output directories must not already exist. Each run uses fresh
random document names. A shared `CAD_TRIAL_LOCK` (default
`cad-harness-trial.lock` under the system temporary directory) prevents overlap with the Harbor wrapper.
Do not launch other manual FreeCAD reconstructions during a study.

The original mesh, task and scorer are hashed and checked after each trial.
The runner saves experimental documents into their trial folders and closes
those documents after auditing; existing user documents are not selected by
the evaluator. Agent tool execution still has the same host access as the
parent example. Infrastructure failures abort the study rather than becoming
misleading low scores.

Inspect `measurements.json`, `summary.json`, per-trial logs and saved `.FCStd`
files, and the study's trial table. A winning screening trial is provisional:
repeat both it and the baseline before promotion. This example does not
replace the deployed baseline automatically. All runs use the same mesh, so
repetitions test repeatability, not generalization to new shapes.
