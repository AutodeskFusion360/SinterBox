#  Copyright 2022 by Autodesk, Inc.
#  Permission to use, copy, modify, and distribute this software in object code form
#  for any purpose and without fee is hereby granted, provided that the above copyright
#  notice appears in all copies and that both that copyright notice and the limited
#  warranty and restricted rights notice below appear in all supporting documentation.
#
#  AUTODESK PROVIDES THIS PROGRAM "AS IS" AND WITH ALL FAULTS. AUTODESK SPECIFICALLY
#  DISCLAIMS ANY IMPLIED WARRANTY OF MERCHANTABILITY OR FITNESS FOR A PARTICULAR USE.
#  AUTODESK, INC. DOES NOT WARRANT THAT THE OPERATION OF THE PROGRAM WILL BE
#  UNINTERRUPTED OR ERROR FREE.

# Application Global Variables
# This module serves as a way to share variables across different
# modules (global variables).
import os

# Flag that indicates to run in Debug mode or not. When running in Debug mode
# more information is written to the Text Command window. Generally, it's useful
# to set this to True while developing an add-in and set it to False when you
# are ready to distribute it.
DEBUG = False

# Gets the name of the add-in from the name of the folder the py file is in.
# This is used when defining unique internal names for various UI elements 
# that need a unique name. It's also recommended to use a company name as 
# part of the ID to better ensure the ID is unique.
ADDIN_NAME = os.path.basename(os.path.dirname(__file__))
COMPANY_NAME = 'Autodesk'

# Palettes
sample_palette_id = f'{COMPANY_NAME}_{ADDIN_NAME}_palette_id'

# SinterBox Default Values
DEFAULT_OFFSET_METRIC = "3 mm"
DEFAULT_SHELL_METRIC = "2 mm"

DEFAULT_OFFSET_INCHES = ".125 in"
DEFAULT_SHELL_INCHES = ".06 in"

DEFAULT_COMPONENT_NAME = "Sinterbox"
