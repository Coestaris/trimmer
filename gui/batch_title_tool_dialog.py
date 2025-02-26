#!/usr/bin/env python3

#
# @file batch_title_tool_dialog.py
# @date 26-02-2025
# @author Maxim Kurylko <vk_vm@ukr.net>
#

import logging
import os
import functools

from PyQt5 import QtWidgets

logger = logging.getLogger(__name__)

class BatchTitleToolDialog(QtWidgets.QDialog):
    def template_engine(self, template, title, file, index):
        if title is None:
            title = ''

        base = os.path.basename(file)
        base, ext = os.path.splitext(base)
        return (template
                .replace('%b', base)
                .replace('%e', ext)
                .replace('%i', str(index))
                .replace('%f', file)
                .replace('%t', title))

    def update_template(self, data):
        text = data
        self.selector = functools.partial(self.template_engine, text)
        self.example.setText(self.selector('Example Title', 'example.txt', 1))

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Batch title tool options")
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        label = QtWidgets.QLabel(
            'Tokens:\n'
            '  %t - title\n'
            '  %f - full file name\n'
            '  %b - base name without extension\n'
            '  %e - extension\n'
            '  %i - index'
        )
        layout.addWidget(label)

        edit = QtWidgets.QLineEdit()
        edit.setPlaceholderText('Enter title format')
        layout.addWidget(edit)

        label = 'Exmaple: '
        layout.addWidget(QtWidgets.QLabel(label))

        self.example = QtWidgets.QLabel()
        layout.addWidget(self.example)

        edit.textChanged.connect(self.update_template)
        edit.setText('%b')

        dialog_buttons = QtWidgets.QDialogButtonBox()
        dialog_buttons.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel | QtWidgets.QDialogButtonBox.Ok)
        dialog_buttons.accepted.connect(self.accept)
        dialog_buttons.rejected.connect(self.reject)
        layout.addWidget(dialog_buttons)

    def accept(self):
        super().accept()
