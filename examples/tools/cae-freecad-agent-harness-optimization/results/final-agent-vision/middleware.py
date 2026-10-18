# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""A clock for the agent, and a review of every saved model.

Clock: the model cannot see wall time, and the run is stopped after CAD_AGENT_TIMEOUT
seconds wherever it is, so runs ended mid-build with no report.

- Every tool result ends with `[clock: N s of LIMIT used]`.
- A shell command's timeout is capped so it returns before the stop, leaving time to report.
- From WRAP_AT seconds on, the model is told once to stop building and report.
- A shell command that copies, moves or redirects a file onto /app/model.FCStd is refused: only
  the build's save writes the model, and it keeps the better one.

Review (from experimenter C's cad-v10c): after a tool call that changes /app/model.FCStd, the
saved model is verified (verify-model's verify.py), rendered beside the mesh and cut on flat
sections (review/render.py, review/sections.py), and Nemotron 3.5 Super VL compares mesh and
model feature by feature for what a designer would object to. The check numbers and its
findings are appended to that tool result. Keep the best: a save worse than the best one so
far (not one clean solid, or a lower IoU estimate without becoming complete) is moved aside
and the best model restored. The review measures and describes; the agent decides the
features and writes the model.
"""
import asyncio
import base64
import json
import os
import re
import shlex
import shutil
import time
from pathlib import Path

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

START = time.monotonic()            # loaded by run_agent.py when the run starts
LIMIT = int(os.environ.get('CAD_AGENT_TIMEOUT', '300'))
WRAP_AT = LIMIT - 60                 # leave time for one verify or one last report
RESERVE = 25                         # seconds kept free after any shell command


def _used():
    return int(time.monotonic() - START)


def _stamp(result):
    if isinstance(result, ToolMessage) and isinstance(result.content, str):
        result.content = f'{result.content}\n[clock: {_used()} s of {LIMIT} used]'
    return result


GUARD_NOTE = ('Refused: /app/model.FCStd is written only by the build\'s save, which keeps the '
              'better model; copying, moving or redirecting a file onto it can replace a good model '
              'with a worse one. Save a new model through the build, or leave the saved one.')


def _overwrites_model(command):
    """A shell command that copies, moves or redirects onto /app/model.FCStd."""
    for part in re.split(r'[;&|\n]+', command):
        if re.search(r'>\s*\S*model\.FCStd\b', part):
            return True
        try:
            words = shlex.split(part)
        except ValueError:
            words = part.split()
        while words and ('=' in words[0] or words[0] in ('sudo', 'command', 'timeout')
                         or words[0].isdigit()):
            words = words[1:]
        if (len(words) >= 3 and words[0] in ('cp', 'mv', 'install', 'rsync')
                and words[-1].endswith('model.FCStd')):
            return True
    return False


def _refused(request):
    call = request.tool_call
    if call.get('name') == 'execute' and _overwrites_model(str((call.get('args') or {}).get('command', ''))):
        return ToolMessage(content=GUARD_NOTE, tool_call_id=call['id'], name='execute')
    return None


def _cap(request):
    call = request.tool_call
    if call.get('name') == 'execute':
        left = max(LIMIT - RESERVE - _used(), 5)
        args = dict(call.get('args') or {})
        try:
            t = int(float(args.get('timeout') or left))
        except (TypeError, ValueError):
            t = left
        args['timeout'] = min(t, left)
        call['args'] = args
    return request


WRAP_NOTE = (f'[clock] About 60 s of the {LIMIT} s run are left. Stop building now. /app/model.FCStd '
             'holds the best valid model saved so far. Report now, without new tool calls: the '
             'features, the named dimensions and the last SAVED / VERDICT numbers you have seen.')


class Clock(AgentMiddleware):
    def __init__(self):
        super().__init__()
        self.warned = False

    def wrap_tool_call(self, request, handler):
        return _stamp(_refused(request) or handler(_cap(request)))

    async def awrap_tool_call(self, request, handler):
        return _stamp(_refused(request) or await handler(_cap(request)))

    def _note(self, state):
        if not self.warned and _used() >= WRAP_AT:
            self.warned = True
            return {'messages': [HumanMessage(content=WRAP_NOTE)]}
        return None

    def before_model(self, state, runtime):
        return self._note(state)

    async def abefore_model(self, state, runtime):
        return self._note(state)


HERE = Path(__file__).resolve().parent
APP = Path('/app')
MODEL, MESH, OUT = APP / 'model.FCStd', APP / 'reference.obj', APP / 'review'
VISION = 'nvidia-nvidia-nemotron-3-5-super-vl'
NOISE = ('FreeCAD', '(C)', 'Importing', 'Postprocessing', 'Recompute', 'Refine failed')

VISION_SYSTEM = """You review a CAD model against the target mesh it was built to match, as a design
engineer would before accepting it. Describe geometry only: never name or guess what object the part
is, and never use an object's name for a feature, not even in parentheses; call features only main
form, branch, boss, hole, cavity, rim, floor, wall or end, with where they are.

Image 1 is a render: one row per view (iso, front, right, top), same camera in each row; columns
mesh (blue), model (orange), and their silhouette difference (grey both, blue mesh only, red model
only). Image 2 shows flat sections, one row per plane (title `x=`, `y=` or `z=` in mm): the mesh's
section (blue), the model's (orange), their difference (grey both, blue mesh only, red model only).
Answer from the images only; if you cannot tell, say "cannot tell"."""

ASK = """Section areas per plane (mm^2):
{areas}

Compare the model with the mesh, feature by feature (main form, each branch, boss, hole, cavity,
rim, floor, wall, end): is each feature there, in the same place, reaching as far, running the same
way, with the same section? Then look over the model's surfaces in the render and the sections for
anything a designer would object to that the mesh does not have: bulges, notches, creases, seams,
steps, ridges, or a feature that is missing, kinked, shifted, too short or has the wrong section.
Say where each one is (view or plane, and which side).
End with the differences that matter, largest first, at most five, one per line:
`DIFF: <feature or plane> | mesh: <what the mesh shows> | model: <what the model shows>`
or the single line `DIFF: none`."""


def _png(path):
    return {'type': 'image_url',
            'image_url': {'url': 'data:image/png;base64,' + base64.b64encode(path.read_bytes()).decode()}}


async def _run(cmd, env, timeout):
    """A command's output, or None if it did not finish in time."""
    p = await asyncio.create_subprocess_exec(*cmd, cwd='/app', env={**os.environ, **env},
                                             stdout=asyncio.subprocess.PIPE,
                                             stderr=asyncio.subprocess.STDOUT)
    try:
        out, _ = await asyncio.wait_for(p.communicate(), max(5, timeout))
    except TimeoutError:
        p.kill()
        return None
    return out.decode(errors='replace')


def _sig(p):
    try:
        st = p.stat()
        return st.st_mtime_ns, st.st_size
    except OSError:
        return None


def _bbox():
    lo, hi = [float('inf')] * 3, [float('-inf')] * 3
    with open(MESH) as f:
        for ln in f:
            if ln.startswith('v '):
                v = [float(c) for c in ln.split()[1:4]]
                lo, hi = [min(a, b) for a, b in zip(lo, v)], [max(a, b) for a, b in zip(hi, v)]
    return lo, hi


def planes():
    """Three planes across the mesh's longest direction (at 1/4, 1/2 and 3/4) and the mid planes of
    the other two directions: the review picks where to cut, never what to build."""
    lo, hi = _bbox()
    longest = max(range(3), key=lambda i: hi[i] - lo[i])
    out = [f'{"xyz"[longest]}={lo[longest] + t * (hi[longest] - lo[longest]):.2f}' for t in (0.25, 0.5, 0.75)]
    out += [f'{"xyz"[i]}={(lo[i] + hi[i]) / 2:.2f}' for i in range(3) if i != longest]
    return out


def _verdict(out):
    """(one clean solid, IoU estimate) from verify.py's VERDICT line; (None, None) if absent."""
    m = re.search(r'VERDICT .*one clean solid (True|False) .*IoU est ([\d.]+)', out or '')
    return (m.group(1) == 'True', float(m.group(2))) if m else (None, None)


def _complete():
    """Whether cadkit's last save called the model complete (its status file, if newer than the model)."""
    st = APP / '.model_status.json'
    try:
        if st.stat().st_mtime_ns >= MODEL.stat().st_mtime_ns - 5e9:
            return bool(json.loads(st.read_text()).get('complete'))
    except (OSError, ValueError):
        pass
    return False


class Review(AgentMiddleware):
    def __init__(self):
        super().__init__()
        self.lock = asyncio.Lock()
        self.seen = _sig(MODEL)
        self.best = None                   # (iou, complete) of the model kept in OUT/best.FCStd
        self.n = 0
        self._vision = None

    def vision(self):
        if self._vision is None:
            from langchain_openai import ChatOpenAI
            helix = os.environ['CAD_HELIX_URL'].rstrip('/')
            ws = os.environ.get('NHX_WORKSPACE', 'default')
            self._vision = ChatOpenAI(
                model=VISION, api_key='unused', streaming=True, stream_usage=True, max_retries=0,
                base_url=f'{helix}/apis/inference-gateway/v2/workspaces/{ws}/openai/-/v1')
        return self._vision

    async def ask(self, question, images, timeout):
        """Vision's answer, or why there is none (one try: a busy provider costs a minute)."""
        try:
            msg = HumanMessage(content=[{'type': 'text', 'text': question}, *map(_png, images)])
            r = await asyncio.wait_for(self.vision().ainvoke([SystemMessage(VISION_SYSTEM), msg]), timeout)
            c = r.content
            return c if isinstance(c, str) else ''.join(
                b.get('text', '') if isinstance(b, dict) else str(b) for b in c)
        except Exception as e:  # noqa: BLE001
            return f'(vision unavailable: {type(e).__name__} {str(e)[:120]})'

    async def look(self, tag, budget):
        look, sec = OUT / f'look-{tag}.png', OUT / f'sections-{tag}.png'
        base = {'MESH': str(MESH), 'MODEL': str(MODEL)}
        _, s = await asyncio.gather(
            _run(['xvfb-run', '-a', '-s', '-screen 0 1600x1200x24', 'freecadcmd', str(HERE / 'review' / 'render.py')],
                 {**base, 'OUT': str(look)}, min(60, budget)),
            _run(['freecadcmd', str(HERE / 'review' / 'sections.py')],
                 {**base, 'OUT': str(sec), 'PLANES': '; '.join(planes())}, min(60, budget)))
        areas = '\n'.join(ln for ln in (s or '').splitlines() if ': mesh area' in ln or 'no section' in ln)
        imgs = [p for p in (look, sec) if p.exists()]
        if len(imgs) < 2:
            return areas, '(vision skipped: render or sections failed)'
        return areas, await self.ask(ASK.format(areas=areas), imgs, max(10, min(70, LIMIT - RESERVE - _used())))

    async def review(self):
        self.n += 1
        tag = str(self.n)
        budget = LIMIT - RESERVE - 30 - _used()
        if budget < 45:
            return '\n\n[review skipped: too little time left]'
        budget = min(60, budget)
        t0 = time.monotonic()
        out, (areas, ans) = await asyncio.gather(
            _run(['freecadcmd', str(HERE / 'skills' / 'verify-model' / 'verify.py')],
                 {'MODEL': str(MODEL), 'MESH': str(MESH), 'DIMS': '0'}, budget),
            self.look(tag, budget))
        lines = (re.sub(r'\(\s*\d+ %\)', '', ln).strip() for ln in (out or '').splitlines())
        check = '\n'.join(ln for ln in lines if ln and not ln.startswith(NOISE)       # verify's results only
                           and not re.match(r'(dimension |cos\(|\S+: error)', ln))
        text = (f'\n\n[review #{tag} of the saved /app/model.FCStd ({time.monotonic() - t0:.0f} s); images '
                f'{OUT}/look-{tag}.png, {OUT}/sections-{tag}.png]\n'
                f'verify-model: {check if out is not None else "did not finish in time"}\n\n'
                f'[vision (Nemotron 3.5 Super VL), comparing mesh and model]\n{ans.strip()}')
        # keep the best: a worse save never replaces a better model
        ok, iou = _verdict(out)
        if ok is None:
            return text                    # the check did not judge it: no decision
        done = _complete()
        best = OUT / 'best.FCStd'
        if ok and (self.best is None or iou >= self.best[0] - 0.01 or (done and not self.best[1])):
            shutil.copy2(MODEL, best)
            if (APP / 'model.FCStd.iou').exists():
                shutil.copy2(APP / 'model.FCStd.iou', OUT / 'best.iou')
            self.best = (iou, done)
            return text + f'\n\n[kept as the best model so far: IoU estimate {iou:.3f}]'
        if self.best is not None and best.exists():
            lower = OUT / f'lower-{tag}.FCStd'
            shutil.copy2(MODEL, lower)
            shutil.copy2(best, MODEL)
            if (OUT / 'best.iou').exists():
                shutil.copy2(OUT / 'best.iou', APP / 'model.FCStd.iou')
            why = f'IoU estimate {iou:.3f}' if ok else 'not one clean solid'
            text += (f'\n\n[KEEP-THE-BEST: this save ({why}) is worse than the best model (IoU estimate '
                     f'{self.best[0]:.3f}), which is back in /app/model.FCStd; this one is {lower}. The '
                     f'findings above are those of the worse model.]')
        return text

    async def awrap_tool_call(self, request, handler):
        result = await handler(request)
        if not isinstance(result, ToolMessage) or not isinstance(result.content, str):
            return result
        async with self.lock:
            OUT.mkdir(exist_ok=True)
            sig = _sig(MODEL)
            if sig and sig != self.seen:
                result.content += await self.review()
                self.seen = _sig(MODEL)
        return result

    def wrap_tool_call(self, request, handler):
        return handler(request)


MIDDLEWARE = [Clock(), Review()]
