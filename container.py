#!/usr/bin/env python3

#
# @file container.py
# @date 24-02-2025
# @author Maxim Kurylko <vk_vm@ukr.net>
#

import platform
import time
from result import Result, Err, Ok
from ffmpeg import VideoTrack, get_video_tracks, FFMpegRemuxer, Codec, \
    get_container_metadata
import logging
import os
import shutil
from typing import Callable, Any, List, Optional
from __version__ import __version__

from track import Track
from utils import unique_bak_name, pretty_date

logger = logging.getLogger(__name__)

class ContainerType:
    def __init__(self, ext: str, description: str):
        self.__ext = ext # Without dot
        self.__description = description

    @property
    def ext(self) -> str:
        return self.__ext

    @property
    def description(self) -> str:
        return self.__description

    def __str__(self):
        return f'{self.ext} ({self.description})'

    def __repr__(self):
        return f'ContainerType({self.ext}, {self.description})'

SUPPORTED_CONTAINERS = [
    ContainerType('mkv', 'Matroska Video File'),
    ContainerType('webm', 'WebM Video File'),
    ContainerType('mp4', 'MPEG-4 Video File'),
    ContainerType('mov', 'QuickTime Movie'),
    ContainerType('m2ts', 'Blu-ray BDAV Video File'),
]

PREFERRED_CONTAINER = SUPPORTED_CONTAINERS[0]

class Container:
    @staticmethod
    def __get_container_type(file: str) -> Result[ContainerType, str]:
        ext = file.split('.')[-1]
        for container in SUPPORTED_CONTAINERS:
            if container.ext == ext:
                return Ok(container)
        return Err(f'Unsupported container: {ext}')

    @staticmethod
    def __get_signature() -> str:
        return f'{__version__} (Python {platform.python_version()}), {pretty_date(time.time())}'

    def __estimate_duration(self):
        durations_sec = []
        if 'DURATION' in self.__metadata:
            durations_sec.append(float(self.__metadata['DURATION']))
        if 'duration' in self.__metadata:
            durations_sec.append(float(self.__metadata['duration']))

        fps = []
        for track in self.__tracks:
            if isinstance(track, VideoTrack):
                if track.frame_rate is not None and track.frame_rate != 0:
                    fps.append(track.frame_rate)
            if track.duration is not None and track.duration != 0:
                durations_sec.append(track.duration)

        def trim_to_one(name, lst):
            if len(lst) == 0:
                logger.warning("Cannot estimate %s: no tracks", name)
                return None

            if len(lst) == 1:
                return lst[0]

            # If estimations are different, return the average
            ALLOWED_DIFFERENCE = 0.01 # 1%
            if max(lst) - min(lst) > max(lst) * ALLOWED_DIFFERENCE:
                logger.warning("Estimations of %s are different: %s", name, lst)
                return sum(lst) // len(lst)

            return lst[0]

        duration_sec = trim_to_one('duration', durations_sec)
        frame_rate = trim_to_one('frame rate', fps)
        if duration_sec is None or frame_rate is None:
            self.__duration_seconds = 0
            self.__duration_frames = 0
            self.__fps = 0
        else:
            self.__duration_seconds = duration_sec
            self.__duration_frames = int(duration_sec * frame_rate)
            self.__fps = frame_rate

    def __init__(self, file: str, codec: Codec):
        self.__file = file

        self.__codec = codec
        self.__preset = codec.preferred_preset
        self.__tune = codec.preferred_tune
        self.__profile = codec.preferred_profile

        # Will be set by parse()
        self.__tracks = []
        self.__container = None
        self.__duration_frames = None
        self.__duration_seconds = None
        self.__fps = None
        self.__metadata = None

    @property
    def file(self) -> str:
        return self.__file

    @property
    def codec(self) -> Codec:
        return self.__codec

    @codec.setter
    def codec(self, codec: Codec):
        self.__codec = codec
        self.__preset = codec.preferred_preset
        self.__tune = codec.preferred_tune
        self.__profile = codec.preferred_profile

    @property
    def preset(self) -> str:
        return self.__preset

    @preset.setter
    def preset(self, preset: str):
        self.__preset = preset

    @property
    def tune(self) -> str:
        return self.__tune

    @tune.setter
    def tune(self, tune: str):
        self.__tune = tune

    @property
    def profile(self) -> str:
        return self.__profile

    @profile.setter
    def profile(self, profile: str):
        self.__profile = profile

    @property
    def container(self) -> ContainerType:
        return self.__container

    @container.setter
    def container(self, container: ContainerType):
        self.__container = container

    @property
    def duration_frames(self) -> int:
        return self.__duration_frames

    @property
    def duration_seconds(self) -> float:
        return self.__duration_seconds

    @property
    def fps(self) -> float:
        return self.__fps

    @property
    def tracks(self) -> List[Track]:
        return self.__tracks

    @property
    def title(self) -> Optional[str]:
        return self.__metadata.get('title', None)

    @title.setter
    def title(self, title: str):
        self.__metadata['title'] = title

    @property
    def metadata(self) -> dict:
        return self.__metadata

    def parse(self, ffprobe: str) -> Result[Any, str]:
        self.__container = self.__get_container_type(self.file)
        if self.__container.is_err():
            return Err(f"Unsupported container")
        self.__container = self.__container.unwrap()

        self.__metadata = get_container_metadata(ffprobe, self.file)
        if self.__metadata.is_err():
            logging.warning(f"Unable to get container metadata: {self.__metadata.unwrap_err()}")
            self.__metadata = {}
        else:
            self.__metadata = self.__metadata.unwrap()
        self.__metadata['TRIMMER_VERSION'] = self.__get_signature()
        logger.debug('Metadata: %s', self.__metadata)

        self.__tracks = get_video_tracks(ffprobe, self.file)
        if self.__tracks.is_err():
            return Err(f"Unable to get list of tracks: {self.__tracks.unwrap_err()}")
        self.__tracks = self.__tracks.unwrap()
        logger.debug('Tracks: %s', self.tracks)

        self.__estimate_duration()
        logger.debug('Duration in frames: %s', self.duration_frames)

        return Ok(None)

    def remux(self, ffmpeg: str, on_progress: Callable[[int, float], None]) -> Result[Any, str]:
        logger.debug('Processing file: %s', self.file)

        outfile = self.file + '.trimmed.' + self.container.ext
        logger.debug('Output file: %s', outfile)

        ffmpeg = FFMpegRemuxer(ffmpeg, self.file)
        ffmpeg.set_format_metadata(self.metadata)
        ffmpeg.audio_as_is()
        ffmpeg.subtitles_as_is()
        for track in self.tracks:
            if isinstance(track, VideoTrack):
                if not track.is_h265:
                    logger.debug('Converting video track %s to HEVC', track)
                    ffmpeg.video_to_hevc(track, self.codec, self.preset, self.tune, self.profile)
                else:
                    logger.debug('Keeping video track %s as is', track)
                    ffmpeg.video_as_is(track)
            if track.keep:
                ffmpeg.keep_track(track)

        if (res := ffmpeg.process(outfile, on_progress)).is_err():
            logger.error('Failed to process file %s', self.file)
            try:
                os.remove(outfile)
            except Exception as _:
                pass

            return Err(f'Remuxer failed: {res.unwrap_err()}')

        logger.info('File %s processed successfully', self.file)

        # Backup original file
        bak = unique_bak_name(self.file)
        logger.info('Copy %s -> %s', self.file, bak)
        shutil.move(self.file, bak)

        # Replace original file with the trimmed one
        noext = os.path.splitext(self.file)[0]
        destfile = f'{noext}.{self.container.ext}'
        logger.info('Move %s -> %s', outfile, destfile)
        shutil.move(outfile, destfile)
        return Ok(None)

