# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Run the CAD agent in a task container: Deep Agents with a shell in /app, traced
with NeMo Relay to Intake.  python run_agent.py AGENT_DIR INSTRUCTION

The agent's model and each subagent's `model:` are names on the Helix inference gateway.
"""

import asyncio
import os
import re
import runpy
import subprocess
import sys
from pathlib import Path

import yaml
from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend
from deepagents.middleware.subagents import GENERAL_PURPOSE_SUBAGENT
from langchain.agents.middleware import ModelRetryMiddleware
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain_openai import ChatOpenAI
from nemo_relay import ScopeType, plugin, scope
from nemo_relay.integrations.deepagents import add_nemo_relay_integration
from nemo_relay.observability import (AtifConfig, ComponentSpec, HttpStorageConfig,
                                      ObservabilityConfig)
from nemo_relay.plugin import PluginConfig

# Set by the task (task.toml [environment].env): the run's time limit, and NeMo Helix
# as the container reaches it (inference gateway for the model, Intake for traces).
TIMEOUT = int(os.environ['CAD_AGENT_TIMEOUT'])
HELIX = os.environ['CAD_HELIX_URL'].rstrip('/')
WORKSPACE = os.environ.get('NHX_WORKSPACE', 'default')
GATEWAY = f'{HELIX}/apis/inference-gateway/v2/workspaces/{WORKSPACE}/openai/-/v1'
INTAKE = f'{HELIX}/apis/intake/v2/workspaces/{WORKSPACE}/ingest/atif'


def transient(error: Exception) -> bool:
    """A gateway blip worth retrying, not a request that will fail again."""
    text = str(error)
    return (any(s in text for s in ('Connection error', 'Connection closed', 'timed out',
                                    'Timeout', 'Rate limit'))
            or re.search(r'\b(500|502|503|504)\b', text) is not None)


def gateway_model(name: str) -> ChatOpenAI:
    # The Helix inference gateway needs no key; the client requires one. Streamed, because
    # the trial's egress proxy closes a connection that is idle for about 15 s, which cut
    # off every longer non-streamed answer.
    return ChatOpenAI(model=name, base_url=GATEWAY, api_key='unused', streaming=True,
                      stream_usage=True)


async def main(agent_dir: str, instruction: str) -> None:
    spec = yaml.safe_load((Path(agent_dir) / 'agent.yaml').read_text())
    model = os.environ.get('CAD_MODEL') or spec['model']
    # Harness, not agent: ride out model-gateway blips and a busy backend, in the agent and
    # in every subagent. The client's own retries did not catch them (they surfaced through
    # NeMo Relay's wrapper and ended the run).
    def retry():
        # About two minutes of backoff: a backend outage of a minute costs a minute, not the run.
        return ModelRetryMiddleware(max_retries=6, initial_delay=2.0, max_delay=60.0,
                                    retry_on=transient)

    subagents = [{**s, 'middleware': [retry(), *s.get('middleware', [])],
                  **({'model': gateway_model(s['model'])} if 'model' in s else {})}
                 for s in spec.get('subagents') or []]
    if not any(s['name'] == GENERAL_PURPOSE_SUBAGENT['name'] for s in subagents):
        # Deep Agents adds this one itself, without the agent's middleware.
        subagents.append({**GENERAL_PURPOSE_SUBAGENT, 'middleware': [retry()]})
    # Optional: agent/middleware.py exports MIDDLEWARE, a list of Deep Agents middleware.
    extra = Path(agent_dir) / 'middleware.py'
    middleware = [retry(), *(runpy.run_path(str(extra))['MIDDLEWARE'] if extra.exists() else [])]
    agent = create_deep_agent(**add_nemo_relay_integration(
        name=spec['name'], system_prompt=spec['system_prompt'], subagents=subagents,
        skills=[f'{agent_dir}/skills/'], middleware=middleware, model=gateway_model(model),
        # The agent's shell gets the container's environment without the Helix settings,
        # so the agent uses the models it is given, not others on the gateway.
        backend=LocalShellBackend(root_dir='/app', virtual_mode=False, timeout=TIMEOUT, env={
            k: v for k, v in os.environ.items() if not k.startswith(('CAD_', 'NHX_'))})))
    tools = [convert_to_openai_tool(t)['function']
             for t in agent.nodes['tools'].bound.tools_by_name.values()]
    atif = AtifConfig(enabled=True, agent_name=spec['name'], model_name=model,
                      tool_definitions=tools,
                      # Relay's default 3 s is shorter than Intake takes to ingest a long trace.
                      storage=[HttpStorageConfig(endpoint=INTAKE, timeout_millis=60_000)])
    config = PluginConfig(components=[ComponentSpec(config=ObservabilityConfig(atif=atif))])
    async with plugin.activate(config):
        with scope.scope(spec['name'], ScopeType.Agent) as run:
            print(f'trace {run.uuid}', flush=True)  # the Intake trace ID, for publish.py
            try:
                await asyncio.wait_for(agent.ainvoke(
                    {'messages': [{'role': 'user', 'content': instruction}]}), TIMEOUT)
            except TimeoutError:
                print(f'stopped after {TIMEOUT} s', flush=True)
    # Time is up and the trace is sent: stop any FreeCAD still running, so nothing is
    # saved after the limit, and exit without waiting for its shell command.
    subprocess.run(['pkill', '-9', 'freecadcmd'])
    os._exit(0)


if __name__ == '__main__':
    asyncio.run(main(*sys.argv[1:3]))
