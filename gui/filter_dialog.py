#!/usr/bin/env python3

#
# @file filter_dialog.py
# @date 26-02-2025
# @author Maxim Kurylko <vk_vm@ukr.net>
#

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtGui import QIcon

class FilterDialog(QtWidgets.QDialog):
    def add_item(self):
        item = QtWidgets.QListWidgetItem('type here')
        item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
        # Start editing the item
        self.filter_list.addItem(item)
        self.filter_list.editItem(item)

    def accept(self):
        self.filters = [self.filter_list.item(i).text() for i in range(self.filter_list.count())]
        super().accept()

    def __init__(self, icon: QIcon, title: str):
        super().__init__()
        self.setWindowTitle(title)
        self.setWindowIcon(icon)
        # self.setGeometry(100, 100, 500, 500)

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        layout.addWidget(QtWidgets.QLabel(
            'Enter tokens to search in the track title,\n'
            'codec or language. Track will be selected\n'
            'if any of the tokens is found in the track.\n'
            'Tokens are case-insensitive\n'
            '* is special token to match any track'
        ))

        self.filter_list = QtWidgets.QListWidget()
        layout.addWidget(self.filter_list)

        add_button = QtWidgets.QPushButton('Add')
        add_button.clicked.connect(lambda: self.add_item())
        layout.addWidget(add_button)

        remove_button = QtWidgets.QPushButton('Remove')
        remove_button.clicked.connect(lambda: self.filter_list.takeItem(self.filter_list.currentRow()))
        layout.addWidget(remove_button)

        dialog_buttons = QtWidgets.QDialogButtonBox()
        dialog_buttons.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel | QtWidgets.QDialogButtonBox.Ok)
        dialog_buttons.accepted.connect(self.accept)
        dialog_buttons.rejected.connect(self.reject)
        layout.addWidget(dialog_buttons)
        self.add_item()
