<!-- SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Local candidate optimization — 2026-09-24

This experiment follows the live Analyst findings with real CAD candidate
execution. It reuses Helix commit `b6ff571721eadd2b85c939c9c8e3405ab9b3ae44`,
its installed Deep Agents adapter, and the unchanged mesh, task and IoU scorer.
The source checkout was not patched. The local integration is in
[optimization/](../optimization/README.md).

## What the current machinery actually supports

- Helix's Optuna study driver accepts a `CandidateEvaluator`. We connected that
  interface to sequential Helix agent invocation and independent CAD scoring.
- Its stock Fabric evaluator only accepts the implemented judge/tool metrics;
  it does not accept our external IoU scorer directly.
- The genetic prompt backend is a stub. A direct probe returned `failed` and
  `optimizer.prompt.enabled is not supported yet`.
- The stock skills workflow assumes Claude Code traces and a `reward` field.
  Parsing our successful Harbor trial with `eval_iou: 0.5705` returned `ERROR`
  with no reward. It is not a compatible quality optimizer without adaptation.
- Declarative sub-agents are supported. However, the installed adapter rejects
  a per-subagent `tools` override. Review-only behavior is instruction-driven;
  sub-agents inherit parent tools. Custom middleware passthrough is rejected too.

The four screening candidates are authored from the Analyst findings, not
emitted by an automatic proposal model: baseline, stricter system prompt,
prompt plus native-CAD skill, and that skill plus a planning reviewer.
Model and sampling settings are held fixed. This is a progressive comparison,
not a factorial attribution study or a search over every possible architecture.

## Independent acceptance checks

The raw metric remains the original geometric IoU. The optimizer's objective
is that IoU gated on a valid body solid, real sketches and native profile-based
features, measurable named-dimension regeneration with restoration, and
save/reopen persistence. A structurally invalid result receives zero objective
regardless of its raw IoU. The geometric target remains 0.85.

The checker was calibrated during screening before confirmation:

1. Local workspace paths must be relative; an initial startup failed before inference.
2. FreeCAD constraints expose their name as `Constraint.Name`, not
   `SketchObject.getConstraintName`. The original screening study stopped on
   that audit exception; it was not reported as a successful optimization job.
3. A valid candidate used spreadsheet aliases rather than sketch constraints.
   The audit now supports expression-linked properties and literal spreadsheet
   aliases as well as named sketch constraints.
4. Recomputing the restored prompt model changed volume from about 325.018077
   to 325.017770 despite restoring its radius exactly. The audit now uses a
   `1e-5` relative volume tolerance with a `1e-6` absolute floor, rather than
   rejecting ordinary kernel recomputation noise.

All three saved screening models were re-audited with the corrected checker.
Earlier audit records were retained locally. The task, mesh and geometric
scorer were not changed. The corrected runner itself is included in the input
hash manifest for subsequent live trials.

## Screening

| Candidate | Raw IoU | Native/parameter/persistence checks | Gated objective |
| --- | ---: | --- | ---: |
| Baseline | 0.6643 | Fail: no native sketches/features | 0.0000 |
| System prompt | 0.5447 | Pass; named `HandleRadius` drives geometry | 0.5447 |
| Prompt + skill | 0.7164 | Pass; spreadsheet `Parameters.OuterHeight` drives geometry | 0.7164 |
| Skill + reviewer | 0.5868 | Fail: no qualifying named driving dimension | 0.0000 |

The skill model contains 12 real sketches and three native profile-based
features; the prompt model has 19 and three, respectively. Both are valid
single solids and survive saving and reopening. The skill trace confirms an
actual `read_file` call on `/skills/native-cad/SKILL.md`.

The reviewer was actually invoked through `task` with `subagent_type`
`cad-plan-reviewer`. It took 364.91 seconds including host scoring/audit,
versus 260.41 for the skill candidate. Intake reports 452,661 total tokens
for the reviewer trial versus 252,904 for the skill trial. One trial cannot
establish a general effect of delegation, but it gives no reason to select
this reviewer configuration.

## Confirmation

Two fresh trials per arm compare the baseline with the screening leader,
prompt + skill, using the corrected checker frozen. No candidate has been
promoted.

| Candidate | Raw IoU repeats | Structural passes | Mean gated IoU |
| --- | --- | --- | ---: |
| Baseline | 0.5399, 0.6219 | 1/2 | 0.26995 |
| Prompt + skill | 0.5643, 0.5334 | 2/2 | 0.54885 |

The Helix study completed both configurations with two repeats each and
selected `skill` on its gated objective. **This is not an overall geometric
improvement:** mean raw IoU decreased from 0.58090 to 0.54885 (−0.03205), while
the structural pass count improved from 1/2 to 2/2. Both means remain below
0.85. The candidate is retained for review, not promoted to replace the
baseline. More accurate native geometry is the next search objective; a
higher gated score alone does not justify accepting a fidelity regression.
The skill confirmations also averaged 244.65 seconds including scoring/audit
versus 183.73 seconds for baseline, and 392,735 Intake-reported tokens versus
185,592 (rounded). No latency or token-efficiency improvement is claimed.

Eight live CAD reconstructions were measured in total: four screening
candidates and four confirmation runs. Startup-only failures and re-audits
of saved models are not counted as additional reconstructions. All eight have
correlated Intake traces. The successful confirmation study used the frozen
checker and verified hashes of the original mesh, task, scorer, and runner
after every invocation. No upstream source changes were needed.

Raw configs, traces, logs, models, and study artifacts are retained locally
under the ignored `results/runs/optimization-2026-09-24/` directory. The
`study/optimized_config.yml` is a candidate-selection record; use each trial's
materialized `agent.yaml` and workspace to inspect what actually ran.

## Verification

- Example unit suite: 98 passed.
- Repository suites: 74 Python tests and 14 JavaScript tests passed.
- Publication-source SPDX check: 908 files passed.
- Catalog metadata and generated-source checks: passed for 26 examples.
- Staged and unstaged whitespace checks: passed.
- Final health: both service endpoints and Studio returned HTTP 200; FreeCAD retained the five pre-existing documents and all experimental models were saved and closed.
- No deployment replacement or publication was performed.

All trials use one mesh. Repeated trials measure repeatability, not
performance on unseen shapes. The structural checks test concrete properties;
they do not establish that every dimension is fully constrained or editable.
