---
name: native-cad
description: Reconstruct a reference mesh as an editable FreeCAD sketch-driven PartDesign body. Use for mesh-to-parametric CAD reconstruction.
---

<!-- SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

Measure before modeling. Inspect mesh bounds, independent X/Y cross sections,
wall thickness, cavity, base, and attached features. Do not assume circular
symmetry from the object's name. Keep coordinate frame and placement consistent
with the source. Use measured contours where simple approximations lose shape.

Create a new PartDesign::Body. Construct real Sketcher::SketchObject profiles
inside it and drive native PartDesign::Pad, Pocket, AdditiveLoft, SubtractiveLoft,
or other native features from those profiles. A generic PartDesign::Feature
whose Shape is assigned a scripted B-rep is NOT a native feature, even if its
name is Pad or Sketch. Do not use that shortcut.

For a hollow vessel, consider a padded rounded-rectangle outer profile, then a
pocket for the cavity leaving a measured bottom. Use multiple native sketch
sections and an additive loft or native sweep for a handle. Ensure overlaps at
attachments produce a single solid. Keep dimensions editable with named sketch
constraints or expressions that drive feature properties. Do not fabricate
named properties that are disconnected from construction.

After each feature recompute and check errors, nonzero volume, and validity.
Before finishing, list actual TypeIds, verify native sketches and profile links,
and perturb a named driving dimension slightly within a transaction. Recompute
and verify geometry changes; abort the transaction to restore the original.
Only report success if those checks succeed. Leave the final body visible and
all profiles/intermediate features hidden. Preserve the requested document name.
