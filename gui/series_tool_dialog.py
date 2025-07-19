#!/usr/bin/env python3

#
# @file series_tool_dialog.py
# @date 26-02-2025
# @author Maxim Kurylko <vk_vm@ukr.net>
#

import logging
import os
import re
import time
from typing import List

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QAction
from natsort import natsorted
from gui.colors import Colors
from gui.icons import render_svg, ADD_FILES_ICON, ADD_DIRECTORY_ICON, \
    ADD_DIRECTORY_REC_ICON, REMOVE_ICON, RESTORE_ICON, REMOVE_ALL_ICON, \
    RESTORE_ALL_ICON, PROCESS_ICON, TEXT_ICON, REGEX_ICON, UNDO_ICON, \
    SUBTITLE_FILTER_ICON
from gui.windows_taskbar_progress import WindowsTaskbarProgress
from utils import pretty_size, pretty_date

logger = logging.getLogger(__name__)


class IncludeRegexToolDialog(QtWidgets.QDialog):
    def __init__(self, example_index:int, example_file: str):
        super().__init__()
        self.example_file = example_file or 'example'
        self.example_index = example_index or 0
        self.init_ui()
        self.update_example()

    def build_replace(self):
        is_case_sensitive = self.case_sensitive.isChecked()
        series_list = self.series_list.toPlainText().split('\n')
        regex = self.regex.text()
        replacement = self.replacement.text()
        def function(index, title):
            try:
                r = re.compile(regex, re.IGNORECASE if not is_case_sensitive else 0)
            except:
                return "<invalid regex>"

            match = r.search(title)

            if replacement.find('%s') != -1:
                if index >= len(series_list):
                    return "<invalid series index>"
                r = replacement.replace('%s', series_list[index])
            else:
                r = replacement

            if match:
                print(match.groups())

            r = (r.replace('%%', '%')
                  .replace('%i', str(index))
                  .replace('%t', title)
                  .replace('%0', match.group(0) if match else ''))

            if match:
                for i in range(1, 10):
                    if i > len(match.groups()):
                        break
                    r = r.replace(f'%{i}', match.group(i))

            return r

        return function

    def update_example(self):
        logger.info('Update example')
        self.example.setText(self.build_replace()(self.example_index, self.example_file))

    def init_ui(self):
        self.setWindowTitle('Include Regex Tool')
        self.setBaseSize(800, 600)

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        layout.addWidget(QtWidgets.QLabel('Series list (new line separated)'))
        self.series_list = QtWidgets.QTextEdit()
        layout.addWidget(self.series_list)
        self.series_list.setPlainText('Series 1\nSeries 2\nSeries 3')
        self.series_list.textChanged.connect(self.update_example)

        layout.addWidget(QtWidgets.QLabel('Regex'))
        self.regex = QtWidgets.QLineEdit()
        layout.addWidget(self.regex)
        self.regex.setPlaceholderText('Example: (.*)')
        self.regex.setText('(.*)')
        self.regex.textChanged.connect(self.update_example)

        layout.addWidget(QtWidgets.QLabel('Replacement\n'
                                          '%% replace with \'%\' character\n'
                                          '%t replace with full title\n'
                                          '%0 replace with full match\n'
                                          '%<index> replace with group index\n'
                                          '%s replace with series name\n'
                                          '%i replace with index'))
        self.replacement = QtWidgets.QLineEdit()
        layout.addWidget(self.replacement)
        self.replacement.setPlaceholderText('Example: %t_%i')
        self.replacement.setText('%t_%i')
        self.replacement.textChanged.connect(self.update_example)

        self.case_sensitive = QtWidgets.QCheckBox('Case sensitive')
        layout.addWidget(self.case_sensitive)
        self.case_sensitive.setChecked(False)
        self.case_sensitive.stateChanged.connect(self.update_example)

        self.example = QtWidgets.QLabel()
        layout.addWidget(self.example)

        dialog_buttons = QtWidgets.QDialogButtonBox()
        dialog_buttons.setStandardButtons(
            QtWidgets.QDialogButtonBox.Cancel | QtWidgets.QDialogButtonBox.Ok)
        dialog_buttons.accepted.connect(self.accept)
        dialog_buttons.rejected.connect(self.reject)
        layout.addWidget(dialog_buttons)

        self.show()

    def accept(self):
        super().accept()
        self.result = self.build_replace()

class ExcludeRegexToolDialog(QtWidgets.QDialog):
    def __init__(self, example_index:int, example_file: str):
        super().__init__()
        self.example_file = example_file or 'example'
        self.example_index = example_index or 0
        self.init_ui()
        self.update_example()

    def build_replace(self):
        is_case_sensitive = self.case_sensitive.isChecked()
        regex = self.regex.text()
        replacement = self.replacement.text()
        def function(index, title):
            try:
                r = re.compile(regex, re.IGNORECASE if not is_case_sensitive else 0)
            except:
                return "<invalid regex>"

            match = r.search(title)
            print(match)

            r = (replacement
                    .replace('%%', '%')
                    .replace('%i', str(index))
                    .replace('%t', title)
                    .replace('%0', match.group(0) if match else '')
                 )

            if match:
                for i in range(1, 10):
                    if i > len(match.groups()):
                        break
                    r = r.replace(f'%{i}', match.group(i))
                title = title.replace(match.group(0), r)

            return title

        return function

    def update_example(self):
        logger.info('Update example')
        self.example.setText(self.build_replace()(self.example_index, self.example_file))

    def init_ui(self):
        self.setWindowTitle('Exclude Regex Tool')
        self.setBaseSize(800, 600)

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        layout.addWidget(QtWidgets.QLabel('Regex'))
        self.regex = QtWidgets.QLineEdit()
        layout.addWidget(self.regex)
        self.regex.setPlaceholderText('Example: (.*)')
        self.regex.textChanged.connect(self.update_example)

        layout.addWidget(QtWidgets.QLabel('Replacement\n'
                                          '%% replace with \'%\' character\n'
                                          '%t replace with full title\n'
                                          '%0 replace with full match\n'
                                          '%<index> replace with group index\n'
                                          '%i replace with index'))
        self.replacement = QtWidgets.QLineEdit()
        layout.addWidget(self.replacement)
        self.replacement.textChanged.connect(self.update_example)
        self.replacement.setPlaceholderText('Example: %0')

        self.case_sensitive = QtWidgets.QCheckBox('Case sensitive')
        layout.addWidget(self.case_sensitive)
        self.case_sensitive.setChecked(False)
        self.case_sensitive.stateChanged.connect(self.update_example)

        self.example = QtWidgets.QLabel()
        layout.addWidget(self.example)

        dialog_buttons = QtWidgets.QDialogButtonBox()
        dialog_buttons.setStandardButtons(
            QtWidgets.QDialogButtonBox.Cancel | QtWidgets.QDialogButtonBox.Ok)
        dialog_buttons.accepted.connect(self.accept)
        dialog_buttons.rejected.connect(self.reject)
        layout.addWidget(dialog_buttons)

        self.show()

    def accept(self):
        super().accept()
        self.result = self.build_replace()

class File:
    def __init__(self, file):
        self.file = file
        self.dir = os.path.dirname(file)
        noext, ext = os.path.splitext(os.path.basename(file))
        self.ext = ext
        self.output = noext


class SeriesTool(QtWidgets.QDialog):
    def __init__(self, start_files: List[str] = None):
        super().__init__()
        self.setAcceptDrops(True)
        self.init_ui()
        self.files = []
        self.history = []

        for file in start_files or []:
            if os.path.isdir(file):
                self.open_directory(file, False)
            else:
                self.open_file(file)
        self.update_files_table()

    def update_files_table(self):
        # Sort files naturally by path
        self.files = list(natsorted(self.files, key=lambda x: x.file))

        self.files_table.setRowCount(len(self.files))
        for i, file in enumerate(self.files):
            self.files_table.setItem(i, 0, QtWidgets.QTableWidgetItem(str(i)))
            self.files_table.setItem(i, 1, QtWidgets.QTableWidgetItem(file.dir))
            self.files_table.setItem(i, 2, QtWidgets.QTableWidgetItem(file.ext))
            self.files_table.setItem(i, 3, QtWidgets.QTableWidgetItem(os.path.basename(file.file)))
            self.files_table.setItem(i, 4, QtWidgets.QTableWidgetItem(file.output))

        has_files = len(self.files) > 0
        self.save_changes_action.setEnabled(has_files)
        self.inclusive_regex_tool_action.setEnabled(has_files)
        self.exclusive_regex_tool_action.setEnabled(has_files)

    def open_file(self, file):
        self.history = []

        logger.info("open %s", file)
        self.files.append(File(file))

    def open_directory(self, directory, recursive=False):
        # Don't use os.walk() here, it's too slow
        try:
            for any in os.listdir(directory):
                path = os.path.join(directory, any)
                if os.path.isdir(path):
                    if recursive:
                        self.open_directory(path, True)
                else:
                    self.open_file(path)
        except Exception as e:
            logger.error('Failed to open directory %s: %s', directory, e)

        self.update_files_table()

    # Process dropped files
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            logger.debug('Accepting drop event')
            event.accept()
        else:
            logger.debug('Ignoring drop event')
            event.ignore()

    def dropEvent(self, event):
        logger.debug('Dropped files: %s', event.mimeData().urls())
        for url in event.mimeData().urls():
            if url.isLocalFile():
                if os.path.isdir(url.toLocalFile()):
                    self.open_directory(url.toLocalFile(), True)
                else:
                    self.open_file(url.toLocalFile())
                self.update_files_table()

    def add_files(self):
        dialog = QtWidgets.QFileDialog()
        dialog.setFileMode(QtWidgets.QFileDialog.ExistingFiles)
        dialog.setNameFilter('Backup files (*.bak*);;All files (*)')
        if dialog.exec_():
            for file in dialog.selectedFiles():
                self.open_file(file)
            self.update_files_table()

    def add_directory(self):
        dialog = QtWidgets.QFileDialog()
        dialog.setFileMode(QtWidgets.QFileDialog.Directory)
        if dialog.exec_():
            for directory in dialog.selectedFiles():
                self.open_directory(directory)

    def add_directory_recursively(self):
        dialog = QtWidgets.QFileDialog()
        dialog.setFileMode(QtWidgets.QFileDialog.Directory)
        if dialog.exec_():
            for directory in dialog.selectedFiles():
                self.open_directory(directory, True)

    def save_changes(self):
        logger.info('Processing %d files', len(self.files))
        progress = WindowsTaskbarProgress.get_singleton()
        progress.set_visible(True)

        for i, file in enumerate(self.files):
            progress.set_progress(i * 100 / len(self.files))

            in_file = file.file
            out_file = os.path.join(file.dir, file.output + file.ext)
            logger.info('Processing %s -> %s', in_file, out_file)
            try:
                os.rename(in_file, out_file)
                file.file = out_file
            except Exception as e:
                logger.error('Failed to process %s -> %s: %s', in_file, out_file)
                logger.exception(e)

        self.history = []
        self.update_files_table()
        progress.set_visible(False)

    def include_regex_tool(self):
        logger.info('Include Regex tool')
        if not self.files:
            example = None
        else:
            example = self.files[0].output
        dialog = IncludeRegexToolDialog(0, example)
        if dialog.exec_():
            self.history.append([ file.output for file in self.files ])

            function = dialog.result
            for i, file in enumerate(self.files):
                file.output = function(i, file.output)
            self.update_files_table()
        self.undo_action.setEnabled(True)

    def exclude_regex_tool(self):
        logger.info('Exclude Regex tool')
        if not self.files:
            example = None
        else:
            example = self.files[0].output
        dialog = ExcludeRegexToolDialog(0, example)
        if dialog.exec_():
            self.history.append([ file.output for file in self.files ])

            function = dialog.result
            for i, file in enumerate(self.files):
                file.output = function(i, file.output)
            self.update_files_table()
        self.undo_action.setEnabled(True)

    def undo(self):
        logger.info('Undo')
        if self.history:
            for i, file in enumerate(self.files):
                file.output = self.history[-1][i]
            self.history.pop()
            self.update_files_table()

        if not self.history:
            self.undo_action.setEnabled(False)

    def list_tool(self):
        logger.info('List tool')
        pass

    def init_ui(self):
        self.setWindowTitle('Series Tool')
        self.setBaseSize(1600, 1000)

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        toolbar = QtWidgets.QToolBar()
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setOrientation(QtCore.Qt.Horizontal)
        toolbar.setIconSize(QtCore.QSize(32, 32))
        toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        layout.addWidget(toolbar)
        toolbar.addAction(
            render_svg(ADD_FILES_ICON, 32, Colors.get_icon_color()),
            'Add files', self.add_files)
        toolbar.addAction(
            render_svg(ADD_DIRECTORY_ICON, 32, Colors.get_icon_color()),
            'Add directory', self.add_directory)
        toolbar.addAction(
            render_svg(ADD_DIRECTORY_REC_ICON, 32, Colors.get_icon_color()),
            'Add directory\nrecursively', self.add_directory_recursively)
        toolbar.addSeparator()
        self.undo_action = toolbar.addAction(
            render_svg(UNDO_ICON, 32, Colors.get_icon_color()),
            'Undo', self.undo)
        self.undo_action.setEnabled(False)
        self.inclusive_regex_tool_action = toolbar.addAction(render_svg(REGEX_ICON, 32, Colors.get_icon_color()),
                          'Include Regex\ntool', self.include_regex_tool)
        self.exclusive_regex_tool_action = toolbar.addAction(render_svg(REGEX_ICON, 32, Colors.get_icon_color()),
                          'Exclude Regex\ntool', self.exclude_regex_tool)
        # toolbar.addAction(render_svg(SUBTITLE_FILTER_ICON, 32, Colors.get_icon_color()), 'List', self.list_tool)
        toolbar.addSeparator()
        self.save_changes_action =toolbar.addAction(render_svg(PROCESS_ICON, 32, Colors.get_icon_color()),
                          'Save changes', self.save_changes)

        self.files_table = QtWidgets.QTableWidget()
        self.files_table.setColumnCount(5)
        self.files_table.setHorizontalHeaderLabels(
            ['Index', 'Dir', 'Ext', 'Original', 'Output'])
        self.files_table.horizontalHeader().setSectionResizeMode(0,
                                                                 QtWidgets.QHeaderView.ResizeToContents)
        self.files_table.horizontalHeader().setSectionResizeMode(1,
                                                                 QtWidgets.QHeaderView.Stretch)
        self.files_table.horizontalHeader().setSectionResizeMode(2,
                                                                 QtWidgets.QHeaderView.ResizeToContents)
        self.files_table.horizontalHeader().setSectionResizeMode(3,
                                                                 QtWidgets.QHeaderView.Stretch)
        self.files_table.horizontalHeader().setSectionResizeMode(4,
                                                                 QtWidgets.QHeaderView.Stretch)
        self.files_table.verticalHeader().setVisible(False)
        layout.addWidget(self.files_table)

        self.show()
