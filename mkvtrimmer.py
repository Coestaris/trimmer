#!/usr/bin/env python3

#
# @file mkvtrimmer.py
# @date 23-02-2025
# @author Maxim Kurylko <vk_vm@ukr.net>
#

import argparse
import logging

from ffmpeg import find_ffmpeg, find_ffprobe, get_supported_hevc_encoders, \
    get_video_duration_seconds, get_video_tracks, VideoTrack
from gui import run_gui
from utils import get_gpu_name


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
        logging.addLevelName(logging.CRITICAL, f"{Fore.RED}{logging.getLevelName(logging.CRITICAL)}{Fore.RESET}")
        logging.addLevelName(logging.ERROR, f"{Fore.RED}{logging.getLevelName(logging.ERROR)}{Fore.RESET}")
        logging.addLevelName(logging.WARNING, f"{Fore.YELLOW}{logging.getLevelName(logging.WARNING)}{Fore.RESET}")
        logging.addLevelName(logging.INFO, f"{Fore.GREEN}{logging.getLevelName(logging.INFO)}{Fore.RESET}")
        logging.addLevelName(logging.DEBUG, f"{Fore.CYAN}{logging.getLevelName(logging.DEBUG)}{Fore.RESET}")

    logging.getLogger().setLevel(logging.getLevelName(args.log.upper()))
    # Output to file
    if args.log_file is not None:
        handler = logging.FileHandler(args.log_file)
    else:
        handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(get_format_string(not args.colorless, args.log == "debug")))
    logging.getLogger().addHandler(handler)

class MKVFile:
    def __init__(self, file: str):
        self.file = file
        self.tracks = []
        self.duration_frames = None

    def __estimate_duration_frames(self) -> int:
        estimations = []
        for track in self.tracks:
            if isinstance(track, VideoTrack):
                if track.frame_rate is not None and track.frame_rate != 0:
                    fps = track.frame_rate
                else:
                    logging.warning("No frame rate for track %s", track)

                if track.duration is not None and track.duration != 0:
                    duration = track.duration
                else:
                    logging.warning("No duration for track %s", track)

                estimations.append(int(fps * duration))

        # If there are no video tracks, return None
        if len(estimations) == 0:
            logging.warning("Cannot estimate duration in frames: no video tracks of file %s", self.file)
            return None

        # If estimations are different, return the average
        ALLOWED_DIFFERENCE = 0.01 # 1%
        if max(estimations) - min(estimations) > max(estimations) * ALLOWED_DIFFERENCE:
            logging.warning("Estimations are different: %s", estimations)
            return sum(estimations) // len(estimations)

        return estimations[0]

    def parse(self, ffprobe: str) -> bool:
        self.tracks = get_video_tracks(ffprobe, self.file)
        if self.tracks is None:
            logging.error('Failed to get video tracks of file %s', self.file)
            return False
        logging.debug('Tracks: %s', self.tracks)

        self.duration_frames = self.__estimate_duration_frames()
        logging.debug('Duration in frames: %s', self.duration_frames)
        pass

def main():
    parser = argparse.ArgumentParser(description='MKV Trimmer')
    parser.add_argument("--log-file", type=str, help="Log file")
    parser.add_argument("-l", "--log", type=str, default="info",
                        choices=["debug", "info", "warning", "error",
                                 "critical"],
                        help="Log level. Note: 'debug' log level may print sensitive information,\n"
                             "produce a lot of output and program may run slower/incorectly")
    parser.add_argument("--colorless", action="store_true",
                        help="Disable colored output")
    args = parser.parse_args()

    setup_logging(args)

    run_gui()

if __name__ == '__main__':
    main()
