#!/usr/bin/env python3

#
# @file backup_manager_dialog.py
# @date 26-02-2025
# @author Maxim Kurylko <vk_vm@ukr.net>
#

import logging
import os
import time
from typing import List

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QAction

from gui.colors import Colors
from gui.icons import render_svg, ADD_FILES_ICON, ADD_DIRECTORY_ICON, \
    ADD_DIRECTORY_REC_ICON, REMOVE_ICON, RESTORE_ICON, REMOVE_ALL_ICON, \
    RESTORE_ALL_ICON
from utils import pretty_size, pretty_date

logger = logging.getLogger(__name__)

class BackupManager(QtWidgets.QDialog):
    def __init__(self, start_files: List[str] = None):
        super().__init__()
        self.setAcceptDrops(True)
        self.init_ui()
        self.files = []

        for file in start_files or []:
            self.open_file(file)

    def get_nobak(self, file):
        return file.split('.bak')[0]

    def open_file(self, file):
        if not ".bak" in file:
            return

        nobak = self.get_nobak(file)
        if not os.path.exists(nobak):
            logger.warning('File %s does not exist', nobak)
            return

        self.files.append(file)
        self.files_count_changed()

        self.files_table.setRowCount(len(self.files))
        self.files_table.setItem(len(self.files) - 1, 0, QtWidgets.QTableWidgetItem(nobak))
        self.files_table.setItem(len(self.files) - 1, 1, QtWidgets.QTableWidgetItem(file))
        self.files_table.setItem(len(self.files) - 1, 2, QtWidgets.QTableWidgetItem(pretty_date(os.path.getmtime(file))))
        self.files_table.setItem(len(self.files) - 1, 3, QtWidgets.QTableWidgetItem(pretty_size(os.path.getsize(nobak))))
        self.files_table.setItem(len(self.files) - 1, 4, QtWidgets.QTableWidgetItem(pretty_size(os.path.getsize(file))))

    def restore_file(self, file):
        nobak = self.get_nobak(file)
        logger.info("copy %s to %s", file, nobak)

        # Don't use copy, it's too slow
        try:
            os.remove(nobak)
        except FileNotFoundError:
            pass
        os.rename(file, nobak)

    def remove_file(self, file):
        logger.info("remove %s", file)
        os.remove(file)

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

    def files_count_changed(self):
        any_files = len(self.files) != 0
        self.remove_all_action.setEnabled(any_files)
        self.restore_all_action.setEnabled(any_files)

    def selection_changed(self):
        if self.files_table.currentRow() == -1:
            self.remove_selected_action.setEnabled(False)
            self.restore_selected_action.setEnabled(False)
        else:
            self.remove_selected_action.setEnabled(True)
            self.restore_selected_action.setEnabled(True)

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

    def add_files(self):
        dialog = QtWidgets.QFileDialog()
        dialog.setFileMode(QtWidgets.QFileDialog.ExistingFiles)
        dialog.setNameFilter('Backup files (*.bak*);;All files (*)')
        if dialog.exec_():
            for file in dialog.selectedFiles():
                self.open_file(file)

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

    def remove_bak(self):
        index = self.files_table.currentRow()
        if index < 0:
            return

        file = self.files[index]
        self.files_table.removeRow(index)
        self.files.remove(file)
        self.files_count_changed()

    def restore_all_bak(self):
        for file in self.files:
            self.restore_file(file)
        self.files_table.setRowCount(0)
        self.files = []
        self.files_count_changed()

    def restore_bak(self):
        index = self.files_table.currentRow()
        if index < 0:
            return

        file = self.files[index]
        self.restore_file(file)
        self.files_table.removeRow(index)
        self.files.remove(file)
        self.files_count_changed()

    def remove_all_bak(self):
        for file in self.files:
            self.remove_file(file)
        self.files_table.setRowCount(0)
        self.files = []
        self.files_count_changed()

    def init_ui(self):
        self.setWindowTitle('Backup Manager')
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
        toolbar.addAction(render_svg(ADD_FILES_ICON, 32, Colors.get_icon_color()), 'Add files', self.add_files)
        toolbar.addAction(render_svg(ADD_DIRECTORY_ICON, 32, Colors.get_icon_color()), 'Add directory', self.add_files)
        toolbar.addAction(render_svg(ADD_DIRECTORY_REC_ICON, 32, Colors.get_icon_color()), 'Add directory\nrecursively', self.add_files)
        toolbar.addSeparator()

        self.remove_selected_action = QAction(render_svg(REMOVE_ICON, 32, Colors.get_icon_color()), 'Remove\nselected', toolbar)
        self.remove_selected_action.setEnabled(False)
        self.remove_selected_action.triggered.connect(self.remove_bak)
        toolbar.addAction(self.remove_selected_action)

        self.restore_selected_action = QAction(render_svg(RESTORE_ICON, 32, Colors.get_icon_color()), 'Restore\nselected', toolbar)
        self.restore_selected_action.setEnabled(False)
        self.restore_selected_action.triggered.connect(self.restore_bak)
        toolbar.addAction(self.restore_selected_action)

        toolbar.addSeparator()

        self.remove_all_action = QAction(render_svg(REMOVE_ALL_ICON, 32, Colors.get_icon_color()), 'Remove all', toolbar)
        self.remove_all_action.setEnabled(False)
        self.remove_all_action.triggered.connect(self.remove_all_bak)
        toolbar.addAction(self.remove_all_action)

        self.restore_all_action = QAction(render_svg(RESTORE_ALL_ICON, 32, Colors.get_icon_color()), 'Restore all', toolbar)
        self.restore_all_action.setEnabled(False)
        self.restore_all_action.triggered.connect(self.restore_all_bak)
        toolbar.addAction(self.restore_all_action)

        self.files_table = QtWidgets.QTableWidget()
        self.files_table.setColumnCount(5)
        self.files_table.setHorizontalHeaderLabels(['File', 'Backup', 'Date', 'File size', 'Backup size'])
        self.files_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.files_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.files_table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        self.files_table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        self.files_table.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)
        self.files_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.files_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.files_table.itemSelectionChanged.connect(self.selection_changed)
        layout.addWidget(self.files_table)

        self.show()
