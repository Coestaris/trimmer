#!/usr/bin/env python3

#
# @file icons.py
# @date 26-02-2025
# @author Maxim Kurylko <vk_vm@ukr.net>
#

from PyQt5 import QtGui
from PyQt5.QtGui import QPixmap, QPainter, QColor, QIcon

ADD_DIRECTORY_REC_ICON = "icons/folder-directory.svg"
RESTORE_ICON = "icons/time-past.svg"
BACKUP_TOOL_ICON = "icons/copy-alt.svg"
KEEP_ALL_ICON = "icons/border-all.svg"
KEEP_NONE_ICON = "icons/border-none.svg"
REMOVE_ALL_ICON = "icons/cross-circle.svg"
ADD_FILES_ICON = "icons/document.svg"
VIDEO_FILTER_ICON = "icons/film.svg"
ADD_DIRECTORY_ICON = "icons/folder-open.svg"
SUBTITLE_FILTER_ICON = "icons/poll-h.svg"
PROCESS_ICON = "icons/process.svg"
REMOVE_ICON = "icons/trash.svg"
AUDIO_FILTER_ICON = "icons/waveform-path.svg"
BATCH_ENCODING_OPTIONS_ICON = "icons/settings.svg"
APP_ICON = "icons/scissors.svg"
RESTORE_ALL_ICON = "icons/trash-restore.svg"
BATCH_TITLE_TOOL_ICON = "icons/id-card-clip-alt.svg"
SERIES_RENAME_TOOL_ICON = "icons/table-rows.svg"
UNDO_ICON = "icons/undo-alt.svg"
TEXT_ICON = "icons/text-box-edit.svg"
REGEX_ICON = "icons/medical-star.svg"

def render_svg(icon: str, size: int, color: str) -> QtGui.QIcon:
    img = QPixmap(icon)
    qp = QPainter(img)
    qp.setCompositionMode(QPainter.CompositionMode_SourceIn)
    qp.fillRect(img.rect(), QColor(color))
    qp.end()
    return QIcon(img)