import math
from typing import List
from dataclasses import dataclass

import adsk.core
import adsk.fusion

from ... import config

app = adsk.core.Application.get()
ui = app.userInterface


@dataclass
class FeatureValues:
    shell_thickness: float
    bar: float
    gap: float
    x_pos: float
    x_neg: float
    y_pos: float
    y_neg: float
    z_pos: float
    z_neg: float


def middle(min_p_value: float, max_p_value: float) -> float:
    return min_p_value + ((max_p_value - min_p_value) / 2)


def mid_point(p1: adsk.core.Point3D, p2: adsk.core.Point3D) -> adsk.core.Point3D:
    return adsk.core.Point3D.create(
        middle(p1.x, p2.x),
        middle(p1.y, p2.y),
        middle(p1.z, p2.z)
    )


def oriented_b_box_from_b_box(b_box: adsk.core.BoundingBox3D) -> adsk.core.OrientedBoundingBox3D:
    design: adsk.fusion.Design = app.activeProduct
    root_comp = design.rootComponent

    o_box = adsk.core.OrientedBoundingBox3D.create(
        mid_point(b_box.minPoint, b_box.maxPoint),
        root_comp.yZConstructionPlane.geometry.normal.copy(),
        root_comp.xZConstructionPlane.geometry.normal.copy(),
        b_box.maxPoint.x - b_box.minPoint.x,
        b_box.maxPoint.y - b_box.minPoint.y,
        b_box.maxPoint.z - b_box.minPoint.z
    )
    return o_box


def bounding_box_from_selections(selections):
    if len(selections) > 0:
        b_box: adsk.core.BoundingBox3D = selections[0].boundingBox
        for selection in selections[1:]:
            b_box.combine(selection.boundingBox)

    else:
        b_box = adsk.core.BoundingBox3D.create(
            adsk.core.Point3D.create(-1, -1, -1),
            adsk.core.Point3D.create(1, 1, 1)
        )
    return b_box


def create_brep_shell_box(modified_b_box, thickness):
    brep_mgr = adsk.fusion.TemporaryBRepManager.get()
    inner_o_box = oriented_b_box_from_b_box(modified_b_box)

    outer_o_box = inner_o_box.copy()

    outer_o_box.length = outer_o_box.length + thickness * 2
    outer_o_box.width = outer_o_box.width + thickness * 2
    outer_o_box.height = outer_o_box.height + thickness * 2

    inner_box = brep_mgr.createBox(inner_o_box)
    outer_box = brep_mgr.createBox(outer_o_box)

    brep_mgr.booleanOperation(outer_box, inner_box, adsk.fusion.BooleanTypes.DifferenceBooleanType)

    return outer_box


def create_gaps(b_box: adsk.core.BoundingBox3D, feature_values: FeatureValues) -> List[adsk.fusion.BRepBody]:
    gap = feature_values.gap
    bar = feature_values.bar
    thk = feature_values.shell_thickness

    o_box = oriented_b_box_from_b_box(b_box)
    create_o_box = adsk.core.OrientedBoundingBox3D.create
    create_point = adsk.core.Point3D.create

    if (o_box.length - bar - gap - thk * 2) > 0:
        x_num = int(math.floor((o_box.length + bar) / (gap + bar)))
        x_step = (o_box.length - (gap * x_num) - (bar * (x_num - 1))) / 2
    else:
        x_num = 0
        x_step = 0

    if (o_box.width - bar - gap - thk * 2) > 0:
        y_num = int(math.floor((o_box.width + bar) / (gap + bar)))
        y_step = (o_box.width - (gap * y_num) - (bar * (y_num - 1))) / 2
    else:
        y_num = 0
        y_step = 0

    if (o_box.height - bar - gap - thk * 2) > 0:
        z_num = int(math.floor((o_box.height + bar) / (gap + bar)))
        z_step = (o_box.height - (gap * z_num) - (bar * (z_num - 1))) / 2
    else:
        z_num = 0
        z_step = 0

    x_min = b_box.minPoint.x + x_step + gap / 2
    y_min = b_box.minPoint.y + y_step + gap / 2
    z_min = b_box.minPoint.z + z_step + gap / 2

    gaps = []
    brep_mgr = adsk.fusion.TemporaryBRepManager.get()

    for z in range(z_num):
        for y in range(y_num):
            cp_x = create_point(
                o_box.centerPoint.x - (o_box.length + thk) / 2, y_min + y * (bar + gap), z_min + z * (bar + gap))
            x_box = create_o_box(cp_x, o_box.lengthDirection, o_box.widthDirection, thk, gap, gap)
            gaps.append(brep_mgr.createBox(x_box))

            cp_x = create_point(
                o_box.centerPoint.x + (o_box.length + thk) / 2, y_min + y * (bar + gap), z_min + z * (bar + gap))
            x_box = create_o_box(cp_x, o_box.lengthDirection, o_box.widthDirection, thk, gap, gap)
            # x_box = create_o_box(cp_x, o_box.lengthDirection, o_box.widthDirection, o_box.length + thk * 2, gap, gap)
            gaps.append(brep_mgr.createBox(x_box))

    for z in range(z_num):
        for x in range(x_num):
            cp_y = create_point(
                x_min + x * (bar + gap), o_box.centerPoint.y - (o_box.width + thk) / 2, z_min + z * (bar + gap))
            y_box = create_o_box(cp_y, o_box.widthDirection, o_box.lengthDirection, thk, gap, gap)
            gaps.append(brep_mgr.createBox(y_box))

            cp_y = create_point(
                x_min + x * (bar + gap), o_box.centerPoint.y + (o_box.width + thk) / 2, z_min + z * (bar + gap))
            y_box = create_o_box(cp_y, o_box.widthDirection, o_box.lengthDirection, thk, gap, gap)
            gaps.append(brep_mgr.createBox(y_box))

    for y in range(y_num):
        for x in range(x_num):
            cp_z = create_point(
                x_min + x * (bar + gap), y_min + y * (bar + gap), o_box.centerPoint.z - (o_box.height + thk) / 2)
            z_box = create_o_box(cp_z, o_box.heightDirection, o_box.widthDirection, thk, gap, gap)
            gaps.append(brep_mgr.createBox(z_box))

            cp_z = create_point(
                x_min + x * (bar + gap), y_min + y * (bar + gap), o_box.centerPoint.z + (o_box.height + thk) / 2)
            z_box = create_o_box(cp_z, o_box.heightDirection, o_box.widthDirection, thk, gap, gap)
            gaps.append(brep_mgr.createBox(z_box))

    return gaps


def get_default_offset():
    design: adsk.fusion.Design = app.activeProduct
    units = design.unitsManager.defaultLengthUnits
    try:
        if units in [adsk.fusion.DistanceUnits.InchDistanceUnits, adsk.fusion.DistanceUnits.FootDistanceUnits]:
            default_offset = config.DEFAULT_OFFSET_INCHES
        else:
            default_offset = config.DEFAULT_OFFSET_METRIC

    except AttributeError:
        default_offset = f"1 {units}"

    default_value = design.unitsManager.evaluateExpression(default_offset)
    return default_value


def get_default_thickness():
    design: adsk.fusion.Design = app.activeProduct
    units = design.fusionUnitsManager.distanceDisplayUnits
    try:
        if units in [adsk.fusion.DistanceUnits.InchDistanceUnits, adsk.fusion.DistanceUnits.FootDistanceUnits]:
            default_shell = config.DEFAULT_SHELL_INCHES
        else:
            default_shell = config.DEFAULT_SHELL_METRIC

    except AttributeError:
        default_shell = f"1 {units}"

    design: adsk.fusion.Design = app.activeProduct
    default_value = design.unitsManager.evaluateExpression(default_shell)
    return default_value
