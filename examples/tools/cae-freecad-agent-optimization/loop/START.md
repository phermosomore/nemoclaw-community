<!-- SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Run the loop

Paste the prompt below into a fresh coding-agent session (Claude Code, Codex or another)
opened in `examples/tools/cae-freecad-agent-optimization`, after the
[Prerequisites](../README.md#prerequisites). Fill in `<run>` and the budget. It creates the
eval, then runs the loop round by round from the base agent in `agent/`. It stops for you
at each Eval Author checkpoint and once before the first round.

---

You run one harness-optimization run of the FreeCAD CAD agent, `<run>`, with a budget of
`<N>` rounds. You schedule and decide; fresh subagents do the experimenting.

1. Read `ETHOS.md`, `agent/`, `harness/`, `loop/` and the `cad-experimenter` skill
   (`npx skills add ./skills --skill cad-experimenter --agent <you> --yes`). Earlier runs
   must not shape this one: do not read `README.md` (it describes the previous eval and
   its results, and is rewritten from this run's report), `results/`, other folders under
   `experiments/`, or the git history of `evals/`.
2. Check the stack: Helix answers (`nemo --version`, the gateway lists the agent's model and
   Compass's), Docker reaches Colima, `harbor` and `compass` are installed, `.env` is filled,
   and the agent's image builds (`docker build -t cad-env -f harness/Dockerfile harness`).
   Stop and report anything that fails.
3. Create the eval, from scratch, before round 0: with the
   [Eval Author skills](https://github.com/NVIDIA-NeMo/eval-author) installed, start from
   its `eval-author` entry skill and build Harbor tasks from `ETHOS.md` alone
   (`eval-author-first-eval`): the tasks, their environment, the grader with its pass and
   its reward, and the train, val and test sets (ETHOS, Evaluation Setup). The Ethos is
   confirmed by the owner. The two hand-made parts in `parts/` (mesh and reference
   solution) belong to test. Stop for the owner at every checkpoint of the skill.
   - Every task is proven before it is accepted: the reference solution passes with reward
     1, an empty answer gets 0, and each realistic wrong model fails and scores below the
     reference solution.
   - Accepted tasks go to `evals/train`, `evals/val` and `evals/test`, with each task's
     family in `evals/splits.json` (`{"tasks": {"<task>": {"family": "..."}}}`) and the
     grader's image built from `evals/verifier` as `cad-verifier`; a task's environment
     starts from `cad-env`, and the agent saves `/app/model.FCStd`.
   - The loop reads three files a trial's verifier writes: `reward.txt` (the reward, 1 only
     on a pass), `results` (one `<check><TAB>PASS|FAIL` line per check) and `metrics.json`
     (`iou` and any other numbers). Keep that, or change `publish.py` (`grade`) and
     `loop/summary.py` with their tests in the same step.
   - This is the only point where `evals/` and its splits may change: record the task
     list, the splits and the proof in `experiments/<run>/EVAL.md`.
4. Tell the owner, in five lines: the goal (the ETHOS success criteria), the budget, the
   splits (`evals/train`, `evals/val`, `evals/test`) with one run per train task and two per
   val task, the run limit, the keep rule (the skill's). Wait for one "go".
5. Step 0, once: a frontier solve of a few train parts of different families in the agent's
   image, from the ETHOS, the instruction and the mesh alone. Write
   `experiments/<run>/FRONTIER.md`: what worked, with no numbers or shapes specific to these
   parts. Experimenters read only that.
6. Each round `N` in `experiments/<run>/round-<N>/`, with the agent under study in its
   `agent/` (round 0: a copy of `agent/`):
   - Step 1: `loop/eval.sh` on train (1 run per task); in round 0 also on val (2 runs per
     task), the baseline. A kept candidate brings its val runs with it.
   - Step 2: `loop/compass.sh` on this round's train runs. Start nothing else until
     `insights.yml` exists.
   - Step 3: Eval Author checks each Insight against the eval, and passing models against
     the Ethos ([EVAL-AUTHOR.md](EVAL-AUTHOR.md)); stop for the owner on any proposal.
     A new or fixed check is proven (NOP 0, Oracle 1, a realistic negative 0) before it
     is applied, and stored runs are regraded (`harbor jobs regrade`), never re-run.
     Decide on the new grades.
   - Step 4: two experimenter subagents with the `cad-experimenter` skill, each given a
     different area. They read train only: never `evals/val`, `evals/test` or
     `evals/splits.json`. Measure each candidate on val (2 runs per task) and on train
     (1 run per task) with `loop/eval.sh`, and apply the keep rule on val
     (`loop/summary.py CANDIDATE_VAL AGENT_VAL`).
   - Append to `experiments/<run>/LOG.md`: time stamps, results, the decision and why.
7. Never change the ETHOS, the keep rule, the splits (after step 3), the runs per task or
   the run limit during the run; log the request for the next one. A run lost to the
   infrastructure is VOID: re-run it, never count it, and stop if the same failure repeats.
8. Stop at the budget, or after two rounds in a row with no kept candidate. Read test once:
   the final agent and the base agent, 5 runs per task each (`loop/eval.sh ... test 5`), and
   write `experiments/<run>/REPORT.md`: the eval and its proof, every round and decision,
   the Insights and what resolved each, and the final agent against the base agent: runs
   passed, mean reward, and tokens per run and per passed run.
