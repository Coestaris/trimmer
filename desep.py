#!/usr/bin/env python3
#
# @file desep.py
# @date 17-07-2025
# @author Maxim Kurylko <vk_vm@ukr.net>
#
# Additional script for de-separating MKV containers
# Use case:
# You have 3 folders:
#    - A folder with MKV files (e.g., "videos") with names like "video1.mkv", "video2.mkv", etc.
#    - A folder with separate audio files (e.g., "audio") with names like "video1.mp3", "video2.mp3", etc.
#    - A folder with separate subtitle files (e.g., "subtitles") with names like "video1.srt", "video2.srt", etc.
# Note that the names of the audio and subtitle files must match the names
# of the video files, except for the extensions.
#
# The script will create a new folder (e.g., "output") and remux each video file
# with the corresponding audio and subtitle files into a new MKV file.
#
# Call the script with the following command:
# python desep.py --no-gui --videos videos --audio audio --subtitles subtitles --output output
# or
# python desep.py
# and it will prompt you for the folders.
#
import logging
import os
import re
from typing import Optional, Callable, List

from PyQt5 import QtWidgets
from alive_progress import alive_bar

import argparse


class Track:
    def __init__(self, path: str, group_name: str, name: Optional[str] = None,
                 language: Optional[str] = None):
        self.path = path
        self.group_name = group_name
        self.name = name or "default"
        self.language = language or "und"

    @staticmethod
    def track_factory(path: str,
                      name_extractor: Optional[Callable[[str], Optional[str]]] = None,
                      lang_extractor: Optional[Callable[[str], Optional[str]]] = None) \
            -> Optional["Track"]:
        extension = os.path.splitext(path)[1][1:].lower().strip()
        # Name before all the dots
        group_name = os.path.splitext(os.path.basename(path))[0].split('.')[0].strip()
        if name_extractor is not None:
            name = name_extractor(os.path.basename(path))
        else:
            name = None

        if lang_extractor is not None:
            language = lang_extractor(os.path.basename(path))
        else:
            language = None

        logging.debug("Creating track from path: %s, name: %s, language: %s",
                      path, name, language)

        if extension in VideoTrack.EXTENSIONS:
            return VideoTrack(path, group_name, name, language)
        elif extension in SubtitleTrack.EXTENSIONS:
            return SubtitleTrack(path, group_name, name, language)
        elif extension in AudioTrack.EXTENSIONS:
            return AudioTrack(path, group_name, name, language)
        else:
            logging.error("Unsupported file type: %s", path)
        return None


class VideoTrack(Track):
    EXTENSIONS = ['mkv', 'mp4', 'webm', 'avi', 'mov']

    def __init__(self, path: str, group_name: str, name: Optional[str] = None,
                 language: Optional[str] = None):
        super().__init__(path, group_name, name, language)

    def __str__(self):
        return f"VideoTrack(gn={self.group_name}, lang={self.language}, name={self.name})"

    def __repr__(self):
        return self.__str__()


class SubtitleTrack(Track):
    EXTENSIONS = ['mks', 'srt', 'ass', 'vtt', 'scc', 'sub']

    def __init__(self, path: str, group_name: str, name: Optional[str] = None,
                 language: Optional[str] = None):
        super().__init__(path, group_name, name, language)

    def __str__(self):
        return f"SubtitleTrack(gn={self.group_name}, lang={self.language}, name={self.name})"

    def __repr__(self):
        return self.__str__()


class AudioTrack(Track):
    EXTENSIONS = ['mka']

    def __init__(self, path: str, group_name: str, name: Optional[str] = None,
                 language: Optional[str] = None):
        super().__init__(path, group_name, name, language)

    def __str__(self):
        return f"AudioTrack(gn={self.group_name}, lang={self.language}, name={self.name})"

    def __repr__(self):
        return self.__str__()


class DeSep:
    def __init__(self, folders: List[str], output_dir: Optional[str] = None):
        self.folders = folders
        self.output_folder = output_dir or "."

    @staticmethod
    def list_files(folder: str) -> list:
        """List of absolute paths of files in the folder."""
        if not os.path.exists(folder):
            raise ValueError(f"Folder {folder} does not exist.")
        if not os.path.isdir(folder):
            raise ValueError(f"{folder} exists but is not a directory.")

        files = [os.path.join(folder, f) for f in os.listdir(folder)
                 if os.path.isfile(os.path.join(folder, f))]
        logging.debug("Files in folder '%s': %s", folder, files)
        return files

    @staticmethod
    def ensure_folder(folder: str) -> None:
        """Ensure that the folder exists, create it if it does not."""
        if not os.path.exists(folder):
            os.makedirs(folder)
            logging.info("Created folder: %s", folder)
        elif not os.path.isdir(folder):
            raise ValueError(f"{folder} exists but is not a directory.")
        else:
            logging.info("Using existing folder: %s", folder)

    @staticmethod
    def build_ffmpeg_cmd(group_name, tracks, output_folder):
        cmd = ["ffmpeg", "-y"]
        input_idxs = []
        main_video_idx = None

        # Находим VideoTrack, это "главный" файл
        for i, track in enumerate(tracks):
            if isinstance(track, VideoTrack):
                main_video_idx = i
                break
        if main_video_idx is None:
            raise ValueError("No VideoTrack in group!")

        # Первый вход — главный видеофайл
        cmd += ["-i", tracks[main_video_idx].path]
        input_idxs.append(main_video_idx)

        # Остальные — по порядку, кроме главного
        for i, track in enumerate(tracks):
            if i != main_video_idx:
                cmd += ["-i", track.path]
                input_idxs.append(i)

        # Считаем сколько в главном mkv уже есть дорожек каждого типа
        # (Можно узнать через ffprobe, но если не критично — можно не задавать метаданные старым дорожкам вовсе)
        # Но если вдруг хочется узнать, пример:
        # ffprobe -show_streams -select_streams a "mainfile.mkv" | grep index
        # Для простоты: пусть мы не меняем старые дорожки!

        cmd += ["-map", "0", "-c", "copy"]  # Всё из главного файла

        # Счётчики для новых дорожек
        # (надо знать сколько уже было дорожек типа — тогда можем корректно поставить индекс)
        audio_offset = 0
        subs_offset = 0

        # Если хочется по-настоящему корректно: тут надо прогнать ffprobe по главному файлу!
        # Ниже пример с ffprobe (быстро):

        import subprocess
        import json

        def count_streams(mkv_path, stream_type):
            # stream_type: 'a' (audio), 's' (subs)
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries",
                 "stream=index,codec_type", "-of", "json", mkv_path],
                stdout=subprocess.PIPE, text=True)
            info = json.loads(result.stdout)
            return sum(1 for s in info["streams"] if s.get("codec_type") == {
                "a": "audio", "s": "subtitle", "v": "video"
            }[stream_type])

        audio_offset = count_streams(tracks[main_video_idx].path, "a")
        subs_offset = count_streams(tracks[main_video_idx].path, "s")

        # Теперь добавляем новые треки
        audio_idx = audio_offset
        subs_idx = subs_offset
        rel_input_idx = 1  # первый дополнительный файл (0 — это оригинал)
        for i, track in enumerate(tracks):
            if i == main_video_idx:
                continue
            if isinstance(track, AudioTrack):
                cmd += [
                    "-map", f"{rel_input_idx}:a",
                    f"-metadata:s:a:{audio_idx}", f"language={track.language}",
                    f"-metadata:s:a:{audio_idx}", f"title={track.name}",
                ]
                audio_idx += 1
            elif isinstance(track, SubtitleTrack):
                cmd += [
                    "-map", f"{rel_input_idx}:s",
                    f"-metadata:s:s:{subs_idx}", f"language={track.language}",
                    f"-metadata:s:s:{subs_idx}", f"title={track.name}",
                ]
                subs_idx += 1
            rel_input_idx += 1

        # Выходной файл
        output_path = os.path.join(output_folder, f"{group_name}.mkv")
        cmd.append(output_path)
        return cmd

    def run(self,
            callback: Optional[Callable[[str, float], None]] = None) -> None:

        files = []
        for folder in self.folders:
            if not os.path.exists(folder):
                raise ValueError(f"Folder {folder} does not exist.")
            if not os.path.isdir(folder):
                raise ValueError(f"{folder} exists but is not a directory.")
            files.extend(self.list_files(folder))

        logging.debug("Found %d files in folders: %s", len(files), self.folders)

        logging.debug("Ensuring output folder exists")
        self.ensure_folder(self.output_folder)

        name_re = re.compile(r'\.\[([^.]*?)]\.')
        def name_extractor(name: str) -> Optional[str]:
            match = name_re.search(name)
            if match:
                return match.group(1).strip()
            return None

        lang_re = re.compile(r'\.(\w{3})\.')
        def lang_extractor(name: str) -> Optional[str]:
            match = lang_re.search(name)
            if match:
                return match.group(1).strip()
            return None

        tracks = [Track.track_factory(t, name_extractor, lang_extractor) for t in files if t is not None]
        # Drop nones
        tracks = [t for t in tracks if t is not None]

        # Group tracks by their group name
        groups = {}
        for track in tracks:
            if track.group_name not in groups:
                groups[track.group_name] = []
            groups[track.group_name].append(track)

        topology = None
        for gn, group_tracks in groups.items():
            logging.debug("Group '%s'", gn)
            for track in group_tracks:
                logging.debug("  > %s", track)

            if topology is None:
                topology = [track.__class__.__name__ for track in group_tracks]
            else:
                current_topology = [track.__class__.__name__ for track in group_tracks]
                if current_topology != topology:
                    raise ValueError(
                        "Inconsistent track topology at group '%s' detected. Expected: %s, got: %s" %
                        (gn, topology, current_topology))


        for i, (gn, group_tracks) in enumerate(groups.items()):
            args = self.build_ffmpeg_cmd(gn, group_tracks, self.output_folder)
            logging.debug("Processing group '%s' (%d/%d)", gn, i + 1, len(groups))
            if callback:
                callback(gn, i / len(groups))

            logging.debug("Running command: %s", " ".join(args))
            import subprocess
            process = subprocess.run(args, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True)
            if process.returncode != 0:
                logging.error("FFmpeg command failed for group '%s': %s",
                              gn, process.stderr.strip())
                raise RuntimeError(
                    f"FFmpeg command failed for group '{gn}': {process.stderr.strip()}")



def setup_logging(args):
    class Fore:
        GREEN = "\x1b[32m"
        CYAN = "\x1b[36m"
        RED = "\x1b[31m"
        YELLOW = "\x1b[33m"
        RESET = "\x1b[39m"

    def get_format_string(colored: bool, details: bool) -> str:
        green = Fore.GREEN if colored else ""
        cyan = Fore.CYAN if colored else ""
        reset = Fore.RESET if colored else ""
        yellow = Fore.YELLOW if colored else ""

        if details:
            return f"{green}%(asctime)s{reset} - {cyan}%(name)s:%(funcName)s:%(lineno)d{reset} - %(levelname)s - %(message)s"
        else:
            return f"{green}%(asctime)s{reset} - {cyan}%(name)s{reset} - %(levelname)s - %(message)s"

    # Set up logging
    if not args.colorless:
        logging.addLevelName(logging.CRITICAL,
                             f"{Fore.RED}{logging.getLevelName(logging.CRITICAL)}{Fore.RESET}")
        logging.addLevelName(logging.ERROR,
                             f"{Fore.RED}{logging.getLevelName(logging.ERROR)}{Fore.RESET}")
        logging.addLevelName(logging.WARNING,
                             f"{Fore.YELLOW}{logging.getLevelName(logging.WARNING)}{Fore.RESET}")
        logging.addLevelName(logging.INFO,
                             f"{Fore.GREEN}{logging.getLevelName(logging.INFO)}{Fore.RESET}")
        logging.addLevelName(logging.DEBUG,
                             f"{Fore.CYAN}{logging.getLevelName(logging.DEBUG)}{Fore.RESET}")

    logging.getLogger().setLevel(logging.getLevelName(args.log.upper()))
    # Output to file
    if args.log_file is not None:
        handler = logging.FileHandler(args.log_file)
    else:
        handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        get_format_string(not args.colorless, args.log == "debug")))
    logging.getLogger().addHandler(handler)


def run_gui() -> int:
    class MainWindow(QtWidgets.QMainWindow):
        def select_folder(self, title: str, multiple: bool) -> List[str]:
            if hasattr(self, 'prev_directory'):
                prev_dir = self.prev_directory
            else:
                prev_dir = os.path.expanduser("~")

            folder = QtWidgets.QFileDialog.getExistingDirectory(
                self, title, prev_dir, QtWidgets.QFileDialog.ShowDirsOnly)

            if not folder:
                logging.error("No folder selected for %s", title)
                return []

            self.prev_directory = folder

            logging.info("Selected folder for %s: %s", title, folder)
            return [folder]

        def start_de_separation(self):
            logging.info("Starting de-separation process")
            logging.info(
                "Use this line to run the script in command line mode: ")

            def shell_escape(s: str) -> str:
                if not s:
                    return "\"\""
                return "\"" + s.replace("'", "'\\''") + "\""

            args = [
                "python", shell_escape(os.path.basename(__file__)),
                "--output", shell_escape(self.desep.output_folder),
                "--no-gui"
            ]
            for folder in self.desep.folders:
                args.append("--folders")
                args.append(shell_escape(folder))

            logging.info(" ".join(args))
            self.progress_bar.setValue(0)

            def update_progress(file: str, progress: float):
                self.progress_bar.setValue(int(progress * 100))
                self.progress_bar.setFormat(
                    f"Processing {file}... {int(progress * 100)}%")

            def run():
                self.desep.run(callback=update_progress)

            # Run the de-separation process in a separate thread
            from threading import Thread
            thread = Thread(target=run)
            thread.start()

        def __init__(self):
            super().__init__()
            self.desep = DeSep([], "output")
            self.setWindowTitle("DeSep MKV De-separator")
            self.setGeometry(0, 0, 400, 300)
            main_widget = QtWidgets.QWidget()
            main_layout = QtWidgets.QVBoxLayout(main_widget)
            self.setCentralWidget(main_widget)

            output_folder_widget = QtWidgets.QWidget()
            output_layout = QtWidgets.QHBoxLayout(output_folder_widget)
            output_layout.setContentsMargins(0, 0, 0, 0)
            output_label = QtWidgets.QLabel("Output Folder:")
            output_edit = QtWidgets.QLineEdit(self.desep.output_folder)
            output_edit.setReadOnly(True)
            output_edit.textEdited.connect(lambda text: setattr(self.desep, 'output_folder', text))
            output_button = QtWidgets.QPushButton("...")
            output_button.setFixedWidth(30)
            def select_output_folder():
                folder = self.select_folder("Select Output Folder", False)
                if folder:
                    output_edit.setText(folder[0])
                    self.desep.output_folder = folder[0]
            output_button.clicked.connect(select_output_folder)
            output_layout.addWidget(output_label)
            output_layout.addWidget(output_edit)
            output_layout.addWidget(output_button)
            main_layout.addWidget(output_folder_widget)

            list_widget = QtWidgets.QListWidget()
            main_layout.addWidget(list_widget)
            add_button = QtWidgets.QPushButton("Add")
            def add_folders():
                folders = self.select_folder("Select Folders", True)
                if folders:
                    for folder in folders:
                        list_widget.addItem(folder)
                        self.desep.folders.append(folder)
            add_button.clicked.connect(add_folders)
            main_layout.addWidget(add_button)

            button = QtWidgets.QPushButton("Start De-separation")
            button.clicked.connect(self.start_de_separation)
            main_layout.addWidget(button)

            self.progress_bar = QtWidgets.QProgressBar()
            self.progress_bar.setRange(0, 100)
            main_layout.addWidget(self.progress_bar)

    app = QtWidgets.QApplication([])
    main_window = MainWindow()
    main_window.show()
    return app.exec_()


def main() -> int:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        prog=os.path.basename(__file__))
    parser.description = "De-separating MKV containers"
    parser.add_argument("--log-file", type=str, help="Log file")
    parser.add_argument("-l", "--log", type=str, default="info",
                        choices=["debug", "info", "warning", "error",
                                 "critical"],
                        help="Log level. Note: 'debug' log level may print sensitive information,\n"
                             "produce a lot of output and program may run slower/incorectly")
    parser.add_argument("--colorless", action="store_true",
                        help="Disable colored output")
    parser.add_argument("--no-gui", action="store_true",
                        help="Run in command line mode without GUI")
    parser.add_argument("-f", "--folders", default=[], nargs='*', action="append",
                        help="Folders to process. If not specified, will prompt for folders.")
    parser.add_argument("-o", "--output", type=str, default="output",
                        help="Output folder for processed files")

    args = parser.parse_args()
    setup_logging(args)

    print(args)

    logging.info("Running DeSep script")

    if args.no_gui:
        logging.info("Running in command line mode")
        if not args.folders or not args.folders[0]:
            logging.error("No folders specified. Use --folders to specify folders or run without --no-gui to use GUI.")
            return 1

        folders = [f for sublist in args.folders for f in sublist]
        desep = DeSep(folders, args.output)

        bar = None
        def update_progress(file: str, progress: float):
            nonlocal bar
            if bar is None:
                bar = alive_bar(1, title="Processing files", manual=True)
            bar(progress)
            if progress >= 1.0:
                bar.stop()
                bar = None
        desep.run(callback=update_progress)

    else:
        logging.info("Running GUI mode")
        return run_gui()

    return 0


if __name__ == '__main__':
    exit(main())
