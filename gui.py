#!/usr/bin/env python3

#
# @file gui.py
# @date 24-02-2025
# @author Maxim Kurylko <vk_vm@ukr.net>
#

import logging
import os
import time
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtGui import QIcon

from backup_manager import BackupManager
from ffmpeg import find_ffmpeg, find_ffprobe, get_supported_hevc_codecs, \
    VideoTrack, AudioTrack, SubtitleTrack, Codec
from mkv_file import MKVFile
from preferences import prefer_hevc_codec
from utils import get_gpu_name, ETACalculator, pretty_duration, pretty_size

logger = logging.getLogger(__name__)

RESTORE_ICON = "icons/time-past.svg"
BACKUP_MANAGER_ICON = "icons/copy-alt.svg"
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

STATUS_COLORS = {
    'pending': '#F5F5F5',
    'working': '#D4E6F1',
    'done': '#CEEAD6',
    'error': '#FEEFC3'
}

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

class BatchEncodingOptionsDialog(QtWidgets.QDialog):
    def __init__(self, codecs: list[Codec], preferred_codec: Codec):
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
        else:
            logger.error('Unknown result type')
            return

        super().accept()

class GUI(QtWidgets.QMainWindow):
    def popup_error(self, message: str):
        QtWidgets.QMessageBox.critical(self, 'Error', message)

    def __init__(self, files: list[str]):
        super().__init__()
        self.init_ui()
        self.files = []

        self.processing_thread = QtCore.QThread()
        self.worker = None

        self.ffmpeg = find_ffmpeg()
        if self.ffmpeg.is_err():
            self.popup_error(f"Unable to find ffmpeg: {self.ffmpeg.err()}. Make sure it is installed and in PATH")
            return
        self.ffmpeg = self.ffmpeg.unwrap()

        self.ffprobe = find_ffprobe()
        if self.ffprobe.is_err():
            self.popup_error(f"Unable to find ffprobe: {self.ffprobe.err()}. Make sure it is installed and in PATH")
            return
        self.ffprobe = self.ffprobe.unwrap()

        self.gpu_name = get_gpu_name()
        if self.gpu_name.is_err():
            self.popup_error(f"Unable to get GPU name: {self.gpu_name.err()}")
            return
        self.gpu_name = self.gpu_name.unwrap()

        self.supported_codecs = get_supported_hevc_codecs(self.ffmpeg)
        if self.supported_codecs.is_err():
            self.popup_error(f"Unable to get supported codecss: {self.supported_codecs.err()}")
            return
        self.supported_codecs = self.supported_codecs.unwrap()

        self.preferred_codec = prefer_hevc_codec(self.supported_codecs, self.gpu_name)
        if self.preferred_codec.is_err():
            self.popup_error(f'No suitable HEVC codec found: {self.preferred_codec.err()}')
            return
        self.preferred_codec = self.preferred_codec.unwrap()

        logger.info('FFMpeg: %s', self.ffmpeg)
        logger.info('FFProbe: %s', self.ffprobe)
        logger.info('GPU: %s', self.gpu_name)
        logger.info('HEVC codecs: %s', self.supported_codecs)
        logger.info('Preferred codec: %s', self.preferred_codec)

        if len(files) != 0:
            for file in files:
                self.open_file(file)
            self.update_files_table()

        self.setAcceptDrops(True)

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
            self.open_file(url.toLocalFile())
        self.update_files_table()

    def open_file(self, file: str):
        for f in self.files:
            if f.file == file:
                logger.info('File %s already opened', file)
                return

        logger.info('Opening file: %s', file)
        mkvfile = MKVFile(file, self.preferred_codec)
        try:
            if (res := mkvfile.parse(self.ffprobe)).is_err():
                self.popup_error(f'Failed to parse file {file}: {res.unwrap_err()}')
                return
        except Exception as e:
            self.popup_error(f'Error parsing file {file}: {e}')
            logger.exception('Error parsing file %s: %s', file, e)
            return

        self.files.append(mkvfile)

    def update_files_table(self):
        self.files_table.setRowCount(len(self.files))
        for i, mkvfile in enumerate(self.files):
            self.files_table.setItem(i, 0, CustomTableWidgetItem(os.path.basename(mkvfile.file), mkvfile))

            codec_select = QtWidgets.QComboBox()
            for codec in self.supported_codecs:
                codec_select.addItem(codec.name, codec)
            codec_select.setCurrentText(mkvfile.codec.name)
            self.files_table.setCellWidget(i, 1, codec_select)

            preset_select = QtWidgets.QComboBox()
            preset_select.addItems(mkvfile.codec.presets)
            preset_select.setCurrentText(mkvfile.preset)
            def update_preset(preset, f=mkvfile):
                f.preset = preset
                self.on_file_selected()
            preset_select.currentTextChanged.connect(update_preset)
            self.files_table.setCellWidget(i, 2, preset_select)

            tune_select = QtWidgets.QComboBox()
            tune_select.addItems(mkvfile.codec.tunes)
            tune_select.setCurrentText(mkvfile.tune)
            def update_tune(tune, f=mkvfile):
                f.tune = tune
                self.on_file_selected()
            tune_select.currentTextChanged.connect(update_tune)
            self.files_table.setCellWidget(i, 3, tune_select)

            profile_select = QtWidgets.QComboBox()
            profile_select.addItems(mkvfile.codec.profiles)
            profile_select.setCurrentText(mkvfile.profile)
            def update_profile(profile, f=mkvfile):
                f.profile = profile
                self.on_file_selected()
            profile_select.currentTextChanged.connect(update_profile)
            self.files_table.setCellWidget(i, 4, profile_select)

            def update_codec(codec_name, f=mkvfile, codec_select=codec_select, preset_select=preset_select, tune_select=tune_select, profile_select=profile_select):
                codec = next((c for c in self.supported_codecs if c.name == codec_name), None)

                f.codec = codec
                f.preset = codec.preferred_preset
                f.tune = codec.preferred_tune
                f.profile = codec.preferred_profile

                preset_select.clear()
                preset_select.addItems(codec.presets)
                preset_select.setCurrentText(codec.preferred_preset)

                tune_select.clear()
                tune_select.addItems(codec.tunes)
                tune_select.setCurrentText(codec.preferred_tune)

                profile_select.clear()
                profile_select.addItems(codec.profiles)
                profile_select.setCurrentText(codec.preferred_profile)

                self.on_file_selected()
            codec_select.currentTextChanged.connect(update_codec)

            self.files_table.setItem(i, 5, QtWidgets.QTableWidgetItem(pretty_duration(mkvfile.duration_seconds)))
            self.files_table.setItem(i, 6, QtWidgets.QTableWidgetItem(file_track_summary(mkvfile)))

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
            'File': f'"{mkvfile.file}"',
            'Duration': f'{pretty_duration(mkvfile.duration_seconds)} ({mkvfile.duration_frames} frames)',
            'File size': pretty_size(os.path.getsize(mkvfile.file)),
            'Video':
                'is H.265: ' + ('Yes' if any(track.is_h265() for track in mkvfile.tracks if track.keep and isinstance(track, VideoTrack)) else 'No') + \
                f', codec: "{mkvfile.codec.name}", preset: "{mkvfile.preset}", tune: "{mkvfile.tune}", profile: "{mkvfile.profile}"'
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

    def backup_manager(self):
        logger.info('Backup manager')
        dialog = BackupManager()
        dialog.exec_()

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

    def batch_encoding_options(self):
        logger.info('Batch encoding options')
        codecs = list(set([file.codec for file in self.files]))
        if len(codecs) != 1:
            codec = self.preferred_codec
        else:
            codec = codecs[0]

        dialog = BatchEncodingOptionsDialog(self.supported_codecs, codec)
        if dialog.exec_():
            def update_all(updater, value):
                for mkvfile in self.files:
                    updater(value, mkvfile)
                self.update_files_table()
                self.on_file_selected()

            def update_codec(codec_name, f):
                codec = next((c for c in self.supported_codecs if c.name == codec_name), None)

                f.codec = codec
                f.preset = codec.preferred_preset
                f.tune = codec.preferred_tune
                f.profile = codec.preferred_profile

            if dialog.result_type == "preset":
                update_all(lambda preset, f: setattr(f, 'preset', preset), dialog.result)
            elif dialog.result_type == "tune":
                update_all(lambda tune, f: setattr(f, 'tune', tune), dialog.result)
            elif dialog.result_type == "profile":
                update_all(lambda profile, f: setattr(f, 'profile', profile), dialog.result)
            elif dialog.result_type == "codec":
                update_all(lambda codec, f: update_codec(codec, f), dialog.result)
            else:
                logger.error('Unknown result type: %s', dialog.result_type)


    def process(self):
        # Change tab
        self.main_tabwidget.setCurrentIndex(1)

        class Worker(QtCore.QObject):
            ffmpeg_process = QtCore.pyqtSignal(int, int, float)
            file_update = QtCore.pyqtSignal(int, str)
            finished = QtCore.pyqtSignal()
            error_message = QtCore.pyqtSignal(str)

            def __init__(self, files: list[MKVFile], ffmpeg: str):
                super().__init__()
                self.files = files
                self.ffmpeg = ffmpeg

            def run(self):
                logger.info('Processing %d files', len(self.files))

                for i, mkvfile in enumerate(self.files):
                    def on_progress(frame: int, fps: float, index=i):
                        self.ffmpeg_process.emit(index, frame, fps)

                    self.file_update.emit(i, 'working')
                    if (res := mkvfile.remux(self.ffmpeg, on_progress)).is_err():
                        self.file_update.emit(i, 'error')
                        self.error_message.emit(f'Failed to process file {mkvfile.file}: {res.unwrap_err()}')
                    else:
                        self.file_update.emit(i, 'done')

                logger.info('All files processed')
                self.finished.emit()

        class FileStatus:
            def __init__(self, file: MKVFile):
                self.file = file
                self.total_frames = file.duration_frames
                self.start_time = time.time()
                self.eta = ETACalculator(self.start_time, 0)
                self.set_status('pending')

            def set_status(self, status: str):
                self.status = status
                self.update_time = time.time()
                if self.status == 'done' or self.status == 'error':
                    self.completed_percent = 100
                if self.status == 'pending' or self.status == 'working':
                    self.completed_percent = 0
                    self.eta.reset(time.time(), 0)

            def update_progress(self, frame: int):
                self.completed_percent = int(frame / self.total_frames * 100)
                self.eta.feed(self.completed_percent)
                self.update_time = time.time()

        file_statuses = [
            FileStatus(mkvfile) for mkvfile in self.files
        ]

        self.overall_progress_label.setText('')
        self.overall_progress.setValue(0)
        self.current_progress_label.setText('')
        self.current_progress.setValue(0)

        start_time = time.time()
        overall_eta = ETACalculator(start_time, 0)

        def update_overall_progress():
            total_percent = sum(status.completed_percent for status in file_statuses) / len(file_statuses)
            overall_eta.feed(total_percent)
            self.overall_progress.setValue(int(total_percent))
            self.overall_progress.setFormat(f'{total_percent:.2f}%')
            self.overall_progress_label.setText(
                f'Overall progress: {total_percent:.2f}%. '
                f'Time elapsed: {pretty_duration(time.time() - start_time)}. '
                f'ETA: {pretty_duration(overall_eta.get())}'
            )

        def update_file_status_with_gui(index, status):
            file_statuses[index].set_status(status)
            self.process_table.setItem(index, 1, QtWidgets.QTableWidgetItem(status))
            self.process_table.item(index, 1).setBackground(QtGui.QColor(STATUS_COLORS[status]))
            self.process_table.setItem(index, 2, QtWidgets.QTableWidgetItem(str(time.strftime('%H:%M:%S'))))
            update_overall_progress()

        def on_progress(index, frame: int, fps: float):
            logger.info('Progress: %d frames, %f FPS', frame, fps)

            status = file_statuses[index]
            status.update_progress(frame)

            self.current_progress.setValue(int(status.completed_percent))
            self.current_progress.setFormat(f'{os.path.basename(status.file.file)} - {status.completed_percent}%')
            self.current_progress_label.setText(
                f'FPS: {fps:.2f} ({fps / status.file.fps:.2f}x of realtime). ' 
                f'{frame}/{status.total_frames} frames processed. '
                f'Time elapsed: {pretty_duration(time.time() - status.start_time)}. '
                f'ETA: {pretty_duration(status.eta.get())}'
            )

            update_overall_progress()

        # Add files to process
        self.process_table.setRowCount(len(self.files))
        for i, file_status in enumerate(file_statuses):
            self.process_table.setItem(i, 0, QtWidgets.QTableWidgetItem(os.path.basename(file_status.file.file)))
            update_file_status_with_gui(i, 'pending')

        self.worker = Worker(self.files, self.ffmpeg)
        self.worker.ffmpeg_process.connect(on_progress)
        self.worker.file_update.connect(update_file_status_with_gui)
        self.worker.error_message.connect(self.popup_error)
        self.worker.moveToThread(self.processing_thread)

        self.processing_thread.started.connect(self.worker.run)
        self.processing_thread.finished.connect(self.processing_thread.deleteLater)
        self.worker.finished.connect(self.processing_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)

        self.processing_thread.start()

    def init_ui(self):
        self.setWindowTitle('MKV Trimmer')
        self.setBaseSize(1600, 1000)

        self.main_tabwidget = QtWidgets.QTabWidget()
        self.main_tabwidget.tabBar().hide()

        def files_tab() -> QtWidgets.QWidget:
            files_tab = QtWidgets.QWidget()
            files_tab_layout = QtWidgets.QVBoxLayout()

            toolbar = QtWidgets.QToolBar()
            toolbar.setMovable(False)
            toolbar.setFloatable(False)
            toolbar.setOrientation(QtCore.Qt.Horizontal)
            toolbar.setIconSize(QtCore.QSize(32, 32))
            toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
            toolbar.addAction(QIcon(BACKUP_MANAGER_ICON), 'Backup manager', lambda: self.backup_manager())
            toolbar.addSeparator()
            toolbar.addAction(QIcon(ADD_FILES_ICON), 'Add files', lambda: self.add_files())
            toolbar.addAction(QIcon(ADD_DIRECTORY_ICON), 'Add directory', lambda: self.add_directory())
            toolbar.addAction(QIcon(REMOVE_ICON), 'Remove\nselected', lambda: self.remove_selected())
            toolbar.addAction(QIcon(REMOVE_ALL_ICON), 'Remove all', lambda: self.remove_all())
            toolbar.addSeparator()
            toolbar.addAction(QIcon(AUDIO_FILTER_ICON), 'Audio filter', lambda: self.audio_filter())
            toolbar.addAction(QIcon(VIDEO_FILTER_ICON), 'Video filter', lambda: self.video_filter())
            toolbar.addAction(QIcon(SUBTITLE_FILTER_ICON), 'Subtitle filter', lambda: self.subtitle_filter())
            toolbar.addAction(QIcon(KEEP_ALL_ICON), 'Keep all', lambda: self.keep_all())
            toolbar.addAction(QIcon(KEEP_NONE_ICON), 'Keep none', lambda: self.keep_none())
            toolbar.addSeparator()
            toolbar.addAction(QIcon(BATCH_ENCODING_OPTIONS_ICON), 'Batch codec\noptions', lambda: self.batch_encoding_options())
            toolbar.addSeparator()
            toolbar.addAction(QIcon(PROCESS_ICON), 'Process', lambda: self.process())
            files_tab_layout.addWidget(toolbar)

            # Make horizontal splitter. Top - table, bottom - details
            splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)

            self.files_table = QtWidgets.QTableWidget()
            self.files_table.setColumnCount(7)
            self.files_table.setHorizontalHeaderLabels(['File', 'Codec', 'Preset', 'Tune', 'Profile', 'Duration', 'Tracks summary'])
            # Make duration to take as little space as possible
            self.files_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
            self.files_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
            self.files_table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
            self.files_table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
            self.files_table.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)
            self.files_table.horizontalHeader().setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeToContents)
            self.files_table.horizontalHeader().setSectionResizeMode(6, QtWidgets.QHeaderView.Stretch)
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
            files_tab.setLayout(files_tab_layout)
            return files_tab

        def process_tab() -> QtWidgets.QWidget:
            process_tab = QtWidgets.QWidget()
            process_tab_layout = QtWidgets.QVBoxLayout()

            # Table of files to process
            self.process_table = QtWidgets.QTableWidget()
            self.process_table.setColumnCount(3)
            self.process_table.setHorizontalHeaderLabels(['File', 'Status', 'Updated'])
            self.process_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
            self.process_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
            self.process_table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
            process_tab_layout.addWidget(self.process_table)

            # Two progress bars: one for current file, one for overall progress + label below them
            self.current_progress = QtWidgets.QProgressBar()
            self.current_progress.setRange(0, 100)
            self.current_progress.setValue(40)
            self.current_progress.setFormat('Current file: %p%')
            process_tab_layout.addWidget(self.current_progress)

            self.current_progress_label = QtWidgets.QLabel('Current progress: 40%. Time left: 1:23')
            process_tab_layout.addWidget(self.current_progress_label)

            self.overall_progress = QtWidgets.QProgressBar()
            self.overall_progress.setRange(0, 100)
            self.overall_progress.setValue(40)
            self.overall_progress.setFormat('Overall progress: %p%')
            process_tab_layout.addWidget(self.overall_progress)

            self.overall_progress_label = QtWidgets.QLabel('Overall progress: 40%. Time left: 1:23')
            process_tab_layout.addWidget(self.overall_progress_label)

            process_tab.setLayout(process_tab_layout)
            return process_tab

        self.files_tab = files_tab()
        self.main_tabwidget.addTab(self.files_tab, 'Files')

        self.process_tab = process_tab()
        self.main_tabwidget.addTab(self.process_tab, 'Process')

        self.setCentralWidget(self.main_tabwidget)

# TEST_FILES = [
#     "\\\\192.168.3.68\\share\\ext\\TE\\Inception.2010.1080p.BluRay.x264.5xRus.Eng-Otaibi.mkv",
#     "\\\\192.168.3.68\\share\\ext\\TE\\Once Upon a Time ... in Hollywood (2019) 1080p.mkv",
# ]
TEST_FILES = [
    "/home/taris/downloads/South Park - S25E01 - Pajama Day.mkv",
    "/home/taris/downloads/South Park - S25E02 - The Big Fix.mkv",
]

def run_gui():
    app = QtWidgets.QApplication([])
    app.setWindowIcon(QIcon(APP_ICON))
    gui = GUI(TEST_FILES)

    gui.show()
    app.exec_()