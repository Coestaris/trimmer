#!/usr/bin/env python3

#
# @file batch_encoding_dialog.py
# @date 26-02-2025
# @author Maxim Kurylko <vk_vm@ukr.net>
#

import logging
from typing import List

from PyQt5 import QtWidgets

from container import ContainerType
from ffmpeg import Codec

logger = logging.getLogger(__name__)

class BatchEncodingOptionsDialog(QtWidgets.QDialog):
    def __init__(self, codecs: list[Codec], preferred_codec: Codec, containers: List[ContainerType], preferred_container: ContainerType):
        super().__init__()
        self.setWindowTitle("Batch encoding options")
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        radio_group = QtWidgets.QButtonGroup()
        radio_group.setExclusive(True)

        gridwidget = QtWidgets.QWidget()
        gridlayout = QtWidgets.QGridLayout()
        gridwidget.setLayout(gridlayout)
        # No padding between widgets
        # gridlayout.setSpacing(0)
        layout.addWidget(gridwidget)

        self.codec_radio = QtWidgets.QRadioButton('Codec')
        gridlayout.addWidget(self.codec_radio, 0, 0)
        self.codec_select = QtWidgets.QComboBox()
        for codec in codecs:
            self.codec_select.addItem(codec.name)
        self.codec_select.setCurrentText(preferred_codec.name)
        self.codec_select.setEnabled(False)
        self.codec_radio.toggled.connect(lambda: self.codec_select.setEnabled(self.codec_radio.isChecked()))
        gridlayout.addWidget(self.codec_select, 0, 1)

        self.preset_radio = QtWidgets.QRadioButton('Preset')
        gridlayout.addWidget(self.preset_radio, 1, 0)
        self.preset_select = QtWidgets.QComboBox()
        self.preset_select.addItems(preferred_codec.presets)
        self.preset_select.setCurrentText(preferred_codec.preferred_preset)
        self.preset_select.setEnabled(False)
        self.preset_radio.toggled.connect(lambda: self.preset_select.setEnabled(self.preset_radio.isChecked()))
        self.preset_radio.setChecked(True)
        gridlayout.addWidget(self.preset_select, 1, 1)

        self.tune_radio = QtWidgets.QRadioButton('Tune')
        gridlayout.addWidget(self.tune_radio, 2, 0)
        self.tune_select = QtWidgets.QComboBox()
        self.tune_select.addItems(preferred_codec.tunes)
        self.tune_select.setCurrentText(preferred_codec.preferred_tune)
        self.tune_select.setEnabled(False)
        self.tune_radio.toggled.connect(lambda: self.tune_select.setEnabled(self.tune_radio.isChecked()))
        gridlayout.addWidget(self.tune_select, 2, 1)

        self.profile_radio = QtWidgets.QRadioButton('Profile')
        gridlayout.addWidget(self.profile_radio, 3, 0)
        self.profile_select = QtWidgets.QComboBox()
        self.profile_select.addItems(preferred_codec.profiles)
        self.profile_select.setCurrentText(preferred_codec.preferred_profile)
        self.profile_select.setEnabled(False)
        self.profile_radio.toggled.connect(lambda: self.profile_select.setEnabled(self.profile_radio.isChecked()))
        gridlayout.addWidget(self.profile_select, 3, 1)

        self.container_radio = QtWidgets.QRadioButton('Container')
        gridlayout.addWidget(self.container_radio, 4, 0)
        self.container_select = QtWidgets.QComboBox()
        self.container_select.addItems([container.ext for container in containers])
        self.container_select.setCurrentText(preferred_container.ext)
        self.container_select.setEnabled(False)
        self.container_radio.toggled.connect(lambda: self.container_select.setEnabled(self.container_radio.isChecked()))
        gridlayout.addWidget(self.container_select, 4, 1)

        dialog_buttons = QtWidgets.QDialogButtonBox()
        dialog_buttons.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel | QtWidgets.QDialogButtonBox.Ok)
        dialog_buttons.accepted.connect(self.accept)
        dialog_buttons.rejected.connect(self.reject)
        layout.addWidget(dialog_buttons)

    def accept(self):
        self.result_type = None
        if self.preset_radio.isChecked():
            self.result_type = "preset"
            self.result = self.preset_select.currentText()
        elif self.tune_radio.isChecked():
            self.result_type = "tune"
            self.result = self.tune_select.currentText()
        elif self.profile_radio.isChecked():
            self.result_type = "profile"
            self.result = self.profile_select.currentText()
        elif self.codec_radio.isChecked():
            self.result_type = "codec"
            self.result = self.codec_select.currentText()
        elif self.container_radio.isChecked():
            self.result_type = "container"
            self.result = self.container_select.currentText()
        else:
            logger.error('Unknown result type')
            return

        super().accept()
