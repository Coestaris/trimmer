#!/usr/bin/env python3

#
# @file windows_taskbar_progress.py
# @date 27-02-2025
# @author Maxim Kurylko <vk_vm@ukr.net>
#

import platform
import logging

from PyQt5 import QtWidgets
from PyQt5.QtWinExtras import QWinTaskbarButton

logger = logging.getLogger(__name__)


class WindowsTaskbarProgressDummy:
    __single_instance = None

    def set_progress(self, value: int):
        pass

    def set_visible(self, visible: bool):
        pass

    @staticmethod
    def get_singleton() -> 'WindowsTaskbarProgress':
        return None

if platform.system() == 'Windows':
    class WindowsTaskbarProgress(WindowsTaskbarProgressDummy):
        __single_instance = None

        def __init__(self, main_window: QtWidgets.QMainWindow):
            if WindowsTaskbarProgress.__single_instance is not None:
                raise Exception('WindowsTaskbarProgress is a singleton')
            WindowsTaskbarProgress.__single_instance = self

            logger.info('Windows detected, enabling taskbar progress')
            self.win_taskbar_button = QWinTaskbarButton(main_window)
            self.win_taskbar_button.setWindow(main_window.windowHandle())

            self.win_taskbar_progress = self.win_taskbar_button.progress()
            self.win_taskbar_progress.setRange(0, 100)
            self.win_taskbar_progress.setVisible(False)

        def set_progress(self, value: float):
            self.win_taskbar_progress.setValue(int(value))

        def set_visible(self, visible: bool):
            self.win_taskbar_progress.setVisible(visible)

        @staticmethod
        def get_singleton() -> 'WindowsTaskbarProgressDummy':
            if WindowsTaskbarProgress.__single_instance is None:
                logger.warning('WindowsTaskbarProgress is not initialized')
                return WindowsTaskbarProgressDummy()
            return WindowsTaskbarProgress.__single_instance
else:
    WindowsTaskbarProgress = WindowsTaskbarProgressDummy