#!/usr/bin/env python3

#
# @file gui.py
# @date 24-02-2025
# @author Maxim Kurylko <kurylko.m@ajax.systems>
#

import logging
import os
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtGui import QIcon

from ffmpeg import find_ffmpeg, find_ffprobe, get_supported_hevc_encoders, \
    VideoTrack, AudioTrack, SubtitleTrack, prefer_hevc_encoder
from mkv_file import MKVFile
from utils import get_gpu_name

logger = logging.getLogger(__name__)


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

TYPE_ALIASES = {
    VideoTrack: 'Video',
    AudioTrack: 'Audio',
    SubtitleTrack: 'Subtitle',
}

TYPE_COLORS = {
    # Pale white-like colors
    VideoTrack: '#CEEAD6',
    AudioTrack: '#FEEFC3',
    SubtitleTrack: '#FAD2CF'
}

LANGUAGE_COLORS = [
    '#CEEAD6', # Green
    '#D4E6F1', # Blue
    '#E2E2E2', # Gray
    '#FAD2CF', # Red
    '#FEEFC3', # Yellow
    '#F5F5F5', # Light gray
    '#F8F8F8', # Lighter gray
    '#F0F0F0', # Lightest gray
]

def pretty_duration(seconds: float) -> str:
    if seconds == 0:
        return "unknown"

    if seconds < 120:
        return f'{int(seconds):02} seconds'
    elif seconds < 3600:
        minutes, seconds = divmod(seconds, 60)
        return f'{int(minutes):02}:{int(seconds):02}'
    else:
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        return f'{int(hours):02}:{int(minutes):02}:{int(seconds):02}'

def pretty_size(size: int) -> str:
    if size < 1024:
        return f'{size} B'
    elif size < 1024 * 1024:
        return f'{size / 1024:.2f} KB'
    elif size < 1024 * 1024 * 1024:
        return f'{size / 1024 / 1024:.2f} MB'
    else:
        return f'{size / 1024 / 1024 / 1024:.2f} GB'

def file_track_summary(mkvfile: MKVFile) -> str:
    d = {}
    for track in mkvfile.tracks:
        if not track.keep:
            continue

        t = type(track)
        d[t] = d.get(t, []) + [track.language]

    return ', '.join([f'{TYPE_ALIASES[k]}: [{', '.join(v)}]' for k, v in d.items()])

class CustomTableWidgetItem(QtWidgets.QTableWidgetItem):
    def __init__(self, text, custom_data):
        super().__init__(text)
        self.custom_data = custom_data

class FilterDialog(QtWidgets.QDialog):
    def add_item(self):
        item = QtWidgets.QListWidgetItem('filter')
        item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
        # Start editing the item
        self.filter_list.addItem(item)
        self.filter_list.editItem(item)

    def accept(self):
        self.filters = [self.filter_list.item(i).text() for i in range(self.filter_list.count())]
        super().accept()

    def __init__(self, title: str):
        super().__init__()
        self.setWindowTitle(title)
        # self.setGeometry(100, 100, 500, 500)

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        layout.addWidget(QtWidgets.QLabel('Filters are case-insensitive'))
        layout.addWidget(QtWidgets.QLabel('Use * to match any value'))

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

class GUI(QtWidgets.QMainWindow):
    def __init__(self, files: list[str]):
        super().__init__()
        self.init_ui()
        self.files = []

        self.ffmpeg = find_ffmpeg()
        self.ffprobe = find_ffprobe()
        self.gpu_name = get_gpu_name()
        self.hevc_encoders = get_supported_hevc_encoders(self.ffmpeg)
        self.preferred_encoder = prefer_hevc_encoder(self.hevc_encoders, self.gpu_name)
        self.preferred_preset = 'slow'

        logger.info('FFMpeg: %s', self.ffmpeg)
        logger.info('FFProbe: %s', self.ffprobe)
        logger.info('GPU: %s', self.gpu_name)
        logger.info('HEVC encoders: %s', self.hevc_encoders)
        logger.info('Preferred encoder: %s', self.preferred_encoder)
        logger.info('Preferred preset: %s', self.preferred_preset)
        # TODO: Popup error message if ffmpeg or ffprobe is not found

        if len(files) != 0:
            for file in files:
                self.open_file(file)
            self.update_files_table()

    def open_file(self, file: str):
        mkvfile = MKVFile(file)
        try:
            mkvfile.parse(self.ffprobe)
        except Exception as e:
            # TODO: Popup error message
            logger.exception('Error parsing file %s: %s', file, e)
            return

        self.files.append(mkvfile)

    def update_files_table(self):
        self.files_table.setRowCount(len(self.files))
        for i, mkvfile in enumerate(self.files):
            self.files_table.setItem(i, 0, CustomTableWidgetItem(os.path.basename(mkvfile.file), mkvfile))
            self.files_table.setItem(i, 1, QtWidgets.QTableWidgetItem(pretty_duration(mkvfile.duration_seconds)))
            self.files_table.setItem(i, 2, QtWidgets.QTableWidgetItem(file_track_summary(mkvfile)))

    def on_file_selected(self):
        index = self.files_table.currentRow()
        if index == -1:
            # Clear metadata and tracks
            self.file_metadata.clear()
            self.file_tracks.setRowCount(0)
            return

        mkvfile = self.files_table.item(index, 0).custom_data

        # Fill metadata
        self.file_metadata.clear()
        data = {
            'File': mkvfile.file,
            'Duration': f'{pretty_duration(mkvfile.duration_seconds)} ({mkvfile.duration_frames} frames)',
            'File size': pretty_size(os.path.getsize(mkvfile.file)),
        }
        self.file_metadata.setText('\n'.join([f'{k}: {v}' for k, v in data.items()]))

        language_colors = {}
        for i, track in enumerate(mkvfile.tracks):
            language = track.language
            if language not in language_colors:
                language_colors[language] = LANGUAGE_COLORS[len(language_colors) % len(LANGUAGE_COLORS)]

        # Fill tracks
        self.file_tracks.setRowCount(len(mkvfile.tracks))
        for i, track in enumerate(mkvfile.tracks):
            keep_checkbox = QtWidgets.QCheckBox()
            keep_checkbox.setChecked(track.keep)
            def update(state, t=track):
                t.keep = state == QtCore.Qt.Checked
                self.update_files_table()

            keep_checkbox.stateChanged.connect(update)

            self.file_tracks.setCellWidget(i, 0, keep_checkbox)
            self.file_tracks.setItem(i, 1, QtWidgets.QTableWidgetItem(TYPE_ALIASES[type(track)]))
            self.file_tracks.item(i, 1).setBackground(QtGui.QColor(TYPE_COLORS[type(track)]))
            self.file_tracks.setItem(i, 2, QtWidgets.QTableWidgetItem(track.codec))
            self.file_tracks.setItem(i, 3, QtWidgets.QTableWidgetItem(track.language))
            self.file_tracks.item(i, 3).setBackground(QtGui.QColor(language_colors[track.language]))
            self.file_tracks.setItem(i, 4, QtWidgets.QTableWidgetItem(track.title))
            self.file_tracks.setItem(i, 5, QtWidgets.QTableWidgetItem(pretty_duration(track.duration)))
            if isinstance(track, VideoTrack):
                self.file_tracks.setItem(i, 6, QtWidgets.QTableWidgetItem(f'{track.frame_rate:.2f} FPS'))
            elif isinstance(track, AudioTrack):
                self.file_tracks.setItem(i, 6, QtWidgets.QTableWidgetItem(f'{track.channels} channels'))
            else:
                self.file_tracks.setItem(i, 6, QtWidgets.QTableWidgetItem(''))

    def add_files(self):
        logger.info('Add files')
        dialog = QtWidgets.QFileDialog()
        dialog.setFileMode(QtWidgets.QFileDialog.ExistingFiles)
        dialog.setNameFilter('MKV files (*.mkv)')
        if dialog.exec_():
            files = dialog.selectedFiles()
            for file in files:
                self.open_file(file)
            self.update_files_table()

    def add_directory(self):
        logger.info('Add directory')
        dialog = QtWidgets.QFileDialog()
        dialog.setFileMode(QtWidgets.QFileDialog.Directory)
        if dialog.exec_():
            directory = dialog.selectedFiles()[0]
            for root, _, files in os.walk(directory):
                for file in files:
                    if file.endswith('.mkv'):
                        self.open_file(os.path.join(root, file))
            self.update_files_table()

    def remove_selected(self):
        logger.info('Remove selected')
        self.files_table.removeRow(self.files_table.currentRow())

    def remove_all(self):
        logger.info('Remove all')
        self.files_table.setRowCount(0)

    def filter(self, filters: list[str], t: type):
        logger.info('Filters: %s', filters)
        for mkvfile in self.files:
            for track in mkvfile.tracks:
                if isinstance(track, t):
                    track.keep = False
                    for filter in filters:
                        if filter == '*':
                            track.keep = True
                            break
                        if filter.lower() in track.language.lower():
                            track.keep = True
                            break
                        if filter.lower() in track.title.lower():
                            track.keep = True
                            break
                        if filter.lower() in track.codec.lower():
                            track.keep = True
                            break
        self.update_files_table()
        self.on_file_selected()

    def audio_filter(self):
        logger.info('Audio filter')
        filter = FilterDialog('Audio filter')
        if filter.exec_():
            self.filter(filter.filters, AudioTrack)

    def video_filter(self):
        logger.info('Video filter')
        filter = FilterDialog('Video filter')
        if filter.exec_():
            self.filter(filter.filters, VideoTrack)

    def subtitle_filter(self):
        logger.info('Subtitle filter')
        filter = FilterDialog('Audio filter')
        if filter.exec_():
            self.filter(filter.filters, SubtitleTrack)

    def keep_all(self):
        logger.info('Keep all')
        for mkvfile in self.files:
            for track in mkvfile.tracks:
                track.keep = True
        self.update_files_table()
        self.on_file_selected()

    def keep_none(self):
        logger.info('Keep none')
        for mkvfile in self.files:
            for track in mkvfile.tracks:
                track.keep = False
        self.update_files_table()
        self.on_file_selected()

    def process(self):
        def on_progress(frame: int, fps: float):
            logger.info('Progress: %d frames, %f FPS', frame, fps)

        for mkvfile in self.files:
            if not mkvfile.remux(self.ffmpeg, self.preferred_preset, self.preferred_encoder, on_progress):
                logger.error('Failed to process file %s', mkvfile.file)

    def init_ui(self):
        self.setWindowTitle('MKV Trimmer')
        # self.setGeometry(100, 100, 1500, 900)
        self.setMinimumSize(1600, 1000)

        # layout = QtWidgets.QVBoxLayout()
        self.main_tabwidget = QtWidgets.QTabWidget()
        self.files_tab = QtWidgets.QWidget()
        self.process_tab = QtWidgets.QWidget()

        self.main_tabwidget.addTab(self.files_tab, 'Files')
        files_tab_layout = QtWidgets.QVBoxLayout()
        self.files_tab.setLayout(files_tab_layout)

        toolbar = QtWidgets.QToolBar()
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setOrientation(QtCore.Qt.Horizontal)
        toolbar.setIconSize(QtCore.QSize(32, 32))
        toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        toolbar.addAction(QIcon(ADD_FILES_ICON), 'Add files', lambda: self.add_files())
        toolbar.addAction(QIcon(ADD_DIRECTORY_ICON), 'Add directory', lambda: self.add_directory())
        toolbar.addAction(QIcon(REMOVE_ICON), 'Remove selected', lambda: self.remove_selected())
        toolbar.addAction(QIcon(REMOVE_ALL_ICON), 'Remove all', lambda: self.remove_all())
        toolbar.addSeparator()
        toolbar.addAction(QIcon(AUDIO_FILTER_ICON), 'Audio filter', lambda: self.audio_filter())
        toolbar.addAction(QIcon(VIDEO_FILTER_ICON), 'Video filter', lambda: self.video_filter())
        toolbar.addAction(QIcon(SUBTITLE_FILTER_ICON), 'Subtitle filter', lambda: self.subtitle_filter())
        toolbar.addAction(QIcon(KEEP_ALL_ICON), 'Keep all', lambda: self.keep_all())
        toolbar.addAction(QIcon(KEEP_NONE_ICON), 'Keep none', lambda: self.keep_none())
        toolbar.addSeparator()
        toolbar.addAction(QIcon(PROCESS_ICON), 'Process', lambda: self.process())
        files_tab_layout.addWidget(toolbar)

        # Make horizontal splitter. Top - table, bottom - details
        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)

        self.files_table = QtWidgets.QTableWidget()
        self.files_table.setColumnCount(3)
        self.files_table.setHorizontalHeaderLabels(['File', 'Duration', 'Tracks summary'])
        # Make duration to take as little space as possible
        self.files_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.files_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.files_table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        self.files_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.files_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.files_table.itemSelectionChanged.connect(self.on_file_selected)
        self.files_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        splitter.addWidget(self.files_table)

        self.file_tracks = QtWidgets.QTableWidget()
        self.file_tracks.setColumnCount(7)
        self.file_tracks.setHorizontalHeaderLabels(['Keep', 'Type', 'Codec', 'Language', 'Title', 'Duration', 'FPS/Channels'])
        self.file_tracks.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.file_tracks.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.file_tracks.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        self.file_tracks.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        self.file_tracks.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.Stretch)
        self.file_tracks.horizontalHeader().setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeToContents)
        self.file_tracks.horizontalHeader().setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeToContents)
        self.file_tracks.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.file_tracks.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.file_tracks.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        splitter.addWidget(self.file_tracks)

        self.file_metadata = QtWidgets.QLabel()
        self.file_metadata.setWordWrap(True)
        splitter.addWidget(self.file_metadata)

        files_tab_layout.addWidget(splitter)

        self.main_tabwidget.addTab(self.process_tab, 'Process')
        process_tab_layout = QtWidgets.QVBoxLayout()
        self.process_tab.setLayout(process_tab_layout)
        process_tab_layout.addWidget(QtWidgets.QLabel('Process'))

        self.setCentralWidget(self.main_tabwidget)

TEST_FILES = [
    "\\\\192.168.3.68\\share\\ext\\TE\\Inception.2010.1080p.BluRay.x264.5xRus.Eng-Otaibi.mkv",
    "\\\\192.168.3.68\\share\\ext\\TE\\Once Upon a Time ... in Hollywood (2019) 1080p.mkv",
]

def run_gui():
    app = QtWidgets.QApplication([])
    gui = GUI(TEST_FILES)

    gui.show()
    app.exec_()