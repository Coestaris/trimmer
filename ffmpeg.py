#!/usr/bin/env python3
import errno
#
# @file ffmpeg.py
# @date 23-02-2025
# @author Maxim Kurylko <vk_vm@ukr.net>
#

import json
import re
import subprocess
import logging
from typing import Optional, List, Callable, Any
import shutil
from result import Result, Ok, Err

from utils import run

# 02:27:57.535000000
FFMPEG_DURATION_RE = re.compile(r'(?P<hours>\d+):(?P<minutes>\d+):(?P<seconds>\d+\.\d+)')
# 24000/1001
FFMPEG_FRAME_RATE_RE = re.compile(r'(?P<dividend>\d+)/(?P<divisor>\d+)')

logger = logging.getLogger(__name__)

# TODO: Maybe get this from ffmpeg?
class Codec:
    def __init__(self, name: str,
                 presets: List[str],
                 preferred_preset: str,
                 tunes: List[str],
                 preferred_tune: str,
                 profiles: List[str],
                 preferred_profile: str):
        self.name = name

        self.presets = presets
        self.preferred_preset = preferred_preset

        self.tunes = tunes
        self.preferred_tune = preferred_tune

        self.profiles = profiles
        self.preferred_profile = preferred_profile

    def __str__(self):
        return f'Codec({self.name})'

LIBX265_CODEC = Codec(
    'libx265',
    [
        'ultrafast',
        'superfast',
        'veryfast',
        'faster',
        'fast',
        'medium' ,
        'slow',
        'slower',
        'veryslow',
        'placebo',
    ],
    'slow',
    [
        'psnr',
        'ssim',
        'grain',
        'fastdecode',
        'zerolatency',
        'animation'
    ],
    'grain',
    [
        'main',
        'main444-8',
        'main10',
        'main422-10',
        'main444-10',
        'main12',
        'main422-12',
        'main444-12',
    ],
    'main'
)

HEVC_NVENC_CODEC = Codec(
    'hevc_nvenc',
    [
        'default',
        'slow',  # hq 2 passes
        'medium',  # hq 1 pass
        'fast',  # hp 1 pass
        'hp',
        'hq',
        'bd',
        'll',  # low latency
        'llhq',  # low latency hq
        'llhp',  # low latency hp
        'lossless',  # lossless
        'losslesshp',  # lossless hp
        'p1',  # fastest (lowest quality)
        'p2',  # faster (lower quality)
        'p3',  # fast (low quality)
        'p4',  # medium (default)
        'p5',  # slow (good quality)
        'p6',  # slower (better quality)
        'p7',  # slowest (best quality)
     ],
    'p6',
    [
        'hq', # High quality
        'll', # Low latency
        'ull', # Ultra low latency
        'lossless', # Set the encoding profile (from 0 to 4) (default main)
    ],
    'hq',
    [
        'main',
        'main10',
        'rext',
    ],
    'main'
)

def find_ffmpeg() -> Result[str, str]:
    ffmpeg = shutil.which('ffmpeg')
    if ffmpeg is None:
        return Err('ffmpeg not found')

    return Ok(ffmpeg)

def find_ffprobe() -> Result[str, str]:
    ffprobe = shutil.which('ffprobe')
    if ffprobe is None:
        return Err('ffprobe not found')

    return Ok(ffprobe)

def get_supported_hevc_codecs(ffmpeg: str) -> Result[List[Codec], str]:
    args = [ffmpeg, '-hide_banner', '-encoders']

    code, result = run(args)
    if code != 0:
        return Err(f'Failed to get codecs: {result.strip()}')

    known_codecs = [ LIBX265_CODEC, HEVC_NVENC_CODEC ]
    codecs = []
    for line in result.split('\n'):
        for codec in known_codecs:
            if codec.name in line:
                codecs.append(codec)
                break

    return Ok(codecs)

def get_video_duration_seconds(ffprobe: str, file: str) -> Result[float, str]:
    args = [ffprobe, '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', file]
    code, result = run(args)
    if code != 0:
        return Err(f'Failed to get duration: {result.strip()}')

    return Ok(float(result))

def get_video_duration_frames(ffprobe: str, file: str) -> Result[int, str]:
    duration_sec = get_video_duration_seconds(ffprobe, file)
    if isinstance(duration_sec, Err):
        return duration_sec

    # Using "count_frames" took too long, so just get the frame rate and duration
    args = [ffprobe, "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=r_frame_rate",
        "-of", "csv=p=0", file]
    code, output = run(args)
    if code != 0:
        return Err(f'Failed to get frame rate: {output.strip()}')

    # Let's not use 'eval' here...
    frame_rate = output.split('/')
    frame_rate = int(frame_rate[0]) / int(frame_rate[1])

    logger.debug('Frame rate: %f, duration: %f', frame_rate, duration_sec.unwrap())
    return Ok(int(frame_rate * duration_sec.unwrap()))

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

def get_video_tracks(ffprobe: str, file: str) -> Result[List['FFMpegTrack'], str]:
    def duration_to_secs(duration: str) -> float:
        match = FFMPEG_DURATION_RE.match(duration)
        if match is None:
            logger.warning(
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
            logger.warning(
                'Invalid frame rate: %s while processing %s (stream type %s)',
                frame_rate, file, type)
            return 0

        return int(match.group('dividend')) / int(match.group('divisor'))

    def process_streams(
            type: str,
            add_tags: str,
            add_entries: str,
            parser: callable) -> Result[List[FFMpegTrack], str]:

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
            return Err(f'Failed to get {type} streams: {result.strip()}')

        tracks = []
        data = json.loads(result)
        for stream in data['streams']:
            index = stream['index']
            codec = stream['codec_name']

            def select_tag(tag: str) -> Optional[str]:
                if 'tags' not in stream:
                    logger.warning('No tags in stream %d while processing %s (stream type %s)', index, file, type)
                    return None
                if tag not in stream['tags']:
                    logger.warning('No tag %s in stream %d while processing %s (stream type %s)', tag, index, file, type)
                    return None
                return stream['tags'][tag]
            if (title := select_tag('title')) is None:
                title = "default"
            if (language := select_tag('language')) is None:
                language = "und"
            if (duration := select_tag('DURATION')) is None:
                if 'duration' not in stream:
                    logger.warning('No duration in stream %d while processing %s (stream type %s)', index, file, type)
                    duration = 0
                else:
                    duration = float(stream['duration'])
            else:
                duration = duration_to_secs(duration)

            tracks.append(parser(index, codec, language, title, duration, stream))

        return Ok(tracks)

    tracks = []
    res = process_streams(
            'V',
            '',
            'r_frame_rate,',
            lambda index, codec, language, title, duration, data: VideoTrack(
                index, codec, language, title, duration,
                frame_rate_to_float(data['r_frame_rate'])))
    if res.is_err():
        return res
    tracks.extend(res.unwrap())

    res = process_streams(
            'a',
            '',
            'channels,',
            lambda index, codec, language, title, duration, data: AudioTrack(
                index, codec, language, title, duration,
                data['channels']))
    if res.is_err():
        return res
    tracks.extend(res.unwrap())

    res = process_streams(
            's',
            '',
            '',
            lambda index, codec, language, title, duration, _: SubtitleTrack(
                index, codec, language, title, duration))
    if res.is_err():
        return res
    tracks.extend(res.unwrap())

    if len(tracks) == 0:
        return Err('No tracks found')

    return Ok(tracks)

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

    def video_as_is(self, _: VideoTrack) -> 'FFMpegRemuxer':
        self.args.extend(['-c:v', 'copy'])
        return self

    def video_to_hevc(self, _: VideoTrack, codec: Codec, preset: str, tune: str, profile: str) -> 'FFMpegRemuxer':
        self.args.extend(['-c:v', codec.name, '-preset', preset, '-tune', tune, '-profile:v', profile, '-vtag', 'hvc1'])
        return self

    def keep_all_attachments(self) -> 'FFMpegRemuxer':
        self.args.extend(['-map', '0:t?'])
        return self

    def keep_track(self, track: FFMpegTrack) -> 'FFMpegRemuxer':
        self.args.extend(['-map', f'0:{track.index}'])
        return self

    def process(self, output_file: str, on_progress: Callable[[int, float], None]) -> Result[Any, str]:
        self.args.append(output_file)

        # Track progress
        self.args.append('-progress')
        self.args.append('pipe:1')
        self.args.append('-v')
        self.args.append('error')

        logger.debug('Running ffmpeg: [%s]', ' '.join(self.args))
        process = subprocess.Popen(self.args,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               universal_newlines=True,
                               encoding='utf-8',
                               bufsize=1)

        frame = 0
        fps = 0
        updated = True
        while True:
            # Print stdout
            line = process.stdout.readline()
            if line == '' and process.poll() is not None:
                break
            if line:
                if (match := self.FFMPEG_PROCESSED_FRAMES_RE.match(line)) is not None:
                    frame = int(match.group('frame'))
                    updated = True
                if (match := self.FFMPEG_FPS_RE.match(line)) is not None:
                    fps = float(match.group('fps'))
                    updated = True

                if updated:
                    on_progress(frame, fps)
                    updated = False
                logger.debug(line.strip())

        # Read stderr
        stderr = ''
        while True:
            line = process.stderr.readline()
            if line == '' and process.poll() is not None:
                break
            if line:
                stderr += line
                logger.debug(line.strip())

        process.wait()

        if process.returncode == 0:
            return Ok(None)


        return Err(f'Failed to process file. Exit code: {process.returncode} ({process.returncode}): {stderr.strip()}')
