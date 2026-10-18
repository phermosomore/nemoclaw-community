# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Flat cross-sections of the mesh (and the model) on axis planes, drawn to one PNG, for the
review after each save (middleware.py). From experimenter C's cad-v10c.

    PLANES="z=12.5; x=40" MESH=/app/reference.obj [MODEL=/app/model.FCStd] OUT=sections.png \
      freecadcmd sections.py

One row per plane, same scale and axes in every column: the mesh's section (blue), the
model's (orange), and their difference (grey both, blue mesh only, red model only). Prints
per plane the areas of mesh, model, both, mesh only and model only. No display needed."""
import os

import FreeCAD as App
import Mesh
import matplotlib
import numpy as np
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.path import Path  # noqa: E402

AX = {'x': ((1, 0, 0), (0, 1, 0), (0, 0, 1)), 'y': ((0, 1, 0), (1, 0, 0), (0, 0, 1)),
      'z': ((0, 0, 1), (1, 0, 0), (0, 1, 0))}


def parse(spec, centre):
    spec = spec.strip()
    n, u, v = AX[spec[0]]
    o = np.array(centre, float)
    o['xyz'.index(spec[0])] = float(spec[2:])
    return spec, o, np.array(u, float), np.array(v, float)


def mesh_polys(mesh, o, u, v):
    n = np.cross(u, v)
    base = o + n * 1e-5 * mesh.BoundBox.DiagonalLength  # off any plane of mesh vertices
    out = []
    for poly in mesh.crossSections([(App.Vector(*base), App.Vector(*n))], 1e-4)[0]:
        q = np.array([(c.x, c.y, c.z) for c in poly]) - o
        if len(q) >= 4:
            out.append(np.c_[q @ u, q @ v])
    return out


def model_polys(shape, o, u, v):
    n = np.cross(u, v)
    out = []
    ws = []
    for eps in (1e-5, 1e-3, -1e-3):     # off any seam or vertex lying in the plane itself
        ws = shape.slice(App.Vector(*n), float(n @ o) + eps * shape.BoundBox.DiagonalLength)
        if ws:
            break
    for w in ws:
        pts = np.array([(p.x, p.y, p.z) for p in w.discretize(Deflection=0.02)]) - o
        if len(pts) >= 3:
            out.append(np.c_[pts @ u, pts @ v])
    return out


def inside(polys, X, Y):
    """Even-odd fill of a set of closed loops (a hole inside a loop is empty)."""
    q = np.c_[X.ravel(), Y.ravel()]
    m = np.zeros(len(q), bool)
    for p in polys:
        m ^= Path(p).contains_points(q)
    return m.reshape(X.shape)


def main():
    mesh = Mesh.Mesh(os.environ.get('MESH', '/app/reference.obj'))
    bb = mesh.BoundBox
    centre = (bb.Center.x, bb.Center.y, bb.Center.z)
    shape = None
    if os.environ.get('MODEL') and os.path.exists(os.environ['MODEL']):
        doc = App.openDocument(os.environ['MODEL'])   # the shapes as saved (no recompute: quiet and fast)
        bodies = [o for o in doc.Objects if o.TypeId == 'PartDesign::Body']
        shape = (bodies[0] if bodies else [o for o in doc.Objects if hasattr(o, 'Shape') and o.Shape.Solids][-1]).Shape
    planes = [parse(s, centre) for s in os.environ.get('PLANES', 'z=%.3f' % bb.Center.z).split(';') if s.strip()]
    cols = 3 if shape is not None else 1
    secs = []
    for name, o, u, v in planes:
        mp = mesh_polys(mesh, o, u, v)
        secs.append((name, mp, model_polys(shape, o, u, v) if shape is not None else []))
    def aspect(polys):
        if not polys:
            return 0.5
        P = np.vstack(polys)
        w, h = P.max(axis=0) - P.min(axis=0)
        return float(np.clip((h + 1) / (w + 1), 0.3, 1.3))
    hs = [aspect(mp + sp) for _, mp, sp in secs]
    fig, axs = plt.subplots(len(planes), cols, figsize=(4.4 * cols, sum(3.9 * a + 0.6 for a in hs)),
                            squeeze=False, gridspec_kw={'height_ratios': hs})
    for r, (name, mp, sp) in enumerate(secs):
        allp = mp + sp
        if not allp:
            print(f'{name}: no section of mesh or model on this plane')
            for a in axs[r]:
                a.set_title(f'{name}: empty', fontsize=9)
            continue
        P = np.vstack(allp)
        lo, hi = P.min(axis=0), P.max(axis=0)
        pad = 0.08 * max(hi - lo) + 0.5
        lo, hi = lo - pad, hi + pad
        h = max(hi - lo) / 400
        X, Y = np.meshgrid(np.arange(lo[0], hi[0], h), np.arange(lo[1], hi[1], h))
        A = inside(mp, X, Y)
        B = inside(sp, X, Y) if shape is not None else np.zeros_like(A)
        cell = h * h
        line = f'{name}: mesh area {A.sum() * cell:.2f} ({len(mp)} loops)'
        if shape is not None:
            line += (f', model {B.sum() * cell:.2f} ({len(sp)} loops), both {(A & B).sum() * cell:.2f}, '
                     f'mesh only {(A & ~B).sum() * cell:.2f}, model only {(B & ~A).sum() * cell:.2f}')
        print(line)
        imgs = [(A, (0.25, 0.45, 0.85), 'mesh')]
        if shape is not None:
            imgs.append((B, (0.95, 0.55, 0.15), 'model'))
            D = np.ones(A.shape + (3,))
            D[A & B] = (0.6, 0.6, 0.6)
            D[A & ~B] = (0.15, 0.35, 0.95)
            D[B & ~A] = (0.9, 0.1, 0.1)
            imgs.append((D, None, 'difference'))
        for c, (img, col, title) in enumerate(imgs):
            if col is not None:
                rgb = np.ones(img.shape + (3,))
                rgb[img] = col
                img = rgb
            ax = axs[r][c]
            ax.imshow(img, origin='lower', extent=(lo[0], hi[0], lo[1], hi[1]), interpolation='nearest')
            ax.set_title(f'{name}  [{title}]', fontsize=9)
            ax.tick_params(labelsize=7)
            ax.set_aspect('equal')
            ax.grid(True, lw=0.3, alpha=0.5)
    fig.tight_layout()
    out = os.environ.get('OUT', '/app/sections.png')
    fig.savefig(out, dpi=80)
    print('wrote', out, f'({len(planes)} planes; in-plane axes: x= planes y,z; y= planes x,z; z= planes x,y)')


main()
