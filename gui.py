#!/usr/bin/env python3
import os.path
from typing import Optional

#
# @file gui.py
# @date 24-02-2025
# @author Maxim Kurylko <kurylko.m@ajax.systems>
#

import pytermgui as ptg
import logging
from inspect import getframeinfo, currentframe

from pytermgui import HorizontalAlignment, VerticalAlignment


class Context:
    def __init__(self):
        pass

class PopupMessage:
    def __init__(self, message: str, frameinfo):
        self.message = message
        self.frameinfo = frameinfo

class InfoMessage(PopupMessage):
    def __init__(self, message: str):
        super().__init__(message, getframeinfo(currentframe().f_back))

class ErrorMessage(PopupMessage):
    def __init__(self, message: str):
        super().__init__(message, getframeinfo(currentframe().f_back))

class FatalMessage(PopupMessage):
    def __init__(self, message: str):
        super().__init__(message, getframeinfo(currentframe().f_back))

def popup(manager: ptg.WindowManager, message: PopupMessage, title: Optional[str] = None):
    # Create Popup with error message
    popup = ptg.Window(
        ptg.Label(message.message),

        ptg.Container(
            ptg.Button("OK", lambda: manager.remove(popup), parent_align=HorizontalAlignment.RIGHT),
            ptg.Button("Cancel", lambda: manager.remove(popup), parent_align=HorizontalAlignment.RIGHT),
            box="EMPTY_HORIZONTAL",
            parent_align=HorizontalAlignment.RIGHT,
        ),

        ptg.Collapsible(
            "Frame info",
            ptg.Label(f"File: {os.path.basename(message.frameinfo.filename)}", parent_align=0),
            ptg.Label(f"Line: {message.frameinfo.lineno}", parent_align=0),
            ptg.Label(f"Function: {message.frameinfo.function}", parent_align=0),
            # box="EMPTY_VERTICAL",
        ),

        title=title or ("Info" if isinstance(message, InfoMessage) else "Error"),
        box="DOUBLE",
    ).center()

    # Add popup to WindowManager
    manager.add(popup)

def run_gui():
    with ptg.WindowManager() as manager:
        popup(manager, InfoMessage("Hello world!"))