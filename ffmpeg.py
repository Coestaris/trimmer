#!/usr/bin/env python3

#
# @file ffmpeg.py
# @date 23-02-2025
# @author Maxim Kurylko <vk_vm@ukr.net>
#

import json
import re
import subprocess
import logging
from typing import Optional, List, Callable

from utils import run

# 02:27:57.535000000
FFMPEG_DURATION_RE = re.compile(r'(?P<hours>\d+):(?P<minutes>\d+):(?P<seconds>\d+\.\d+)')
# 24000/1001
FFMPEG_FRAME_RATE_RE = re.compile(r'(?P<dividend>\d+)/(?P<divisor>\d+)')

def find_ffmpeg() -> Optional[str]:
    import shutil
    return shutil.which('ffmpeg')

def find_ffprobe() -> Optional[str]:
    import shutil
    return shutil.which('ffprobe')

def get_supported_hevc_encoders(ffmpeg: str) -> Optional[List[str]]:
    args = [ffmpeg, '-hide_banner', '-encoders']

    code, result = run(args)
    if code != 0:
        logging.error('Failed to get encoders: %s', result)
        return None

    encoders = []
    for line in result.split('\n'):
        if 'hevc' in line:
            encoders.append(line.split(' ')[2])
    return encoders

def get_video_duration_seconds(ffprobe: str, file: str) -> Optional[float]:
    args = [ffprobe, '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', file]
    code, result = run(args)
    if code != 0:
        logging.error('Failed to get video duration: %s', result)
        return None

    return float(result)

def get_video_duration_frames(ffprobe: str, file: str) -> Optional[int]:
    duration_sec = get_video_duration_seconds(ffprobe, file)
    if duration_sec is None:
        return None

    # Using "count_frames" took too long, so just get the frame rate and duration
    args = [ffprobe, "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=r_frame_rate",
        "-of", "csv=p=0", file]
    code, output = run(args)
    if code != 0:
        logging.error('Failed to get frame rate: %s', output)
        return None

    # Let's not use 'eval' here...
    frame_rate = output.split('/')
    frame_rate = int(frame_rate[0]) / int(frame_rate[1])

    logging.debug('Frame rate: %f, duration: %f', frame_rate, duration_sec)
    return int(frame_rate * duration_sec)

class FFMpegTrack:
    def __init__(self, index: int, codec: str, language: str, title: str, duration: float):
        self.index = index
        self.codec = codec
        self.language = language
        self.title = title
        self.duration = duration
        self.keep = True

    def __str__(self):
        return f'{self.index}; codec={self.codec}, lang={self.language}, title=\"{self.title}\", duration={self.duration:.2f}'

    def __repr__(self):
        return self.__str__()

class VideoTrack(FFMpegTrack):
    def __init__(self, index: int, codec: str, language: str, title: str, duration: float, frame_rate: float):
        super().__init__(index, codec, language, title, duration)
        self.frame_rate = frame_rate

    def is_h265(self) -> bool:
        return 'hevc' in self.codec or 'h265' in self.codec

    def __str__(self):
        return f'VideoTrack({super().__str__()}, fps={self.frame_rate:.2f})'

class AudioTrack(FFMpegTrack):
    def __init__(self, index: int, codec: str, language: str, title: str, duration: float, channels: int):
        super().__init__(index, codec, language, title, duration)
        self.channels = channels

    def __str__(self):
        return f'AudioTrack({super().__str__()}, channels={self.channels})'

class SubtitleTrack(FFMpegTrack):
    def __init__(self, index: int, codec: str, language: str, title: str, duration: float):
        super().__init__(index, codec, language, title, duration)

    def __str__(self):
        return f'SubtitleTrack({super().__str__()})'

def get_video_tracks(ffprobe: str, file: str) -> Optional[List['FFMpegTrack']]:
    def duration_to_secs(duration: str) -> float:
        match = FFMPEG_DURATION_RE.match(duration)
        if match is None:
            logging.warning(
                'Invalid duration: %s while processing %s (stream type %s)',
                duration, file, type)
            return 0

        return \
                int(match.group('hours')) * 3600 + \
                int(match.group('minutes')) * 60 + \
                float(match.group('seconds'))

    def frame_rate_to_float(frame_rate: str) -> float:
        match = FFMPEG_FRAME_RATE_RE.match(frame_rate)
        if match is None:
            logging.warning(
                'Invalid frame rate: %s while processing %s (stream type %s)',
                frame_rate, file, type)
            return 0

        return int(match.group('dividend')) / int(match.group('divisor'))

    def process_streams(
            type: str,
            add_tags: str,
            add_entries: str,
            parser: callable) -> Optional[List[FFMpegTrack]]:

        args = [
            ffprobe,
            '-v', 'error',
            '-select_streams', type,
            '-show_entries', f'stream={add_entries},duration,index,codec_name:stream_tags=language,duration,title{add_tags}',
            '-of', 'json',
            file
        ]
        code, result = run(args)
        if code != 0:
            logging.error('Failed to get tracks: %s', result)
            return []

        tracks = []
        data = json.loads(result)
        for stream in data['streams']:
            index = stream['index']
            codec = stream['codec_name']

            def select_tag(tag: str) -> Optional[str]:
                if 'tags' not in stream:
                    logging.warning('No tags in stream %d while processing %s (stream type %s)', index, file, type)
                    return None
                if tag not in stream['tags']:
                    logging.warning('No tag %s in stream %d while processing %s (stream type %s)', tag, index, file, type)
                    return None
                return stream['tags'][tag]
            if (title := select_tag('title')) is None:
                title = "default"
            if (language := select_tag('language')) is None:
                language = "und"
            if (duration := select_tag('DURATION')) is None:
                if 'duration' not in stream:
                    logging.warning('No duration in stream %d while processing %s (stream type %s)', index, file, type)
                    duration = 0
                else:
                    duration = float(stream['duration'])
            else:
                duration = duration_to_secs(duration)

            tracks.append(parser(index, codec, language, title, duration, stream))

        return tracks

    tracks = []
    if (res := process_streams(
            'V',
            '',
            'r_frame_rate,',
            lambda index, codec, language, title, duration, data: VideoTrack(
                index, codec, language, title, duration,
                frame_rate_to_float(data['r_frame_rate'])))) is None:
        logging.error('Failed to get video tracks')
        return None
    tracks.extend(res)

    if (res := process_streams(
            'a',
            '',
            'channels,',
            lambda index, codec, language, title, duration, data: AudioTrack(
                index, codec, language, title, duration,
                data['channels']))) is None:
        logging.error('Failed to get audio tracks')
        return None
    tracks.extend(res)

    if (res := process_streams(
            's',
            '',
            '',
            lambda index, codec, language, title, duration, _: SubtitleTrack(
                index, codec, language, title, duration))) is None:
        logging.error('Failed to get subtitle tracks')
        return None
    tracks.extend(res)

    return tracks

class FFMpegRemuxer:
    # frame=2567
    FFMPEG_PROCESSED_FRAMES_RE = re.compile(r'frame=(?P<frame>\d+)')
    # fps=13.90
    FFMPEG_FPS_RE = re.compile(r'fps=(?P<fps>\d+\.\d+)')

    def __init__(self, ffmpeg: str, file: str):
        self.args = [ffmpeg, '-i', file, '-y']

    def audio_as_is(self) -> 'FFMpegRemuxer':
        self.args.extend(['-c:a', 'copy'])
        return self

    def subtitles_as_is(self) -> 'FFMpegRemuxer':
        self.args.extend(['-c:s', 'copy'])
        return self

    def video_as_is(self, track: VideoTrack) -> 'FFMpegRemuxer':
        self.args.extend(['-c:v', 'copy'])
        return self

    def video_to_hevc(self, track: VideoTrack, preset: str, encoder: str) -> 'FFMpegRemuxer':
        self.args.extend(['-c:v', encoder, '-preset', preset, '-vtag', 'hvc1'])
        return self

    def keep_all_attachments(self) -> 'FFMpegRemuxer':
        self.args.extend(['-map', '0:t?'])
        return self

    def keep_track(self, track: FFMpegTrack) -> 'FFMpegRemuxer':
        self.args.extend(['-map', f'0:{track.index}'])
        return self

    def process(self, output_file: str, on_progress: Callable[[int, float], None]) -> bool:
        self.args.append(output_file)

        # Track progress
        self.args.append('-progress')
        self.args.append('pipe:1')
        self.args.append('-v')
        self.args.append('error')

        logging.debug('Running ffmpeg: [%s]', ' '.join(self.args))

        # If log file not specified, then log to stdout
        process = subprocess.Popen(self.args,
                               stdout=subprocess.PIPE,
                               universal_newlines=True,
                               encoding='utf-8',
                               bufsize=1)

        frame = 0
        fps = 0
        while True:
            # Print stdout
            line = process.stdout.readline()
            if line == '' and process.poll() is not None:
                break
            if line:
                if (match := self.FFMPEG_PROCESSED_FRAMES_RE.match(line)) is not None:
                    frame = int(match.group('frame'))
                if (match := self.FFMPEG_FPS_RE.match(line)) is not None:
                    fps = float(match.group('fps'))
                on_progress(frame, fps)
                logging.debug(line.strip())


        process.wait()

        return process.returncode == 0

def prefer_hevc_encoder(encoders: List[str], gpu_name: str) -> Optional[str]:
    if 'nvidia' in gpu_name.lower():
        for encoder in encoders:
            if 'nvenc' in encoder:
                return encoder
    elif 'intel' in gpu_name.lower():
        for encoder in encoders:
            if 'qsv' in encoder:
                return encoder
    elif 'amd' in gpu_name.lower():
        for encoder in encoders:
            if 'amf' in encoder:
                return encoder

    if 'libx265' in encoders:
        return 'libx265'

    return None