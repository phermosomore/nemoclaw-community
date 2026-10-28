# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
# The agent's image every task's environment/Dockerfile starts from (adding the task's mesh):
# headless FreeCAD 1.1.3 from the same layer as the verifier image, a virtual display so
# FreeCAD can render images (`xvfb-run -a freecadcmd`), and the Deep Agents runtime and NeMo
# Relay for traces. Build it before a run:
#   docker build -t cad-env evals/environment
FROM condaforge/miniforge3:24.11.3-2
RUN mamba install -y -q python=3.12 freecad=1.1.3 numpy && mamba clean -a -y
RUN apt-get update -qq && apt-get install -y -qq xvfb xauth libgl1 libegl1 libxkbcommon-x11-0 \
    libxcb-cursor0 > /dev/null && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir deepagents==0.7.32 langchain-openai==1.7.3 nemo-relay==0.11.0
WORKDIR /app
