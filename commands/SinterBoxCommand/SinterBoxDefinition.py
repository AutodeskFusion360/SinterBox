import adsk.core
import adsk.fusion

import config
from .SinterBoxUtils import get_default_offset, middle, mid_point, create_brep_shell_box, create_gaps, FeatureValues

app = adsk.core.Application.get()
ui = app.userInterface


class Direction:
    def __init__(self, name: str, direction: adsk.core.Vector3D, inputs: adsk.core.CommandInputs, default_value: float):
        self.name = name
        self.direction = direction
        self.origin = adsk.core.Point3D.create(0, 0, 0)

        default_value_input = adsk.core.ValueInput.createByReal(default_value)
        self.dist_input: adsk.core.DistanceValueCommandInput = inputs.addDistanceValueCommandInput(
            f"dist_{self.name}", self.name, default_value_input
        )
        self.dist_input.isEnabled = False
        self.dist_input.isVisible = False
        self.dist_input.minimumValue = 0.0
        self.dist_input.isMinimumValueInclusive = True

    def update_manipulator(self, new_origin):
        self.origin = new_origin
        self.dist_input.setManipulator(self.origin, self.direction)
        self.dist_input.isEnabled = True
        self.dist_input.isVisible = True


class SinterBoxDefinition:
    def __init__(self, b_box: adsk.core.BoundingBox3D, inputs: adsk.core.CommandInputs):
        design: adsk.fusion.Design = app.activeProduct
        root_comp = design.rootComponent

        self.b_box = b_box
        self.modified_b_box = self.b_box.copy()

        self.x_pos_vector = root_comp.yZConstructionPlane.geometry.normal.copy()
        self.x_neg_vector = root_comp.yZConstructionPlane.geometry.normal.copy()
        self.x_neg_vector.scaleBy(-1)
        self.y_pos_vector = root_comp.xZConstructionPlane.geometry.normal.copy()
        self.y_neg_vector = root_comp.xZConstructionPlane.geometry.normal.copy()
        self.y_neg_vector.scaleBy(-1)
        self.z_pos_vector = root_comp.xYConstructionPlane.geometry.normal.copy()
        self.z_neg_vector = root_comp.xYConstructionPlane.geometry.normal.copy()
        self.z_neg_vector.scaleBy(-1)

        self.inputs = inputs
        self.thickness_input = inputs.itemById('thick_input')
        self.gap_input = inputs.itemById('gap')
        self.bar_input = inputs.itemById('bar')

        default_offset = get_default_offset()
        self.feature_values = FeatureValues(
            self.thickness_input.value, self.bar_input.value, self.gap_input.value, *([default_offset] * 6))

        direction_group = inputs.addGroupCommandInput('direction_group', 'Offset Values')
        self.directions = {
            "x_pos": Direction("X Positive", self.x_pos_vector, direction_group.children, self.feature_values.x_pos),
            "x_neg": Direction("X Negative", self.x_neg_vector, direction_group.children, self.feature_values.x_neg),
            "y_pos": Direction("Y Positive", self.y_pos_vector, direction_group.children, self.feature_values.y_pos),
            "y_neg": Direction("Y Negative", self.y_neg_vector, direction_group.children, self.feature_values.y_neg),
            "z_pos": Direction("Z Positive", self.z_pos_vector, direction_group.children, self.feature_values.z_pos),
            "z_neg": Direction("Z Negative", self.z_neg_vector, direction_group.children, self.feature_values.z_neg)
        }
        direction_group.isExpanded = False
        
        self.graphics_group = root_comp.customGraphicsGroups.add()
        self.brep_mgr = adsk.fusion.TemporaryBRepManager.get()
        self.graphics_box = None
        self.selections = []

    def initialize_box(self, b_box):
        self.modified_b_box = b_box.copy()

    def update_box(self, point: adsk.core.Point3D):
        self.modified_b_box.expand(point)

    def update_manipulators(self):
        min_p = self.modified_b_box.minPoint
        max_p = self.modified_b_box.maxPoint

        self.directions["x_pos"].update_manipulator(adsk.core.Point3D.create(
            max_p.x, middle(min_p.y, max_p.y), middle(min_p.z, max_p.z))
        )
        self.directions["x_neg"].update_manipulator(adsk.core.Point3D.create(
            min_p.x, middle(min_p.y, max_p.y), middle(min_p.z, max_p.z))
        )
        self.directions["y_pos"].update_manipulator(adsk.core.Point3D.create(
            middle(min_p.x, max_p.x), max_p.y, middle(min_p.z, max_p.z))
        )
        self.directions["y_neg"].update_manipulator(adsk.core.Point3D.create(
            middle(min_p.x, max_p.x), min_p.y, middle(min_p.z, max_p.z))
        )
        self.directions["z_pos"].update_manipulator(adsk.core.Point3D.create(
            middle(min_p.x, max_p.x), middle(min_p.y, max_p.y), max_p.z)
        )
        self.directions["z_neg"].update_manipulator(adsk.core.Point3D.create(
            middle(min_p.x, max_p.x), middle(min_p.y, max_p.y), min_p.z)
        )

    def expand_box_in_directions(self):
        direction: Direction
        for key, direction in self.directions.items():
            point = direction.dist_input.manipulatorOrigin.copy()
            vector = direction.direction.copy()
            vector.normalize()
            vector.scaleBy(direction.dist_input.value)
            point.translateBy(vector)
            self.update_box(point)

    def box_center(self):
        return mid_point(self.modified_b_box.minPoint, self.modified_b_box.maxPoint)

    def update_graphics(self):
        self.clear_graphics()

        shell_box = create_brep_shell_box(self.modified_b_box, self.thickness_input.value)

        color = adsk.core.Color.create(10, 200, 50, 125)
        color_effect = adsk.fusion.CustomGraphicsSolidColorEffect.create(color)
        self.graphics_box = self.graphics_group.addBRepBody(shell_box)
        self.graphics_box.color = color_effect

    def update_graphics_full(self):
        self.clear_graphics()

        shell_box = create_brep_shell_box(self.modified_b_box, self.thickness_input.value)
        gaps = create_gaps(self.modified_b_box, self.feature_values)

        g_color = adsk.core.Color.create(0, 0, 0, 0)
        g_color_effect = adsk.fusion.CustomGraphicsSolidColorEffect.create(g_color)
        for gap in gaps:
            g_graphic = self.graphics_group.addBRepBody(gap)
            g_graphic.depthPriority = 1
            g_graphic.color = g_color_effect

        color = adsk.core.Color.create(10, 200, 50, 125)
        color_effect = adsk.fusion.CustomGraphicsSolidColorEffect.create(color)
        self.graphics_box = self.graphics_group.addBRepBody(shell_box)
        self.graphics_box.color = color_effect

    def clear_graphics(self):
        if self.graphics_box is not None:
            if self.graphics_box.isValid:
                self.graphics_box.deleteMe()
        for entity in self.graphics_group:
            if entity.isValid:
                entity.deleteMe()

    def create_brep(self) -> adsk.fusion.Occurrence:
        design: adsk.fusion.Design = app.activeProduct
        root_comp = design.rootComponent

        new_occ: adsk.fusion.Occurrence = root_comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        new_comp = new_occ.component
        new_comp.name = config.DEFAULT_COMPONENT_NAME

        shell_box = create_brep_shell_box(self.modified_b_box, self.thickness_input.value)

        gaps = create_gaps(self.modified_b_box, self.feature_values)
        brep_mgr = adsk.fusion.TemporaryBRepManager.get()
        for gap in gaps:
            brep_mgr.booleanOperation(shell_box, gap, adsk.fusion.BooleanTypes.DifferenceBooleanType)

        if design.designType == adsk.fusion.DesignTypes.ParametricDesignType:

            base_feature = new_comp.features.baseFeatures.add()
            base_feature.startEdit()
            new_comp.bRepBodies.add(shell_box, base_feature)
            base_feature.finishEdit()

        else:
            new_comp.bRepBodies.add(shell_box)

        return new_occ

