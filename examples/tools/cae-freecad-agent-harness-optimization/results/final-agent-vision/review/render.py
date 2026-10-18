# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Render the mesh (blue, left) and, if MODEL exists, the model's Body (orange, middle) and
their difference (right: outlines compared pixel by pixel, grey where both are, blue where
only the mesh is, red where only the model is), same camera, one row per view, one PNG.
Needs the virtual display; ~5 s:

    MODEL=/app/model.FCStd MESH=/app/reference.obj OUT=/app/look.png \
      xvfb-run -a -s "-screen 0 1600x1200x24" freecadcmd /agent/review/render.py

VIEWS=iso,front,right,top (default; also rear, left, bottom). front looks along +y,
right along -x, top along -z.
"""
import os

import FreeCAD as App
import FreeCADGui as Gui
import Mesh
import numpy as np

Gui.showMainWindow()
from PySide import QtGui  # noqa: E402  (needs the GUI started)

app = QtGui.QApplication.instance()
VIEWS = os.environ.get('VIEWS', 'iso,front,right,top').split(',')
METHODS = {'iso': 'viewIsometric', 'front': 'viewFront', 'rear': 'viewRear', 'right': 'viewRight',
           'left': 'viewLeft', 'top': 'viewTop', 'bottom': 'viewBottom'}
W, H = 640, 440
model, out = os.environ.get('MODEL', '/app/model.FCStd'), os.environ.get('OUT', '/app/look.png')


def mask(q):
    """Pixels of a white-background render that show something."""
    q = q.convertToFormat(QtGui.QImage.Format_RGB32)
    a = np.frombuffer(q.constBits(), np.uint8, count=q.sizeInBytes()).reshape(q.height(), -1, 4)
    return (a[:, :q.width(), :3] < 245).any(2)


def difference(mesh_img, model_img):
    """Grey where mesh and model both show, blue where only the mesh, red where only the model."""
    me, mo = mask(mesh_img), mask(model_img)
    rgb = np.full(me.shape + (3,), 255, np.uint8)
    rgb[me & mo] = (200, 200, 200)
    rgb[me & ~mo] = (20, 90, 255)
    rgb[mo & ~me] = (235, 40, 20)
    h, w = me.shape
    return QtGui.QImage(rgb.tobytes(), w, h, 3 * w, QtGui.QImage.Format_RGB888).copy()


def settle():
    for _ in range(20):
        app.processEvents()


try:
    if os.path.exists(model) and model.lower().endswith('.fcstd'):
        doc = App.openDocument(model)
        doc.recompute()
        body = next(o for o in doc.Objects if o.TypeId == 'PartDesign::Body')
    else:
        doc, body = App.newDocument('Look'), None
    Gui.ActiveDocument = Gui.getDocument(doc.Name)
    for o in doc.Objects:
        if o.ViewObject:
            o.ViewObject.Visibility = False
    shown = []
    if body is not None:  # draw the body's shape as computed, whatever its view settings
        bad = [o.Name for o in doc.Objects if 'Invalid' in o.State]
        note = f'model: {len(body.Shape.Solids)} solid(s), volume {body.Shape.Volume:.3f}'
        os.write(1, (note + (f', INVALID features {bad}' if bad else '') + '\n').encode())
        if not body.Shape.isNull():
            copy = doc.addObject('Part::Feature', 'ModelShape')
            copy.Shape = body.Shape
            shown = [copy]
    for o in shown:
        o.ViewObject.ShapeColor, o.ViewObject.DisplayMode = (0.95, 0.55, 0.15), 'Shaded'
    mesh = doc.addObject('Mesh::Feature', 'Reference')
    mesh.Mesh = Mesh.Mesh(os.environ.get('MESH', '/app/reference.obj'))
    doc.recompute()
    mesh.ViewObject.ShapeColor = (0.35, 0.55, 0.85)
    view = Gui.ActiveDocument.ActiveView
    view.setAnimationEnabled(False)
    labels = ['mesh', 'model', 'difference'] if shown else ['mesh']  # same camera, one row per view
    img = QtGui.QImage(W * len(labels), H * len(VIEWS), QtGui.QImage.Format_RGB32)
    img.fill(QtGui.QColor('white'))
    painter = QtGui.QPainter(img)
    painter.setFont(QtGui.QFont('Sans', 16))
    for k, name in enumerate(VIEWS):
        for o in shown:
            o.ViewObject.Visibility = True
        mesh.ViewObject.Visibility = True
        getattr(view, METHODS[name])()
        settle()
        view.fitAll()
        panels = []
        for c, label in enumerate(labels):
            if label == 'difference':
                panel = difference(*panels)
            else:
                mesh.ViewObject.Visibility = label == 'mesh'
                for o in shown:
                    o.ViewObject.Visibility = label == 'model'
                settle()
                view.saveImage('/tmp/_look.png', W, H, 'White')
                panel = QtGui.QImage('/tmp/_look.png')
                panels.append(panel)
            painter.drawImage(c * W, k * H, panel)
            painter.drawText(c * W + 10, k * H + 26, f'{name}: {label}')
    painter.end()
    img.save(out)
    os.write(1, f'saved {out}\n'.encode())  # the GUI captures print()
finally:
    os._exit(0)  # the GUI would otherwise keep running
