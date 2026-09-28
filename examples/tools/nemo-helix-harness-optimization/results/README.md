<!-- markdownlint-disable MD013 -->
<!-- SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- markdownlint-enable MD013 -->

# Shipped artifacts and reference measurements

See [live Helix validation](helix-validation.md) for the current installation,
CAD baseline, analysis, and Harbor results, and
[candidate optimization](optimization-validation.md) for the subsequent search.

The historical artifacts and measurements below predate the Helix migration. They preserve the
original experiment's provenance and failure analysis; they are not Helix
validation results or evidence that its removed optimizer still runs.

| Artifact | Historical purpose |
| --- | --- |
| [geometry-fidelity-policy](candidates/geometry-fidelity-policy/SKILL.md) | Candidate skill |
| [system-prompt.yaml](candidates/system-prompt.yaml) | Candidate system instructions |
| [subagent.yaml](candidates/subagent.yaml) | Candidate subagent configuration |
| [runs.json](runs.json) | Three runs per arm, recorded on 2026-09-18 |
| [optimization-run.md](optimization-run.md) | Original optimization observations and failures |
| [legacy-config/](legacy-config/) | Removed optimizer profiles, retained as non-executable text |

Candidate configs retain historical runtime settings. Reapply only the intended
instructions, skills, or subagents to the current baseline and remeasure before
promotion. Do not copy the historical model or telemetry settings blindly.

What follows is the fine print on `runs.json`.

## What these numbers are not

- **n = 3 per arm.** Enough to show a difference this size, nowhere near enough
  to resolve a small one.
- **One host, one FreeCAD session, one model, one day.** No claim is made about
  any other model, machine or FreeCAD version.
- **Not a leaderboard.** One agent configuration against another on one task. It
  does not rank models or CAD agents.
- **Specific to this reference mesh.** The scorer does not align poses, so a
  different mesh is a different measurement, not a different score on the same
  one.
- **Three of six runs returned HTTP 502** at the gateway's 300-second cap while
  the agent kept working. Those documents were built and scored; the 502 is a
  client-side timeout, not a failed run.
