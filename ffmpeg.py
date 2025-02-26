#!/usr/bin/env python3

#
# @file ffmpeg.py
# @date 23-02-2025
# @author Maxim Kurylko <vk_vm@ukr.net>
#

import json
import platform
import re
import subprocess
import logging
from codec import Codec, KNOWN_CODECS
from typing import Optional, List, Callable, Any, Dict
from result import Result, Ok, Err
import atexit

from track import Track, VideoTrack, AudioTrack, SubtitleTrack
from utils import run, pretty_errno

# 02:27:57.535000000
FFMPEG_DURATION_RE = re.compile(r'(?P<hours>\d+):(?P<minutes>\d+):(?P<seconds>\d+\.\d+)')
# 24000/1001
FFMPEG_FRAME_RATE_RE = re.compile(r'(?P<dividend>\d+)/(?P<divisor>\d+)')

logger = logging.getLogger(__name__)

def get_supported_hevc_codecs(ffmpeg: str) -> Result[List[Codec], str]:
    args = [ffmpeg, '-hide_banner', '-encoders']

    code, result = run(args)
    if code != 0:
        return Err(f'Failed to get codecs: {result.strip()}')

    codecs = []
    for line in result.split('\n'):
        for codec in KNOWN_CODECS:
            if codec.name in line:
                codecs.append(codec)
                break

    return Ok(codecs)

def get_container_metadata(ffprobe: str, file: str) -> Result[dict, str]:
    args = [ffprobe, '-v', 'error', '-show_entries', 'format_tags', '-of', 'json', file]
    code, result = run(args)
    if code != 0:
        return Err(f'Failed to get metadata: {result.strip()}')

    data = json.loads(result)
    if 'format' not in data:
        return Err('No format in metadata')

    if 'tags' not in data['format']:
        return Err('No tags in metadata')

    return Ok(data['format']['tags'])

def get_container_duration_seconds(ffprobe: str, file: str) -> Result[float, str]:
    args = [ffprobe, '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', file]
    code, result = run(args)
    if code != 0:
        return Err(f'Failed to get duration: {result.strip()}')

    return Ok(float(result))

def get_container_duration_frames(ffprobe: str, file: str) -> Result[int, str]:
    duration_sec = get_container_duration_seconds(ffprobe, file)
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

def get_video_tracks(ffprobe: str, file: str) -> Result[List['Track'], str]:
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
            parser: callable) -> Result[List[Track], str]:

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
    # Process video
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

    # Process audio
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

    # Process subtitles
    res = process_streams(
            's',
            '',
            '',
            lambda index, codec, language, title, duration, _: SubtitleTrack(
                index, codec, language, title, duration))
    if res.is_err():
        return res
    tracks.extend(res.unwrap())

    # Process attachments
    res = process_streams(
            'd',
            '',
            '',
            lambda index, codec, language, title, duration, _: Track(
                index, codec, language, title, duration))
    if res.is_err():
        return res

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

    def keep_track(self, track: Track) -> 'FFMpegRemuxer':
        # Keep track and update title/language
        self.args.extend(['-map', f'0:{track.index}',
                            f'-metadata:s:{track.index}', f'language={track.language}',
                            f'-metadata:s:{track.index}', f'title={track.title}'])
        return self

    def set_format_metadata(self, data: Dict[str, str]) -> 'FFMpegRemuxer':
        for key, value in data.items():
            self.args.extend(['-metadata', f'{key}={value}'])
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
                               creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == 'Windows' else 0,
                               bufsize=1)

        pid = process.pid
        # Kill the process if the parent is killed
        def kill_child():
            logger.warning('Unxepected exit. Killing child process: %d', pid)
            if platform.system() == 'Windows':
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            else:
                process.kill()
        atexit.register(kill_child)

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
                    new_frame = int(match.group('frame'))
                    updated = updated or new_frame != frame
                    frame = new_frame
                if (match := self.FFMPEG_FPS_RE.match(line)) is not None:
                    new_fps = float(match.group('fps'))
                    updated = updated or new_fps != fps
                    fps = new_fps

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

        atexit.unregister(kill_child)

        return Err(f'Failed to process file. Exit code: {process.returncode} ({process.returncode} - {pretty_errno(process.returncode)}): {stderr.strip()}')
