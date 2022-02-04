import adsk.core
import adsk.fusion
import os

from .SinterBoxUtils import bounding_box_from_selections, get_default_thickness, auto_gaps
from .SinterBoxDefinition import SinterBoxDefinition
from ...lib import fusion360utils as futil
from ... import config

app = adsk.core.Application.get()
ui = app.userInterface


CMD_NAME = 'Sinterbox'
CMD_Description = 'Creates a rectangular sinterbox enclosing the selected geometry for 3D Printing with Selective ' \
                  'Laser Sintering (SLS) or Multi Jet Fusion (MJF).<br><br>' \
                  'Select the solid bodies to enclose then specify the dimensions of the sinterbox. ' \
                  'Use Move Bodies To New Component to consolidate all bodies in the same component. '
IS_PROMOTED = False
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_{CMD_NAME}'

# TODO When workspace issues are fixed for working model.  Also Add MESH when supported.
# WORKSPACE_IDS = ['FusionSolidEnvironment', 'MfgWorkingModelEnv', 'SimplifyWMEnv']
WORKSPACE_IDS = ['FusionSolidEnvironment']
PANEL_ID = 'SolidCreatePanel'
COMMAND_BESIDE_ID = 'PrimitivePipe'
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')
local_handlers = []

# Sinterbox specific global variables
IS_DRAGGING = False
AUTO_SIZE_GAPS = True

the_box: SinterBoxDefinition
the_box = None


def start():
    cmd_def = ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, CMD_Description, ICON_FOLDER)
    cmd_def.toolClipFilename = os.path.join(ICON_FOLDER, 'Sinterbox_Tooltip.png')
    futil.add_handler(cmd_def.commandCreated, command_created)

    for WORKSPACE_ID in WORKSPACE_IDS:
        workspace = ui.workspaces.itemById(WORKSPACE_ID)
        panel = workspace.toolbarPanels.itemById(PANEL_ID)
        control = panel.controls.addCommand(cmd_def, COMMAND_BESIDE_ID, False)
        control.isPromoted = IS_PROMOTED


def stop():
    for WORKSPACE_ID in WORKSPACE_IDS:
        workspace = ui.workspaces.itemById(WORKSPACE_ID)
        panel = workspace.toolbarPanels.itemById(PANEL_ID)
        command_control = panel.controls.itemById(CMD_ID)
        command_definition = ui.commandDefinitions.itemById(CMD_ID)

        if command_control:
            command_control.deleteMe()

        if command_definition:
            command_definition.deleteMe()


def command_created(args: adsk.core.CommandCreatedEventArgs):
    global the_box
    futil.log(f'{CMD_NAME} Command Created Event')

    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.executePreview, command_preview, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)

    futil.add_handler(args.command.mouseDragEnd, mouse_drag_end, local_handlers=local_handlers)
    futil.add_handler(args.command.mouseDragBegin, mouse_drag_begin, local_handlers=local_handlers)

    inputs = args.command.commandInputs
    design: adsk.fusion.Design = app.activeProduct
    units = design.unitsManager.defaultLengthUnits

    selection_input = inputs.addSelectionInput('body_select', "Input Bodies", "Bodies for Bounding Box")
    selection_input.addSelectionFilter('Bodies')
    # selection_input.addSelectionFilter('MeshBodies')   # TODO When bounding box is supported for mesh bodies
    selection_input.setSelectionLimits(1, 0)

    default_selections = []

    b_box = bounding_box_from_selections(default_selections)

    default_thickness = get_default_thickness()
    default_thickness_value = adsk.core.ValueInput.createByReal(default_thickness)

    default_gap_value = adsk.core.ValueInput.createByReal(default_thickness * 4)
    default_bar_value = adsk.core.ValueInput.createByReal(default_thickness * 2)

    inputs.addValueInput('thick_input', "Cage Thickness", units, default_thickness_value)
    inputs.addValueInput('bar', "Bar Width", units, default_bar_value)

    inputs.addBoolValueInput('auto_gaps_input', 'Automatic Bar Spacing', True, '', True)
    gap_input = inputs.addValueInput('gap', "Bar Spacing", units, default_gap_value)
    gap_input.isEnabled = False

    inputs.addBoolValueInput('full_preview_input', 'Preview', True, '', True)

    inputs.addBoolValueInput('new_component_input', 'Move Bodies to New Component', True, '', True)

    the_box = SinterBoxDefinition(b_box, inputs)


def command_execute(args: adsk.core.CommandEventArgs):
    futil.log(f'{CMD_NAME} Command Execute Event')

    inputs = args.command.commandInputs
    selection_input: adsk.core.SelectionCommandInput = inputs.itemById('body_select')
    new_component_input: adsk.core.BoolValueCommandInput = inputs.itemById('new_component_input')
    bar_input: adsk.core.ValueCommandInput = inputs.itemById('bar')
    thickness_input: adsk.core.ValueCommandInput = inputs.itemById('thick_input')
    gap_input: adsk.core.ValueCommandInput = inputs.itemById('gap')

    selection_bodies = [selection_input.selection(i).entity for i in range(selection_input.selectionCount)]
    if len(selection_bodies) < 1:
        return

    design: adsk.fusion.Design = app.activeProduct
    root_comp = design.rootComponent

    group_start_index = 0
    group_end_index = 0

    is_parametric = design.designType == adsk.fusion.DesignTypes.ParametricDesignType

    if is_parametric:
        group_start_index = design.timeline.markerPosition
        group_end_index = group_start_index + 2

    the_box.clear_graphics()

    the_box.update_selections(selection_bodies)

    the_box.feature_values.bar = bar_input.value
    the_box.feature_values.gap = gap_input.value
    the_box.feature_values.shell_thickness = thickness_input.value

    new_occurrence = the_box.create_brep()

    if new_component_input.value:
        body: adsk.fusion.BRepBody
        for body in selection_bodies:
            body.copyToComponent(new_occurrence)

        for body in selection_bodies:
            if body.isValid:
                if is_parametric:
                    remove_feature = root_comp.features.removeFeatures.add(body)
                    group_end_index = remove_feature.timelineObject.index
                else:
                    body.deleteMe()

    if is_parametric:
        design.timeline.timelineGroups.add(group_start_index, group_end_index)


def command_preview(args: adsk.core.CommandEventArgs):
    futil.log(f'{CMD_NAME} Command Preview Event')
    inputs = args.command.commandInputs

    selection_input: adsk.core.SelectionCommandInput = inputs.itemById('body_select')
    selection_bodies = [selection_input.selection(i).entity for i in range(selection_input.selectionCount)]

    full_preview_input: adsk.core.BoolValueCommandInput = inputs.itemById('full_preview_input')
    full_preview_value = full_preview_input.value

    if len(selection_bodies) > 0:
        the_box.update_selections(selection_bodies)

        if (not IS_DRAGGING) and full_preview_value:
            the_box.update_graphics_full()
        else:
            the_box.update_graphics()


def command_input_changed(args: adsk.core.InputChangedEventArgs):
    global AUTO_SIZE_GAPS

    changed_input = args.input
    command: adsk.core.Command = args.firingEvent.sender
    inputs = command.commandInputs
    futil.log(f'{CMD_NAME} Input Changed Event fired from a change to {changed_input.id}')

    selection_input: adsk.core.SelectionCommandInput = inputs.itemById('body_select')
    selection_bodies = [selection_input.selection(i).entity for i in range(selection_input.selectionCount)]

    bar_input: adsk.core.ValueCommandInput = inputs.itemById('bar')
    bar_value = bar_input.value

    thickness_input: adsk.core.ValueCommandInput = inputs.itemById('thick_input')
    thickness_value = thickness_input.value

    gap_input: adsk.core.ValueCommandInput = inputs.itemById('gap')
    gap_value = gap_input.value

    direction_group: adsk.core.GroupCommandInput = inputs.itemById('direction_group')

    auto_gaps_input: adsk.core.BoolValueCommandInput = inputs.itemById('auto_gaps_input')
    auto_gaps_value = auto_gaps_input.value

    if changed_input.id == 'body_select':
        if len(selection_bodies) > 0:
            if direction_group is not None:
                direction_input: adsk.core.DirectionCommandInput
                for direction_input in direction_group.children:
                    if not direction_input.isVisible:
                        direction_input.isVisible = True

            the_box.update_selections(selection_bodies)

            if AUTO_SIZE_GAPS:
                new_gap = auto_gaps(selection_bodies, the_box.modified_b_box, thickness_value, bar_value)
                gap_input.value = new_gap
                the_box.feature_values.gap = new_gap
        else:
            if direction_group is not None:
                direction_input: adsk.core.DirectionCommandInput
                for direction_input in direction_group.children:
                    if direction_input.isVisible:
                        direction_input.isVisible = False

    elif changed_input.id == 'bar':
        the_box.feature_values.bar = bar_value
    elif changed_input.id == 'gap':
        the_box.feature_values.gap = gap_value
    elif changed_input.id == 'thick_input':
        the_box.feature_values.shell_thickness = thickness_value
    elif changed_input.id == 'auto_gaps_input':
        AUTO_SIZE_GAPS = auto_gaps_value
        if AUTO_SIZE_GAPS:
            gap_input.isEnabled = False
            if len(selection_bodies) > 0:
                new_gap = auto_gaps(selection_bodies, the_box.modified_b_box, thickness_value, bar_value)
                gap_input.value = new_gap
                the_box.feature_values.gap = new_gap
        else:
            gap_input.isEnabled = True


def mouse_drag_begin(args: adsk.core.MouseEventArgs):
    futil.log(f'{CMD_NAME} mouse_drag_begin')
    global IS_DRAGGING
    IS_DRAGGING = True


def mouse_drag_end(args: adsk.core.MouseEventArgs):
    futil.log(f'{CMD_NAME} mouse_drag_end')
    global IS_DRAGGING
    IS_DRAGGING = False

    command: adsk.core.Command = args.firingEvent.sender
    inputs = command.commandInputs
    full_preview_input: adsk.core.BoolValueCommandInput = inputs.itemById('full_preview_input')
    full_preview_value = full_preview_input.value

    if full_preview_value:
        command.doExecutePreview()


def command_destroy(args: adsk.core.CommandEventArgs):
    global local_handlers
    futil.log(f'{CMD_NAME} Command Destroy Event')
    the_box.clear_graphics()
    local_handlers = []

