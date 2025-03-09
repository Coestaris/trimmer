#!/usr/bin/env python3

#
# @file main_window.py
# @date 26-02-2025
# @author Maxim Kurylko <vk_vm@ukr.net>
#

import logging
import os
import platform
import time
from abc import abstractmethod
from typing import List

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QAction

from __version__ import __version__
from codec import prefer_hevc_codec
from container import Container, SUPPORTED_CONTAINERS, PREFERRED_CONTAINER
from ffmpeg import VideoTrack, AudioTrack, SubtitleTrack, get_supported_hevc_codecs
from gui.backup_manager_dialog import BackupManager
from gui.batch_encoding_dialog import BatchEncodingOptionsDialog
from gui.batch_title_tool_dialog import BatchTitleToolDialog
from gui.colors import Colors
from gui.filter_dialog import FilterDialog
from gui.icons import render_svg, AUDIO_FILTER_ICON, VIDEO_FILTER_ICON, \
    SUBTITLE_FILTER_ICON, BACKUP_MANAGER_ICON, ADD_FILES_ICON, \
    ADD_DIRECTORY_ICON, REMOVE_ICON, REMOVE_ALL_ICON, KEEP_ALL_ICON, \
    KEEP_NONE_ICON, BATCH_ENCODING_OPTIONS_ICON, PROCESS_ICON, \
    BATCH_TITLE_TOOL_ICON
from gui.windows_taskbar_progress import WindowsTaskbarProgress
from track import Track, AttachmentTrack
from utils import pretty_duration, pretty_size, get_gpu_name, ETACalculator, \
    find_ffmpeg, find_ffprobe, pretty_date, suspend_os

if platform.system() == 'Windows':
    try:
        from PyQt5.QtWinExtras import QWinTaskbarButton
    except ImportError:
        # Chill on non-Windows platforms
        pass


logger = logging.getLogger(__name__)

TYPE_ALIASES = {
    VideoTrack: 'Video',
    AudioTrack: 'Audio',
    SubtitleTrack: 'Subtitle',
    AttachmentTrack: 'Attachment',
}


def file_track_summary(container: Container) -> str:
    d = {}
    for track in container.tracks:
        if not track.keep:
            continue

        t = type(track)
        d[t] = d.get(t, []) + [track.language]

    return ', '.join([f'{TYPE_ALIASES[k]}: [{", ".join(v)}]' for k, v in d.items()])

def container_pretty_info(container: Container) -> str:
    data = ''
    data += f'File: "{container.file}"\n'
    data += f'Duration: {pretty_duration(container.duration_seconds)} ({container.duration_frames} frames)\n'
    data += f'File size: {pretty_size(os.path.getsize(container.file))}\n'
    data += f'Container: {container.container}\n'
    data += f'Metadata: {container.metadata}\n'

    is_265 = any(track.is_h265 for track in container.tracks if track.keep and isinstance(track, VideoTrack))
    data += f'Video summary: is H.265: {"yes" if is_265 else "no"}, codec: "{container.codec.name}", preset: "{container.preset}", tune: "{container.tune}", profile: "{container.profile}"'

    return data

class CustomTableWidgetItem(QtWidgets.QTableWidgetItem):
    def __init__(self, text, custom_data):
        super().__init__(text)
        self.custom_data = custom_data

class MainWindow(QtWidgets.QMainWindow):
    def popup_error(self, message: str):
        QtWidgets.QMessageBox.critical(self, 'Error', message)

    def __init__(self, files: list[str]):
        super().__init__()
        self.init_ui()
        self.files: List[Container] = []

        self.processing_thread = QtCore.QThread()
        self.worker = None
        self.windows_taskbar_progress = None

        self.ffmpeg = find_ffmpeg()
        if self.ffmpeg.is_err():
            self.popup_error(f"Unable to find ffmpeg: {self.ffmpeg.err()}. Make sure it is installed and in PATH")
            raise SystemExit
        self.ffmpeg = self.ffmpeg.unwrap()

        self.ffprobe = find_ffprobe()
        if self.ffprobe.is_err():
            self.popup_error(f"Unable to find ffprobe: {self.ffprobe.err()}. Make sure it is installed and in PATH")
            raise SystemExit
        self.ffprobe = self.ffprobe.unwrap()

        self.gpu_name = get_gpu_name()
        if self.gpu_name.is_err():
            self.popup_error(f"Unable to get GPU name: {self.gpu_name.err()}")
            raise SystemExit
        self.gpu_name = self.gpu_name.unwrap()

        self.supported_codecs = get_supported_hevc_codecs(self.ffmpeg)
        if self.supported_codecs.is_err():
            self.popup_error(f"Unable to get supported codecss: {self.supported_codecs.err()}")
            raise SystemExit
        self.supported_codecs = self.supported_codecs.unwrap()

        self.preferred_codec = prefer_hevc_codec(self.supported_codecs, self.gpu_name)
        if self.preferred_codec.is_err():
            self.popup_error(f'No suitable HEVC codec found: {self.preferred_codec.err()}')
            raise SystemExit
        self.preferred_codec = self.preferred_codec.unwrap()

        logger.info('FFMpeg: %s', self.ffmpeg)
        logger.info('FFProbe: %s', self.ffprobe)
        logger.info('GPU: %s', self.gpu_name)
        logger.info('HEVC codecs: %s', self.supported_codecs)
        logger.info('Preferred codec: %s', self.preferred_codec)

        if len(files) != 0:
            self.open_files(files)

        self.files_count_changed()
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
        files = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        self.open_files(files)

    def open_file(self, file: str):
        for f in self.files:
            if f.file == file:
                logger.info('File %s already opened', file)
                return

        logger.info('Opening file: %s', file)
        container = Container(file, self.preferred_codec)
        try:
            if (res := container.parse(self.ffprobe)).is_err():
                self.popup_error(f'Failed to parse file {file}: {res.unwrap_err()}')
                return
        except Exception as e:
            self.popup_error(f'Error parsing file {file}: {e}')
            logger.exception('Error parsing file %s: %s', file, e)
            return

        self.files.append(container)
        self.files_count_changed()

    def update_files_table(self):
        self.files_table.blockSignals(True)
        self.files_table.setRowCount(len(self.files))
        for i, container in enumerate(self.files):
            self.files_table.setItem(i, 0, CustomTableWidgetItem(os.path.basename(container.file), container))
            self.files_table.item(i, 0).setFlags(self.files_table.item(i, 0).flags() & ~QtCore.Qt.ItemIsEditable)

            self.files_table.setItem(i, 1, CustomTableWidgetItem(container.title, container))
            self.files_table.item(i, 1).setFlags(self.files_table.item(i, 0).flags() | QtCore.Qt.ItemIsEditable)

            codec_select = QtWidgets.QComboBox()
            for codec in self.supported_codecs:
                codec_select.addItem(codec.name, codec)
            codec_select.setCurrentText(container.codec.name)
            self.files_table.setCellWidget(i, 2, codec_select)

            preset_select = QtWidgets.QComboBox()
            preset_select.addItems(container.codec.presets)
            preset_select.setCurrentText(container.preset)
            def update_preset(preset, f=container):
                f.preset = preset
                self.on_file_selected()
            preset_select.currentTextChanged.connect(update_preset)
            self.files_table.setCellWidget(i, 3, preset_select)

            tune_select = QtWidgets.QComboBox()
            tune_select.addItems(container.codec.tunes)
            tune_select.setCurrentText(container.tune)
            def update_tune(tune, f=container):
                f.tune = tune
                self.on_file_selected()
            tune_select.currentTextChanged.connect(update_tune)
            self.files_table.setCellWidget(i, 4, tune_select)

            profile_select = QtWidgets.QComboBox()
            profile_select.addItems(container.codec.profiles)
            profile_select.setCurrentText(container.profile)
            def update_profile(profile, f=container):
                f.profile = profile
                self.on_file_selected()
            profile_select.currentTextChanged.connect(update_profile)
            self.files_table.setCellWidget(i, 5, profile_select)

            container_select = QtWidgets.QComboBox()
            container_select.addItems([c.ext for c in SUPPORTED_CONTAINERS])
            container_select.setCurrentText(container.container.ext)
            def update_container(container, f=container):
                f.container = next((c for c in SUPPORTED_CONTAINERS if c.ext == container), None)
                self.on_file_selected()
            container_select.currentTextChanged.connect(update_container)
            self.files_table.setCellWidget(i, 6, container_select)

            def update_codec(codec_name, f=container, codec_select=codec_select, preset_select=preset_select, tune_select=tune_select, profile_select=profile_select):
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

            self.files_table.setItem(i, 7, QtWidgets.QTableWidgetItem(pretty_duration(container.duration_seconds)))
            self.files_table.item(i, 7).setFlags(self.files_table.item(i, 7).flags() ^ QtCore.Qt.ItemIsEditable)

            self.files_table.setItem(i, 8, QtWidgets.QTableWidgetItem(file_track_summary(container)))
            self.files_table.item(i, 8).setFlags(self.files_table.item(i, 8).flags() ^ QtCore.Qt.ItemIsEditable)
        self.files_table.blockSignals(False)

    def on_files_cell_changed(self, row, column):
        logger.info('Cell changed: %d, %d', row, column)
        item = self.files_table.item(row, column)
        if item is None:
            return  # Ignore empty cells

        index = self.files_table.currentRow()
        if index == -1:
            return

        logger.info('Index: %d', index)
        container = self.files[index]

        if column == 1:
            title = item.text()
            logger.info('Title: %s', title)
            container.title = title
            self.on_file_selected()

    def on_tracks_cell_changed(self, row, column):
        logger.info('Cell changed: %d, %d', row, column)
        item = self.file_tracks.item(row, column)
        if item is None:
            return # Ignore empty cells

        index = self.files_table.currentRow()
        if index == -1:
            return

        if column == 3:
            language = item.text()
            logger.info('Language: %s', language)
            self.files[index].tracks[row].language = language
            self.on_file_selected()
        elif column == 4:
            title = item.text()
            logger.info('Title: %s', title)
            self.files[index].tracks[row].title = title
            self.on_file_selected()

    def on_file_selected(self):
        index = self.files_table.currentRow()
        if index == -1:
            # Clear metadata and tracks
            self.file_metadata.clear()
            self.file_tracks.setRowCount(0)
            self.remove_selected_action.setEnabled(False)
            return

        self.remove_selected_action.setEnabled(True)

        container = self.files_table.item(index, 0).custom_data

        # Fill metadata
        self.file_metadata.clear()
        self.file_metadata.setText(container_pretty_info(container))

        language_colors = {}
        language_palette = Colors.get_language_colors()
        for i, track in enumerate(container.tracks):
            language = track.language
            if language not in language_colors:
                language_colors[language] = language_palette[len(language_colors) % len(language_palette)]

        # Don't trigger signals while updating table
        self.file_tracks.blockSignals(True)

        # Fill tracks
        self.file_tracks.setRowCount(len(container.tracks))
        for i, track in enumerate(container.tracks):
            keep_checkbox = QtWidgets.QCheckBox()
            keep_checkbox.setChecked(track.keep)
            def update(state, t=track):
                t.keep = state == QtCore.Qt.Checked
                self.update_files_table()

            keep_checkbox.stateChanged.connect(update)

            self.file_tracks.setCellWidget(i, 0, keep_checkbox)
            self.file_tracks.setItem(i, 1, QtWidgets.QTableWidgetItem(TYPE_ALIASES[type(track)]))
            self.file_tracks.item(i, 1).setBackground(QtGui.QColor(Colors.get_type_colors()[type(track)]))
            self.file_tracks.item(i, 1).setFlags(self.file_tracks.item(i, 1).flags() ^ QtCore.Qt.ItemIsEditable)

            self.file_tracks.setItem(i, 2, QtWidgets.QTableWidgetItem(track.codec))
            self.file_tracks.item(i, 2).setFlags(self.file_tracks.item(i, 2).flags() ^ QtCore.Qt.ItemIsEditable)

            self.file_tracks.setItem(i, 3, QtWidgets.QTableWidgetItem(track.language))
            self.file_tracks.item(i, 3).setBackground(QtGui.QColor(language_colors[track.language]))
            self.file_tracks.item(i, 3).setFlags(self.file_tracks.item(i, 3).flags() | QtCore.Qt.ItemIsEditable)

            self.file_tracks.setItem(i, 4, QtWidgets.QTableWidgetItem(track.title))
            self.file_tracks.item(i, 4).setFlags(self.file_tracks.item(i, 4).flags() | QtCore.Qt.ItemIsEditable)

            self.file_tracks.setItem(i, 5, QtWidgets.QTableWidgetItem(pretty_duration(track.duration)))
            self.file_tracks.item(i, 5).setFlags(self.file_tracks.item(i, 5).flags() ^ QtCore.Qt.ItemIsEditable)
            if isinstance(track, VideoTrack):
                self.file_tracks.setItem(i, 6, QtWidgets.QTableWidgetItem(f'{track.frame_rate:.2f} FPS'))
            elif isinstance(track, AudioTrack):
                self.file_tracks.setItem(i, 6, QtWidgets.QTableWidgetItem(f'{track.channels} channels'))
            else:
                self.file_tracks.setItem(i, 6, QtWidgets.QTableWidgetItem(''))
            self.file_tracks.item(i, 6).setFlags(self.file_tracks.item(i, 6).flags() ^ QtCore.Qt.ItemIsEditable)

        self.file_tracks.blockSignals(False)

    def backup_manager(self):
        logger.info('Backup manager')
        dialog = BackupManager()
        dialog.exec_()

    def open_files(self, list: list[str]):
        # Notify user that processing is going
        # I'm to lazy to implement proper progress bar
        self.windows_taskbar_progress.set_progress(0)
        self.windows_taskbar_progress.set_visible(True)

        for i, file in enumerate(list):
            self.windows_taskbar_progress.set_progress(i / len(list) * 100)
            self.open_file(file)

        self.windows_taskbar_progress.set_visible(False)
        self.update_files_table()

    def add_files(self):
        logger.info('Add files')
        dialog = QtWidgets.QFileDialog()
        dialog.setFileMode(QtWidgets.QFileDialog.ExistingFiles)

        filter = ''
        for extension, description in SUPPORTED_CONTAINERS:
            filter += f'{description} (*{extension});;'
        # Any video file
        filter += 'All video files (' + ' '.join([f'*{extension} ' for extension, _ in SUPPORTED_CONTAINERS]) + ')' + ';;'
        # Any file
        filter += 'All files (*)'

        dialog.setNameFilter(filter)
        if dialog.exec_():
            files = dialog.selectedFiles()
            self.open_files(files)

    def collect_files(self, dir: str, recursive: bool) -> List[str]:
        logger.debug('Open directory: %s, recursive: %s', dir, recursive)
        files = []
        # Don't use os.walk since its freezes on Windows Network paths
        for token in os.listdir(dir):
            path = os.path.join(dir, token)
            if os.path.isdir(path):
                if recursive:
                    files += self.collect_files(path, True)
            elif any(token.endswith(container.ext) for container in SUPPORTED_CONTAINERS):
                files.append(path)

        return files

    def add_directory(self):
        logger.info('Add directory')
        dialog = QtWidgets.QFileDialog()
        dialog.setFileMode(QtWidgets.QFileDialog.Directory)
        if dialog.exec_():
            directories = dialog.selectedFiles()
            for directory in directories:
                self.open_files(self.collect_files(directory, False))

    def add_directory_recursive(self):
        logger.info('Add directory recursive')
        dialog = QtWidgets.QFileDialog()
        dialog.setFileMode(QtWidgets.QFileDialog.Directory)
        if dialog.exec_():
            directories = dialog.selectedFiles()
            for directory in directories:
                self.open_files(self.collect_files(directory, True))

    def files_count_changed(self):
        any_file = len(self.files) != 0
        self.remove_all_action.setEnabled(any_file)
        self.audio_filter_action.setEnabled(any_file)
        self.video_filter_action.setEnabled(any_file)
        self.subtitle_filter_action.setEnabled(any_file)
        self.keep_all_action.setEnabled(any_file)
        self.keep_none_action.setEnabled(any_file)
        self.batch_encoding_options_action.setEnabled(any_file)
        self.batch_title_tool_action.setEnabled(any_file)
        self.process_action.setEnabled(any_file)

    def batch_title_tool(self):
        logger.info('Batch title tool')
        dialog = BatchTitleToolDialog()
        if dialog.exec_():
            for index, container in enumerate(self.files):
                container.title = dialog.selector(container.title, container.file, index)
            self.update_files_table()
            self.on_file_selected()

    def remove_selected(self):
        logger.info('Remove selected')
        self.files.remove(self.files_table.item(self.files_table.currentRow(), 0).custom_data)
        self.files_table.removeRow(self.files_table.currentRow())
        self.files_count_changed()

    def remove_all(self):
        logger.info('Remove all')
        self.files = []
        self.files_table.setRowCount(0)
        self.files_count_changed()

    def filter(self, filters: list[str], t: Track):
        logger.info('Filters: %s', filters)
        for container in self.files:
            for track in container.tracks:
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
        filter = FilterDialog(render_svg(AUDIO_FILTER_ICON, 32, Colors.get_icon_color()), 'Audio filter')
        if filter.exec_():
            self.filter(filter.filters, AudioTrack)

    def video_filter(self):
        logger.info('Video filter')
        filter = FilterDialog(render_svg(VIDEO_FILTER_ICON, 32, Colors.get_icon_color()), 'Video filter')
        if filter.exec_():
            self.filter(filter.filters, VideoTrack)

    def subtitle_filter(self):
        logger.info('Subtitle filter')
        filter = FilterDialog(render_svg(SUBTITLE_FILTER_ICON, 32, Colors.get_icon_color()), 'Audio filter')
        if filter.exec_():
            self.filter(filter.filters, SubtitleTrack)

    def keep_all(self):
        logger.info('Keep all')
        for container in self.files:
            for track in container.tracks:
                track.keep = True
        self.update_files_table()
        self.on_file_selected()

    def keep_none(self):
        logger.info('Keep none')
        for container in self.files:
            for track in container.tracks:
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

        containers = list(set([file.container for file in self.files]))
        if len(containers) != 1:
            container = self.files[0].container
        else:
            container = PREFERRED_CONTAINER

        dialog = BatchEncodingOptionsDialog(self.supported_codecs, codec, SUPPORTED_CONTAINERS, container)
        if dialog.exec_():
            def update_all(updater, value):
                for container in self.files:
                    updater(value, container)
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
            elif dialog.result_type == "container":
                update_all(lambda container, f: setattr(f, 'container', container), next((c for c in SUPPORTED_CONTAINERS if c.ext == dialog.result), None))
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

            def __init__(self, files: list[Container], ffmpeg: str):
                super().__init__()
                self.files = files
                self.ffmpeg = ffmpeg

            def run(self):
                logger.info('Processing %d files', len(self.files))

                for i, container in enumerate(self.files):
                    def on_progress(frame: int, fps: float, index=i):
                        self.ffmpeg_process.emit(index, frame, fps)

                    self.file_update.emit(i, 'working')
                    if (res := container.remux(self.ffmpeg, on_progress)).is_err():
                        self.file_update.emit(i, 'error')
                        self.error_message.emit(f'Failed to process file {container.file}: {res.unwrap_err()}')
                    else:
                        self.file_update.emit(i, 'done')

                logger.info('All files processed')
                self.finished.emit()

        class FileStatus:
            def __init__(self, file: Container):
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
                self.completed_percent = frame / self.total_frames * 100
                self.eta.feed(self.completed_percent)
                self.update_time = time.time()

        file_statuses = [
            FileStatus(container) for container in self.files
        ]

        self.overall_progress_label.setText('')
        self.overall_progress.setValue(0)
        self.current_progress_label.setText('')
        self.current_progress.setValue(0)
        self.windows_taskbar_progress.set_progress(0)
        self.windows_taskbar_progress.set_visible(True)

        start_time = time.time()
        overall_eta = ETACalculator(start_time, 0)

        # Forbid changing window size to the contents
        # allowing only manual chanes, to prevent visual glitches
        if platform.system() == 'Darwin':
            self.setFixedSize(self.size())

        def update_overall_progress():
            total_percent = sum(status.completed_percent for status in file_statuses) / len(file_statuses)
            overall_eta.feed(total_percent)
            self.overall_progress.setValue(int(total_percent))
            self.overall_progress_simple_label.setText(
                f'{total_percent:.2f}%'
            )
            self.overall_progress_label.setText(
                f'Time elapsed: {pretty_duration(time.time() - start_time)}. '
                f'ETA: {pretty_duration(overall_eta.get())}'
            )

            self.windows_taskbar_progress.set_progress(int(total_percent))

        def update_file_status_with_gui(index, status):
            file_statuses[index].set_status(status)
            self.process_table.setItem(index, 1, QtWidgets.QTableWidgetItem(status))
            self.process_table.item(index, 1).setBackground(QtGui.QColor(Colors.get_status_colors()[status]))
            self.process_table.setItem(index, 2, QtWidgets.QTableWidgetItem(pretty_date(time.time())))
            update_overall_progress()

        def on_progress(index, frame: int, fps: float):
            logger.debug('Progress: %d frames, %f FPS', frame, fps)

            status = file_statuses[index]
            status.update_progress(frame)

            self.current_progress.setValue(int(status.completed_percent))
            self.current_progress_simple_label.setText(
                f'{os.path.basename(status.file.file)} - {status.completed_percent:.2f}%'
            )
            self.current_progress_label.setText(
                f'FPS: {fps:.2f} ({fps / status.file.fps:.2f}x of realtime). ' 
                f'{frame}/{status.total_frames} frames processed. '
                f'Time elapsed: {pretty_duration(time.time() - status.start_time)}. '
                f'ETA: {pretty_duration(status.eta.get())}'
            )

            update_overall_progress()

        def finished():
            logger.info('All files processed')
            self.current_progress.setValue(100)
            self.current_progress.setFormat('Done')
            self.current_progress_label.setText('')
            self.overall_progress.setValue(100)
            self.overall_progress.setFormat('Done')
            self.overall_progress_label.setText('Time elapsed: ' + pretty_duration(time.time() - start_time))

            self.windows_taskbar_progress.set_visible(False)
            if self.suspend_os_on_finish_checkbox.isChecked():
                suspend_os()

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
        self.processing_thread.finished.connect(finished)
        self.worker.finished.connect(self.processing_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)

        self.processing_thread.start()

    def init_ui(self):
        self.setWindowTitle(f'Trimmer v{__version__}')
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
            toolbar.addAction(render_svg(ADD_FILES_ICON, 32, Colors.get_icon_color()), 'Add files', lambda: self.add_files())
            toolbar.addAction(render_svg(ADD_DIRECTORY_ICON, 32, Colors.get_icon_color()), 'Add directory', lambda: self.add_directory())
            toolbar.addAction(render_svg(ADD_DIRECTORY_ICON, 32, Colors.get_icon_color()), 'Add directory\nrecursively', lambda: self.add_directory_recursive())

            self.remove_selected_action = QAction(render_svg(REMOVE_ICON, 32, Colors.get_icon_color()), 'Remove\nselected', toolbar)
            self.remove_selected_action.triggered.connect(lambda: self.remove_selected())
            self.remove_selected_action.setEnabled(False)
            toolbar.addAction(self.remove_selected_action)

            self.remove_all_action = QAction(render_svg(REMOVE_ALL_ICON, 32, Colors.get_icon_color()), 'Remove all', toolbar)
            self.remove_all_action.triggered.connect(lambda: self.remove_all())
            self.remove_selected_action.setEnabled(False)
            toolbar.addAction(self.remove_all_action)

            toolbar.addSeparator()

            self.audio_filter_action = QAction(render_svg(AUDIO_FILTER_ICON, 32, Colors.get_icon_color()), 'Audio tacks\nfilter', toolbar)
            self.audio_filter_action.triggered.connect(lambda: self.audio_filter())
            self.audio_filter_action.setEnabled(False)
            toolbar.addAction(self.audio_filter_action)

            self.video_filter_action = QAction(render_svg(VIDEO_FILTER_ICON, 32, Colors.get_icon_color()), 'Video tracks\nfilter', toolbar)
            self.video_filter_action.triggered.connect(lambda: self.video_filter())
            self.video_filter_action.setEnabled(False)
            toolbar.addAction(self.video_filter_action)

            self.subtitle_filter_action = QAction(render_svg(SUBTITLE_FILTER_ICON, 32, Colors.get_icon_color()), 'Subtitle tracks\nfilter', toolbar)
            self.subtitle_filter_action.triggered.connect(lambda: self.subtitle_filter())
            self.subtitle_filter_action.setEnabled(False)
            toolbar.addAction(self.subtitle_filter_action)

            self.keep_all_action = QAction(render_svg(KEEP_ALL_ICON, 32, Colors.get_icon_color()), 'Keep all\ntracks', toolbar)
            self.keep_all_action.triggered.connect(lambda: self.keep_all())
            self.keep_all_action.setEnabled(False)
            toolbar.addAction(self.keep_all_action)

            self.keep_none_action = QAction(render_svg(KEEP_NONE_ICON, 32, Colors.get_icon_color()), 'Keep none\ntracks', toolbar)
            self.keep_none_action.triggered.connect(lambda: self.keep_none())
            self.keep_none_action.setEnabled(False)
            toolbar.addAction(self.keep_none_action)

            toolbar.addSeparator()

            self.batch_encoding_options_action = QAction(render_svg(BATCH_ENCODING_OPTIONS_ICON, 32, Colors.get_icon_color()), 'Batch codec\ntool', toolbar)
            self.batch_encoding_options_action.triggered.connect(lambda: self.batch_encoding_options())
            self.batch_encoding_options_action.setEnabled(False)
            toolbar.addAction(self.batch_encoding_options_action)

            self.batch_title_tool_action = QAction(render_svg(BATCH_TITLE_TOOL_ICON, 32, Colors.get_icon_color()), 'Batch title\ntool', toolbar)
            self.batch_title_tool_action.triggered.connect(lambda: self.batch_title_tool())
            self.batch_title_tool_action.setEnabled(False)
            toolbar.addAction(self.batch_title_tool_action)

            toolbar.addSeparator()

            self.process_action = QAction(render_svg(PROCESS_ICON, 32, Colors.get_icon_color()), 'Process', toolbar)
            self.process_action.triggered.connect(lambda: self.process())
            self.process_action.setEnabled(False)
            toolbar.addAction(self.process_action)

            toolbar.addAction(render_svg(BACKUP_MANAGER_ICON, 32, Colors.get_icon_color()), 'Backup\nmanager', lambda: self.backup_manager())

            files_tab_layout.addWidget(toolbar)

            # Make horizontal splitter. Top - table, bottom - details
            splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)

            self.files_table = QtWidgets.QTableWidget()
            self.files_table.setColumnCount(9)
            self.files_table.setHorizontalHeaderLabels(['File',
                                                        'Title*',
                                                        'Codec', 'Preset', 'Tune', 'Profile',
                                                        'Container',
                                                        'Duration', 'Tracks summary'])
            # Make duration to take as little space as possible
            self.files_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
            self.files_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
            self.files_table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
            self.files_table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
            self.files_table.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)
            self.files_table.horizontalHeader().setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeToContents)
            self.files_table.horizontalHeader().setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeToContents)
            self.files_table.horizontalHeader().setSectionResizeMode(7, QtWidgets.QHeaderView.ResizeToContents)
            self.files_table.horizontalHeader().setSectionResizeMode(8, QtWidgets.QHeaderView.Stretch)
            self.files_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            self.files_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            self.files_table.itemSelectionChanged.connect(self.on_file_selected)
            self.files_table.cellChanged.connect(self.on_files_cell_changed)
            splitter.addWidget(self.files_table)

            self.file_tracks = QtWidgets.QTableWidget()
            self.file_tracks.setColumnCount(7)
            self.file_tracks.setHorizontalHeaderLabels(['Keep', 'Type', 'Codec', 'Language*', 'Title*', 'Duration', 'FPS/Channels'])
            self.file_tracks.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
            self.file_tracks.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
            self.file_tracks.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
            self.file_tracks.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
            self.file_tracks.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.Stretch)
            self.file_tracks.horizontalHeader().setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeToContents)
            self.file_tracks.horizontalHeader().setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeToContents)
            self.file_tracks.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            self.file_tracks.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            self.file_tracks.cellChanged.connect(self.on_tracks_cell_changed)
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
            self.current_progress.setTextVisible(False)
            process_tab_layout.addWidget(self.current_progress)

            # On windows, ProgressBar text looks terrible, so we will use label instead
            # One on the left side with some advanced info, one on the right side with simple info
            widget = QtWidgets.QWidget()
            layout = QtWidgets.QHBoxLayout()
            widget.setLayout(layout)
            layout.setContentsMargins(0, 0, 0, 0)
            self.current_progress_label = QtWidgets.QLabel('')
            layout.addWidget(self.current_progress_label, alignment=QtCore.Qt.AlignLeft)
            layout.addStretch()
            self.current_progress_simple_label = QtWidgets.QLabel('')
            layout.addWidget(self.current_progress_simple_label, alignment=QtCore.Qt.AlignRight)
            process_tab_layout.addWidget(widget)

            self.overall_progress = QtWidgets.QProgressBar()
            self.overall_progress.setRange(0, 100)
            self.overall_progress.setTextVisible(False)
            process_tab_layout.addWidget(self.overall_progress)

            widget = QtWidgets.QWidget()
            layout = QtWidgets.QHBoxLayout()
            widget.setLayout(layout)
            layout.setContentsMargins(0, 0, 0, 0)
            self.overall_progress_label = QtWidgets.QLabel('')
            layout.addWidget(self.overall_progress_label, alignment=QtCore.Qt.AlignLeft)
            layout.addStretch()
            self.overall_progress_simple_label = QtWidgets.QLabel('')
            layout.addWidget(self.overall_progress_simple_label, alignment=QtCore.Qt.AlignRight)
            process_tab_layout.addWidget(widget)

            self.suspend_os_on_finish_checkbox = QtWidgets.QCheckBox('Suspend OS on finish')
            process_tab_layout.addWidget(self.suspend_os_on_finish_checkbox)

            process_tab.setLayout(process_tab_layout)
            return process_tab

        self.files_tab = files_tab()
        self.main_tabwidget.addTab(self.files_tab, 'Files')

        self.process_tab = process_tab()
        self.main_tabwidget.addTab(self.process_tab, 'Process')

        self.setCentralWidget(self.main_tabwidget)

    def showEvent(self, a0):
        # In constructor, window handle seems to be not yet created
        if self.windows_taskbar_progress is None:
            self.windows_taskbar_progress = WindowsTaskbarProgress(self)