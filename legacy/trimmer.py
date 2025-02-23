#!/usr/bin/env python3

#
# @file mkv_trimmer.py
# @date 06-01-2025
# @author Maxim Kurylko <vk_vm@ukr.net>
#

import argparse
import logging
import platform
import re
import shutil
import tempfile
from enum import Enum
import os
import time
from typing import List
from rich.progress import Progress
import subprocess

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

class FFMpeg:
    FFMPEG = 'ffmpeg'
    FFPROBE = 'ffprobe'
    FFMPEG_PROCESSED_FRAMES_RE = re.compile(r'frame=\s*(\d+)')

    @staticmethod
    def get_supported_hevc_encoders(toolkit=FFMPEG):
        result = subprocess.run([toolkit, '-encoders', '-hide_banner'], stdout=subprocess.PIPE)
        result = result.stdout.decode('utf-8')
        encoders = []
        for line in result.split('\n'):
            if 'hevc' in line:
                encoders.append(line.split(' ')[2])
        return encoders

    @staticmethod
    def get_video_duration_seconds(file: str) -> float:
        args = [FFMpeg.FFPROBE, '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', file]
        logging.debug('Running ffprobe: [%s]', ' '.join(args))
        result = subprocess.run(args, stdout=subprocess.PIPE)
        return float(result.stdout.decode('utf-8'))

    @staticmethod
    def get_video_duration_frames(file: str) -> int:
        duration = FFMpeg.get_video_duration_seconds(file)

        # Using "count_frames" took too long, so just get the frame rate and duration
        args = [FFMpeg.FFPROBE, "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=r_frame_rate",
            "-of", "csv=p=0", file]
        logging.debug('Running ffprobe: [%s]', ' '.join(args))
        result = subprocess.run(args, stdout=subprocess.PIPE)

        output = result.stdout.decode('utf-8')
        logging.debug('ffprobe output: %s', output)

        # Let's not use 'eval' here...
        frame_rate = output.split('/')
        frame_rate = int(frame_rate[0]) / int(frame_rate[1])
        logging.debug('Frame rate: %f, duration: %f', frame_rate, duration)
        return int(frame_rate * duration)

    @staticmethod
    def get_gpu_name():
        if platform.system() == 'Windows':
            import wmi
            w = wmi.WMI(namespace="root\\CIMV2")
            for gpu in w.Win32_VideoController():
                return gpu.Name
        else:
            raise NotImplementedError('Only Windows is supported')

    SUPPORTED_HEVC_ENCODERS = get_supported_hevc_encoders()
    GPU_NAME = get_gpu_name()

    def __init__(self, file):
        self.file = file
        self.args = [self.FFMPEG, '-i', file, '-y']

    def audio_as_is(self) -> bool:
        self.args.extend(['-c:a', 'copy'])
        return True

    def subtitles_as_is(self) -> bool:
        self.args.extend(['-c:s', 'copy'])
        return True

    def video_as_is(self) -> bool:
        self.args.extend(['-c:v', 'copy'])
        return True

    def video_to_hevc(self, preset='slow', encoder=None) -> bool:
        if encoder is None:
            if 'NVIDIA' in self.GPU_NAME:
                encoder = 'hevc_nvenc'
            elif 'AMD' in self.GPU_NAME:
                encoder = 'hevc_amf'
            else:
                encoder = 'libx265'

        if encoder not in self.SUPPORTED_HEVC_ENCODERS:
            logging.error('Encoder %s is not supported', encoder)
            return False

        self.args.extend(['-c:v', encoder, '-preset', preset, '-vtag', 'hvc1'])
        return True

    def keep_all_attachments(self) -> bool:
        self.args.extend(['-map', '0:t?'])
        return True

    def keep_track(self, track) -> bool:
        self.args.extend(['-map', f'0:{track}'])
        return True

    def process(self, output_file: str, progress: Progress, task) -> bool:
        self.args.append(output_file)

        # Track progress
        self.args.append('-progress')
        self.args.append('pipe:1')
        self.args.append('-v')
        self.args.append('error')

        progress.update(
            task,
            description=f"[green]Processing {os.path.basename(self.file)}",
            total=self.get_video_duration_frames(self.file)
        )

        logging.debug('Running ffmpeg: [%s]', ' '.join(self.args))
        # If log file not specified, then log to stdout
        process = subprocess.Popen(self.args,
                               stdout=subprocess.PIPE,
                               universal_newlines=True,
                               encoding='utf-8',
                               bufsize=1)

        while True:
            # Print stdout
            line = process.stdout.readline()
            if line == '' and process.poll() is not None:
                break
            if line:
                match = self.FFMPEG_PROCESSED_FRAMES_RE.search(line)
                if match:
                    progress.update(task, completed=int(match.group(1)))
                logging.debug(line.strip())

        process.wait()

        return process.returncode == 0

class MKVInfo:
    TOOLKIT = 'C:\\Program Files\\MKVToolNix\\mkvinfo.exe'

    class TrackType(Enum):
        VIDEO = 0
        AUDIO = 1
        SUBTITLES = 2
        UNKNOWN = 3

    class Track:
        def __init__(self, number: int, type: "MKVInfo.TrackType", codec_id: str, language: str, name: str = None):
            self.number = number
            self.type = type
            self.codec_id = codec_id
            self.language = language
            self.name = name

        def __eq__(self, other):
            return self.type == other.type and self.codec_id == other.codec_id and self.language == other.language and self.number == other.number

        def __str__(self):
            return f'Track(id={self.number}, type={self.type}, codec_id={self.codec_id}, language={self.language}), name={self.name}'

    def __get_info(self):
        if os.path.exists(self.file):
            result = subprocess.run([self.TOOLKIT, self.file], stdout=subprocess.PIPE)
            result = result.stdout.decode('utf-8')
            return result
        else:
            raise FileNotFoundError('File not found')

    SEGMENT_INFO_REGEX = re.compile(r'^\|\s*\+ Segment information$')
    MUX_APP_REGEX = re.compile(r'^\|\s*\+ Multiplexing application: (.+)$')
    WRITING_APP_REGEX = re.compile(r'^\|\s*\+ Writing application: (.+)$')
    DURATION_REGEX = re.compile(r'^\|\s*\+ Duration: (\d+):(\d+):(\d+).(\d+)')
    TITLE_REGEX = re.compile(r'^\|\s*\+ Title: (.+)$')

    TRACK_REGEX = re.compile(r'^\|\s*\+ Track$')
    TRACK_TYPE_REGEX = re.compile(r'^\|\s*\+ Track type: (.+)$')
    TRACK_NUMBER_REGEX = re.compile(r'^\|\s*\+ Track number: \d+ \([\s\w&]+: (\d+)\)$')
    TRACK_CODEC_ID_REGEX = re.compile(r'^\|\s*\+ Codec ID: (.+)$')
    TRACK_LANGUAGE_REGEX = re.compile(r'^\|\s*\+ Language: (.+)$')
    TRACK_NAME_REGEX = re.compile(r'^\|\s*\+ Name: (.+)$')

    def __init__(self, file):
        logging.debug('Getting info for file: %s', file)
        self.file = file
        raw = self.__get_info()

        tracks_raw: List[List[str]] = []
        segment_info_raw: List[str] = None
        for line in raw.split('\n'):
            line = line.strip()
            if self.TRACK_REGEX.search(line):
                tracks_raw.append([])
            if self.SEGMENT_INFO_REGEX.search(line):
                segment_info_raw = []
            if len(tracks_raw) > 0:
                tracks_raw[-1].append(line)
            elif segment_info_raw is not None:
                segment_info_raw.append(line)

        self.tracks = []
        for track_raw in tracks_raw:
            track_type = MKVInfo.TrackType.UNKNOWN
            number = None
            codec_id = None
            language = None
            name = None
            for line in track_raw:
                if match := self.TRACK_TYPE_REGEX.search(line):
                    if match.group(1) == 'video':
                        track_type = MKVInfo.TrackType.VIDEO
                    elif match.group(1) == 'audio':
                        track_type = MKVInfo.TrackType.AUDIO
                    elif match.group(1) == 'subtitles':
                        track_type = MKVInfo.TrackType.SUBTITLES
                    else:
                        track_type = MKVInfo.TrackType.UNKNOWN
                if match := self.TRACK_NUMBER_REGEX.search(line):
                    number = int(match.group(1))
                if match := self.TRACK_CODEC_ID_REGEX.search(line):
                    codec_id = match.group(1)
                if match := self.TRACK_LANGUAGE_REGEX.search(line):
                    language = match.group(1)
                if match := self.TRACK_NAME_REGEX.search(line):
                    name = match.group(1)

            # Only name is optional
            if number is None:
                logging.error('Track number not found in file %s', file)
                continue
            if codec_id is None:
                logging.error('Codec ID not found in file %s', file)
                continue
            if language is None:
                logging.debug('Language not found, defaulting to "eng" for file %s', file)
                language = 'eng'
            if track_type == MKVInfo.TrackType.UNKNOWN:
                logging.debug('Track type not found in file %s', file)
            if name is None:
                logging.debug('Name not found in file %s', file)
                name = 'default'

            self.tracks.append(self.Track(number, track_type, codec_id, language, name))

        self.mux_app = None
        self.writing_app = None
        self.duration = None
        self.title = None
        for line in segment_info_raw:
            if match := self.MUX_APP_REGEX.search(line):
                self.mux_app = match.group(1)
            if match := self.WRITING_APP_REGEX.search(line):
                self.writing_app = match.group(1)
            if match := self.DURATION_REGEX.search(line):
                self.duration = int(match.group(1)) * 3600 + int(match.group(2)) * 60 + int(match.group(3)) + int(match.group(4)) / 100
            if match := self.TITLE_REGEX.search(line):
                self.title = match.group(1)

        if self.title is None:
            logging.warning('Title not found')
        if self.duration is None:
            logging.warning('Duration not found')
        if self.mux_app is None:
            logging.warning('Muxing application not found')
        if self.writing_app is None:
            logging.warning('Writing application not found')

        if len(self.tracks) == 0:
            logging.warning('No tracks found')

    def print_info(self):
        logging.info(f'File: {self.file}')
        logging.debug(f'Title: {self.title}')
        logging.debug(f'Duration: {self.duration}')
        logging.debug(f'Muxing application: {self.mux_app}')
        logging.debug(f'Writing application: {self.writing_app}')
        for track in self.tracks:
            logging.info("  %s", track)

def pretty_duration(seconds: float) -> str:
    if seconds < 120:
        return f'{int(seconds):02} seconds'
    elif seconds < 3600:
        minutes, seconds = divmod(seconds, 60)
        return f'{int(minutes):02}:{int(seconds):02}'
    else:
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        return f'{int(hours):02}:{int(minutes):02}:{int(seconds):02}'

def main():
    parser = argparse.ArgumentParser(description='MKV Trimmer')
    parser.add_argument("--log-file", type=str, help="Log file")
    parser.add_argument("-l", "--log", type=str, default="info", choices=["debug", "info", "warning", "error", "critical"],
                        help="Log level. Note: 'debug' log level may print sensitive information,\n"
                             "produce a lot of output and program may run slower/incorectly")
    parser.add_argument("--colorless", action="store_true", help="Disable colored output")

    parser.add_argument('input', nargs='+', help='Input files or directories', type=str, action='append')
    parser.add_argument("-r", "--recursive", action="store_true", help="Process files recursively")

    parser.add_argument("--suspend-os-after", type=bool, help="Suspend OS after processing")
    parser.add_argument("--hevc", type=bool, help="Reencode to HEVC")
    parser.add_argument("--hevc-encoder", type=str, help="HEVC encoder to use")
    parser.add_argument("--no-time-check", action="store_true", help="Do not check if the time is correct")
    parser.add_argument("--hevc-presets", type=str, help="HEVC presets to use")
    parser.add_argument("--keep-tracks", type=str, help="Comma separated list of common tracks to keep (if not specified will be prompted)")
    parser.add_argument("--audio-filter", type=str, help="Comma separated list of audio filters (if not specified will be prompted)")
    parser.add_argument("--subtitle-filter", type=str, help="Comma separated list of subtitle filters (if not specified will be prompted)")

    args = parser.parse_args()

    setup_logging(args)

    # Flatten input
    args.input = [item for sublist in args.input for item in sublist]

    logging.debug(args.input)
    logging.debug("ffprobe exe: %s", FFMpeg.FFPROBE)
    logging.debug("ffmpeg exe: %s", FFMpeg.FFMPEG)
    logging.debug("detected GPU name: %s", FFMpeg.GPU_NAME)
    logging.debug("supported HEVC encoders: %s", FFMpeg.SUPPORTED_HEVC_ENCODERS)
    logging.debug("mkvinfo exe: %s", MKVInfo.TOOLKIT)

    files = []
    def process_token(input_token, depth=0):
        logging.debug('Processing token: %s', input_token)
        if os.path.isdir(input_token):
            for token in os.listdir(input_token):
                if args.recursive or depth == 0:
                    process_token(os.path.join(input_token, token), depth + 1)
        elif os.path.isfile(input_token):
            if input_token.endswith('.mkv'):
                files.append(input_token)
        else:
            logging.error('Invalid input: %s', input_token)
            return
    for input_token in args.input:
        process_token(input_token)

    if len(files) == 0:
        logging.error('No files found')
        return

    logging.debug('Files to process:')
    for file in files:
        logging.debug(file)

    # If there's alot of files, make sure that their tracks are the same
    # If not, then we can't process them
    infos = []
    for file in files:
        info = MKVInfo(file)
        infos.append(info)
        info.print_info()

    # Common tracks
    common_tracks = []
    for info in infos:
        if len(common_tracks) == 0:
            common_tracks = info.tracks
        else:
            common_tracks = [track for track in common_tracks if track in info.tracks]

    if len(common_tracks) == 0:
        logging.error('No common tracks found')
        return

    logging.info('Common tracks:')
    for track in common_tracks:
        logging.info("  %s", track)

    # Flush all handlers
    [h_weak_ref().flush() for h_weak_ref in logging._handlerList]

    keep_any = False
    if args.keep_tracks is None:
        tracks = input('Enter tracks to keep (comma separated. "*" to keep any): ')
        if tracks == '*':
            keep_any = True
            tracks = []
    else:
        tracks = args.keep_tracks
    if not keep_any:
        tracks = [int(track) for track in tracks.split(',')]

    if args.audio_filter is None:
        audio_filter = input('Enter audio filter (comma separated): ').strip()
    else:
        audio_filter = args.audio_filter
    if audio_filter != '':
        audio_filter = audio_filter.lower().split(',')
    else:
        audio_filter = []

    if args.subtitle_filter is None:
        subtitle_filter = input('Enter subtitle filter (comma separated): ').strip()
    else:
        subtitle_filter = args.subtitle_filter
    if subtitle_filter != '':
        subtitle_filter = subtitle_filter.lower().split(',')
    else:
        subtitle_filter = []

    logging.debug('Selected tracks:')
    for track in tracks:
        logging.debug("  %s", common_tracks[track])

    def keep_track(track):
        if keep_any:
            return True

        if len(audio_filter) != 0:
            if track.type == MKVInfo.TrackType.AUDIO:
                for filter in audio_filter:
                    if filter in track.language.lower() or filter in track.name.lower():
                        return True

        if len(subtitle_filter) != 0:
            if track.type == MKVInfo.TrackType.SUBTITLES:
                for filter in subtitle_filter:
                    if filter in track.language.lower() or filter in track.name.lower():
                        return True

        return track.number in tracks

    global_stats = {}
    for info in infos:
        logging.info('File: %s', info.file)
        global_stats[info.file] = stats = {}
        for track in info.tracks:
            if keep_track(track):
                logging.info("  %s", track)
                stats[track.type] = stats.get(track.type, []) + [track.language]

    logging.info('Global stats:')
    for file, stats in global_stats.items():
        duration = 0 if args.no_time_check else FFMpeg.get_video_duration_seconds(file)
        logging.info('  [%8s] %-70s: %s',
                     pretty_duration(duration) if duration != 0 else 'N/A',
                     os.path.basename(file),
                     [f'{k.name}: {v}' for k, v in stats.items()])

    if args.hevc is None:
        need_hevc = input('Reencode selected tracks to HEVC (H.265)? (y/n): ')
    else:
        logging.info('%s HEVC reencoding', 'Enabling' if args.hevc else 'Disabling')
        need_hevc = 'y' if args.hevc else 'n'
    need_hevc = need_hevc.lower() == 'y'

    if args.suspend_os_after is None:
        suspend_os_after = input('Suspend OS after processing? (y/n): ')
    else:
        logging.info('%s OS suspension', 'Enabling' if args.suspend_os_after else 'Disabling')
        suspend_os_after = 'y' if args.suspend_os_after else 'n'
    suspend_os_after = suspend_os_after.lower() == 'y'

    def unique_bak_name(file):
        i = 0
        while True:
            new_file = f'{file}.bak{i}'
            if not os.path.exists(new_file):
                return new_file
            i += 1

    def process(info: MKVInfo, progress: Progress, task):
        logging.debug('Processing file: %s', info.file)
        outfile = os.path.join(os.path.dirname(info.file), 'trimmed_' + os.path.basename(info.file))

        ffmpeg = FFMpeg(info.file)
        ffmpeg.audio_as_is()
        ffmpeg.subtitles_as_is()
        ffmpeg.keep_all_attachments()

        for track in info.tracks:
            if keep_track(track):
                ffmpeg.keep_track(track.number)

        reencode = False
        if need_hevc:
            for track in info.tracks:
                if track.type == MKVInfo.TrackType.VIDEO and keep_track(track) and 'hevc' not in track.codec_id:
                    logging.debug('Will reencode video track #%d', track.number)
                    reencode = True
                    break
        if reencode:
            ffmpeg.video_to_hevc()

        if ffmpeg.process(outfile, progress, task):
            logging.debug('File processed successfully')

            # Backup original file
            bak = unique_bak_name(info.file)
            logging.debug('Backing up original file to %s', bak)
            shutil.move(info.file, bak)

            # Move new file to original location
            logging.debug('Moving new file to original location')
            shutil.move(outfile, info.file)

    logging.info('Processing files...')

    # Display progess bar using alive bar
    with Progress() as progress:
        total_task = progress.add_task("[blue]Total progress", total=len(infos))
        file_task = progress.add_task("[green]Processing file", total=len(infos))
        for i, info in enumerate(infos):
            process(info, progress, file_task)
            progress.update(total_task, completed=i + 1)

    if suspend_os_after:
        logging.info('Suspending OS...')
        # Enter hybernation
        os.system('shutdown /h')

if __name__ == '__main__':
    main()
