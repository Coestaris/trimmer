#!/usr/bin/env python3

#
# @file backup_manager.py
# @date 24-02-2025
# @author Maxim Kurylko <vk_vm@ukr.net>
#

import logging
import os
import shutil
from time import gmtime, strftime

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtGui import QIcon

from utils import pretty_size

logger = logging.getLogger(__name__)

RESTORE_ICON = "icons/time-past.svg"
ADD_FILES_ICON = "icons/document.svg"
ADD_DIRECTORY_ICON = "icons/folder-open.svg"
ADD_DIRECTORY_REC_ICON = "icons/folder-directory.svg"
REMOVE_ICON = "icons/cross-circle.svg"
REMOVE_ALL_ICON = "icons/trash.svg"
RESTORE_ALL_ICON = "icons/trash-restore.svg"

class BackupManager(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.init_ui()
        self.files = []

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
        self.files_table.setRowCount(len(self.files))
        self.files_table.setItem(len(self.files) - 1, 0, QtWidgets.QTableWidgetItem(nobak))
        self.files_table.setItem(len(self.files) - 1, 1, QtWidgets.QTableWidgetItem(file))
        self.files_table.setItem(len(self.files) - 1, 2, QtWidgets.QTableWidgetItem(strftime('%d-%m-%Y %H:%M:%S', gmtime(os.path.getmtime(file)))))
        self.files_table.setItem(len(self.files) - 1, 3, QtWidgets.QTableWidgetItem(pretty_size(os.path.getsize(nobak))))
        self.files_table.setItem(len(self.files) - 1, 4, QtWidgets.QTableWidgetItem(pretty_size(os.path.getsize(file))))

    def restore_file(self, file):
        nobak = self.get_nobak(file)
        logger.info("copy %s to %s", file, nobak)
        shutil.copy(file, nobak)
        logger.info("remove %s", file)
        os.remove(file)

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
        dialog.setNameFilter('All files (*)')
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
        self.remove_file(file)
        self.files_table.removeRow(index)

    def restore_all_bak(self):
        for file in self.files:
            self.restore_file(file)
        self.files_table.setRowCount(0)

    def restore_bak(self):
        index = self.files_table.currentRow()
        if index < 0:
            return

        file = self.files[index]
        self.restore_file(file)
        self.files_table.removeRow(index)

    def remove_all_bak(self):
        for file in self.files:
            self.remove_file(file)
        self.files_table.setRowCount(0)

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
        toolbar.addAction(QIcon(ADD_FILES_ICON), 'Add files', self.add_files)
        toolbar.addAction(QIcon(ADD_DIRECTORY_ICON), 'Add directory', self.add_files)
        toolbar.addAction(QIcon(ADD_DIRECTORY_ICON), 'Add directory\nrecursively', self.add_files)
        toolbar.addSeparator()
        toolbar.addAction(QIcon(REMOVE_ICON), 'Remove\nselected', self.remove_bak)
        toolbar.addAction(QIcon(RESTORE_ICON), 'Restore\nselected', self.restore_all_bak)
        toolbar.addSeparator()
        toolbar.addAction(QIcon(REMOVE_ALL_ICON), 'Remove all', self.remove_bak)
        toolbar.addAction(QIcon(RESTORE_ALL_ICON), 'Restore all', self.restore_all_bak)

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
        layout.addWidget(self.files_table)

        self.show()
