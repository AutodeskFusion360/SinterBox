import adsk.core
import adsk.fusion
import os

from .SinterBoxUtils import oriented_b_box_from_b_box, bounding_box_from_selections, get_default_thickness
from .SinterBoxDefinition import Direction, SinterBoxDefinition
from ...lib import fusion360utils as futil
from ... import config

app = adsk.core.Application.get()
ui = app.userInterface

DO_FULL_PREVIEW = False
the_box: SinterBoxDefinition
the_box = None

CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_sinterBox'
CMD_NAME = 'SinterBox'
CMD_Description = 'Create a Sinter Box for the selected geometry'

# Specify that the command will be promoted to the panel.
IS_PROMOTED = False

# This is done by specifying the workspace, the tab, and the panel, and the
# command it will be inserted beside. Not providing the command to position it
# will insert it at the end.
WORKSPACE_ID = 'FusionSolidEnvironment'
PANEL_ID = 'SolidCreatePanel'
COMMAND_BESIDE_ID = 'PrimitivePipe'

# Resource location for command icons, here we assume a sub folder in this directory named "resources".
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []


# Executed when add-in is run.
def start():
    # Create a command Definition.
    cmd_def = ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, CMD_Description, ICON_FOLDER)

    # Define an event handler for the command created event. It will be called when the button is clicked.
    futil.add_handler(cmd_def.commandCreated, command_created)

    # ******** Add a button into the UI so the user can run the command. ********
    # Get the target workspace the button will be created in.
    workspace = ui.workspaces.itemById(WORKSPACE_ID)

    # Get the panel the button will be created in.
    panel = workspace.toolbarPanels.itemById(PANEL_ID)

    # Create the button command control in the UI after the specified existing command.
    control = panel.controls.addCommand(cmd_def, COMMAND_BESIDE_ID, False)

    # Specify if the command is promoted to the main toolbar. 
    control.isPromoted = IS_PROMOTED


# Executed when add-in is stopped.
def stop():
    # Get the various UI elements for this command
    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
    command_control = panel.controls.itemById(CMD_ID)
    command_definition = ui.commandDefinitions.itemById(CMD_ID)

    # Delete the button command control
    if command_control:
        command_control.deleteMe()

    # Delete the command definition
    if command_definition:
        command_definition.deleteMe()


# Function that is called when a user clicks the corresponding button in the UI.
# This defines the contents of the command dialog and connects to the command related events.
def command_created(args: adsk.core.CommandCreatedEventArgs):
    global the_box
    futil.log(f'{CMD_NAME} Command Created Event')

    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.executePreview, command_preview, local_handlers=local_handlers)
    futil.add_handler(args.command.validateInputs, command_validate_input, local_handlers=local_handlers)
    futil.add_handler(args.command.mouseDragEnd, mouse_drag_end, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)

    inputs = args.command.commandInputs
    design: adsk.fusion.Design = app.activeProduct
    units = design.unitsManager.defaultLengthUnits

    selection_input = inputs.addSelectionInput('body_select', "Input Bodies", "Bodies for Bounding Box")
    selection_input.addSelectionFilter('Bodies')
    selection_input.setSelectionLimits(1, 0)

    # TODO Handle preselected bodies?
    default_selections = []

    # Get initialized bounding box, may really not be needed here...
    b_box = bounding_box_from_selections(default_selections)

    default_thickness = get_default_thickness()
    thickness_input = adsk.core.ValueInput.createByReal(default_thickness)

    gap_input = adsk.core.ValueInput.createByReal(2)
    bar_input = adsk.core.ValueInput.createByReal(.2)

    inputs.addValueInput('thick_input', "Cage Thickness", units, thickness_input)

    inputs.addValueInput('gap', "Bar Spacing", units, gap_input)
    inputs.addValueInput('bar', "Bar Width", units, bar_input)

    # Create main box class
    the_box = SinterBoxDefinition(b_box, inputs)


# This event handler is called when the user clicks the OK button in the command dialog or 
# is immediately called after the created event not command inputs were created for the dialog.
def command_execute(args: adsk.core.CommandEventArgs):
    futil.log(f'{CMD_NAME} Command Execute Event')
    the_box.clear_graphics()
    the_box.create_brep()


# This event handler is called when the command needs to compute a new preview in the graphics window.
def command_preview(args: adsk.core.CommandEventArgs):
    global DO_FULL_PREVIEW
    futil.log(f'{CMD_NAME} Command Preview Event')
    inputs = args.command.commandInputs

    selection_input: adsk.core.SelectionCommandInput = inputs.itemById('body_select')
    selections = [selection_input.selection(i).entity for i in range(selection_input.selectionCount)]

    if len(selections) > 0:
        new_box = bounding_box_from_selections(selections)
        the_box.initialize_box(new_box)

        direction: Direction
        for key, direction in the_box.directions.items():
            point = direction.dist_input.manipulatorOrigin.copy()
            vector = direction.direction.copy()
            vector.normalize()
            vector.scaleBy(direction.dist_input.value)
            point.translateBy(vector)
            the_box.update_box(point)

        if DO_FULL_PREVIEW:
            the_box.update_graphics_full()
            DO_FULL_PREVIEW = False
        else:
            the_box.update_graphics()


# This event handler is called when the user changes anything in the command dialog
# allowing you to modify values of other inputs based on that change.
def command_input_changed(args: adsk.core.InputChangedEventArgs):
    global DO_FULL_PREVIEW
    DO_FULL_PREVIEW = True
    changed_input = args.input
    inputs = args.inputs
    futil.log(f'{CMD_NAME} Input Changed Event fired from a change to {changed_input.id}')

    selection_input: adsk.core.SelectionCommandInput = inputs.itemById('body_select')
    selections = [selection_input.selection(i).entity for i in range(selection_input.selectionCount)]

    bar_input: adsk.core.ValueCommandInput = inputs.itemById('bar')
    bar_value = bar_input.value

    thickness_input: adsk.core.ValueCommandInput = inputs.itemById('thick_input')
    thickness_value = thickness_input.value

    gap_input: adsk.core.ValueCommandInput = inputs.itemById('gap')
    gap_value = gap_input.value
    gap_limit = thickness_value * 2

    if changed_input.id == 'body_select':
        if len(selections) > 0:
            the_box.selections = selections
            new_box = bounding_box_from_selections(selections)
            the_box.initialize_box(new_box)
            the_box.update_manipulators()
            o_box = oriented_b_box_from_b_box(new_box)

            min_gaps = []
            for side in [o_box.length, o_box.width, o_box.height]:
                min_gap = side * .9
                if min_gap > gap_limit:
                    min_gaps.append(min_gap)

            if len(min_gaps) > 0:
                most_min_gap = min(min_gaps)
            else:
                most_min_gap = thickness_value

            four_gaps = (side - bar_value * 3) / 4
            three_gaps = (side - bar_value * 2) / 3
            two_gaps = (side - bar_value) / 2

            if four_gaps > gap_limit:
                new_gap = four_gaps
            elif three_gaps > gap_limit:
                new_gap = three_gaps
            elif two_gaps > gap_limit:
                new_gap = two_gaps
            else:
                new_gap = most_min_gap

            inputs.itemById('gap').value = new_gap
            the_box.feature_values.gap = new_gap

    elif changed_input.id == 'bar':
        the_box.feature_values.bar = bar_value
    elif changed_input.id == 'gap':
        the_box.feature_values.gap = gap_value
    elif changed_input.id == 'thick_input':
        the_box.feature_values.shell_thickness = thickness_value
    else:
        DO_FULL_PREVIEW = False


def mouse_drag_end(args: adsk.core.MouseEventArgs):
    global DO_FULL_PREVIEW
    DO_FULL_PREVIEW = True
    command = args.firingEvent.sender
    command.doExecutePreview()


# TODO Maybe better checking
def command_validate_input(args: adsk.core.ValidateInputsEventArgs):
    futil.log(f'{CMD_NAME} Validate Input Event')
    inputs = args.inputs
    
    # Verify the validity of the input values. This controls if the OK button is enabled or not.
    gap_input: adsk.core.ValueCommandInput = inputs.itemById('gap')
    bar_input: adsk.core.ValueCommandInput = inputs.itemById('bar')
    thick_input: adsk.core.ValueCommandInput = inputs.itemById('thick_input')
    if (gap_input.value >= 0) and (bar_input.value >= 0) and (thick_input.value >= 0):
        inputs.areInputsValid = True
    else:
        inputs.areInputsValid = False
        

# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    global local_handlers
    futil.log(f'{CMD_NAME} Command Destroy Event')
    the_box.clear_graphics()
    local_handlers = []
