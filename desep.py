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
from typing import Optional, Callable

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
    EXTENSIONS = ['srt', 'ass', 'vtt', 'scc', 'sub']

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
    def __init__(self, videos_folder: Optional[str] = None,
                 audio_folder: Optional[str] = None,
                 subtitles_folder: Optional[str] = None,
                 output_folder: Optional[str] = None):
        self.videos_folder = videos_folder
        self.audio_folder = audio_folder
        self.subtitles_folder = subtitles_folder
        self.output_folder = output_folder

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
        if not self.videos_folder or not self.audio_folder or not self.subtitles_folder or not self.output_folder:
            raise ValueError(
                "Videos, audio, and subtitles folders must be specified.")

        logging.info("Videos folder: %s", self.videos_folder)
        logging.info("Audio folder: %s", self.audio_folder)
        logging.info("Subtitles folder: %s", self.subtitles_folder)
        logging.info("Output folder: %s", self.output_folder)

        videos = self.list_files(self.videos_folder)
        audios = self.list_files(self.audio_folder)
        subtitles = self.list_files(self.subtitles_folder)

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

        tracks  = [Track.track_factory(t, name_extractor, lang_extractor) for t in (videos + audios + subtitles) if t is not None]

        # Group tracks by their group name
        groups = {}
        for track in tracks:
            if track.group_name not in groups:
                groups[track.group_name] = []
            groups[track.group_name].append(track)

        topology = None
        for gn, group_tracks in groups.items():
            if topology is None:
                topology = [track.__class__.__name__ for track in group_tracks]
            else:
                current_topology = [track.__class__.__name__ for track in group_tracks]
                if current_topology != topology:
                    raise ValueError(
                        "Inconsistent track topology at group '%s' detected. Expected: %s, got: %s" %
                        (gn, topology, current_topology))

            logging.debug("Group '%s'", gn)
            for track in group_tracks:
                logging.debug("  > %s", track)

        for i, (gn, group_tracks) in enumerate(groups.items()):
            args = self.build_ffmpeg_cmd(gn, group_tracks, self.output_folder)
            logging.info("Processing group '%s' (%d/%d)", gn, i + 1, len(groups))
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
        def select_folder(self, title: str) -> Optional[str]:
            if hasattr(self, 'prev_directory'):
                prev_dir = self.prev_directory
            else:
                prev_dir = os.path.expanduser("~")

            folder = QtWidgets.QFileDialog.getExistingDirectory(self, title,
                                                                prev_dir)
            if not folder:
                logging.error("No folder selected for %s", title)
                return None

            self.prev_directory = folder  # Save the selected folder for next time
            return folder

        def spawn_folder_enter(self, title: str) -> QtWidgets.QWidget:
            widget = QtWidgets.QWidget()
            layout = QtWidgets.QHBoxLayout(widget)

            layout.addWidget(QtWidgets.QLabel(f"{title} folder:"))
            line_edit = QtWidgets.QLineEdit()
            line_edit.textChanged.connect(
                lambda text, t=title: setattr(self.desep, f"{t.lower()}_folder",
                                              text))
            layout.addWidget(line_edit)
            button = QtWidgets.QPushButton("...")
            button.clicked.connect(
                lambda _, t=title: line_edit.setText(
                    self.select_folder(t) or ""))
            layout.addWidget(button)

            return widget

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
                "--videos", shell_escape(self.desep.videos_folder),
                "--audio", shell_escape(self.desep.audio_folder),
                "--subtitles", shell_escape(self.desep.subtitles_folder),
                "--output", shell_escape(self.desep.output_folder),
                "--no-gui"
            ]
            logging.info(" ".join(args))
            self.progress_bar.setValue(0)

            def update_progress(file: str, progress: float):
                self.progress_bar.setValue(int(progress * 100))
                self.progress_bar.setFormat(
                    f"Processing {file}... {int(progress * 100)}%")

            try:
                self.desep.run(callback=update_progress)
                logging.info("De-separation completed successfully")
                QtWidgets.QMessageBox.information(self, "Success",
                                                  "De-separation completed successfully.")
            except Exception as e:
                logging.error("Error during de-separation: %s", e)
                QtWidgets.QMessageBox.critical(self, "Error",
                                               f"An error occurred: {e}")

        def __init__(self):
            super().__init__()
            self.desep = DeSep()
            self.setWindowTitle("DeSep MKV De-separator")
            self.setFixedSize(400, 300)
            main_widget = QtWidgets.QWidget()
            main_layout = QtWidgets.QVBoxLayout(main_widget)
            self.setCentralWidget(main_widget)

            main_layout.addWidget(self.spawn_folder_enter("Videos"))
            main_layout.addWidget(self.spawn_folder_enter("Audio"))
            main_layout.addWidget(self.spawn_folder_enter("Subtitles"))
            main_layout.addWidget(self.spawn_folder_enter("Output"))

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
    parser.add_argument("--videos", type=str,
                        help="Path to the folder with video files (used in GUI mode only)")
    parser.add_argument("--audio", type=str,
                        help="Path to the folder with audio files (used in GUI mode only)")
    parser.add_argument("--subtitles", type=str,
                        help="Path to the folder with subtitle files (used in GUI mode only)")
    parser.add_argument("--output", type=str,
                        help="Path to the output folder (used in GUI mode only)")

    args = parser.parse_args()
    setup_logging(args)

    logging.info("Running DeSep script")

    if args.no_gui:
        logging.info("Running in command line mode")
        if not args.videos or not args.audio or not args.subtitles:
            print(
                "Please specify the folders for videos, audio, and subtitles.")
            return 1

        desep = DeSep(videos_folder=args.videos, audio_folder=args.audio,
                      subtitles_folder=args.subtitles,
                      output_folder=args.output)
        with alive_bar(title="De-separating MKV containers",
                       bar="smooth") as bar:
            desep.run(callback=lambda file, progress: bar.text(
                f"Processing {file}...") or bar())
    else:
        logging.info("Running GUI mode")
        return run_gui()

    return 0


if __name__ == '__main__':
    exit(main())
