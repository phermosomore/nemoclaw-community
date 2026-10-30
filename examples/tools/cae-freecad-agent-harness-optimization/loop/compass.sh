#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
# loop/compass.sh ROUND_DIR: NeMo Compass (analyst.yaml) on the train runs in ROUND_DIR/runs
# (loop/eval.sh, their time window in Intake), with ROUND_DIR/agent as the code base, then the
# Insights to Studio (README Step 2). Writes ROUND_DIR/insights.yml, copied to
# ROUND_DIR/../insights.yml for the next round's --existing-insights.
set -eu
D=$(cd "$1" && pwd); shift; RUN=$(dirname "$D")
[ -f "$RUN/insights.yml" ] && set -- --existing-insights "$RUN/insights.yml"
cd "$(dirname "$0")/.."   # the example root: analyst.yaml, publish.py, .env
[ -f .env ] && { set -a; . ./.env; set +a; }
NAME=$(sed -n 's/^name: *//p' "$D/agent/agent.yaml")   # the agent name its traces carry
compass --config analyst.yaml --code-base "$D/agent" "$@" --output-path "$D/insights.yml" \
  --trace.intake.base-url "${NHX_BASE_URL:-http://localhost:8080}" --trace.intake.workspace "${NHX_WORKSPACE:-default}" \
  --trace.intake.query.agent-name "$NAME" --trace.intake.query.started-at-gte "$(cat "$D/runs/train.started")" \
  --trace.intake.query.started-at-lte "$(cat "$D/runs/train.ended")" > "$D/compass.out" 2>&1
uv run -q --with pyyaml python publish.py insights "$D/insights.yml" --agent "$NAME" > "$D/insights.out" 2>&1
cp "$D/insights.yml" "$RUN/insights.yml"   # now with each Insight's Studio ID
