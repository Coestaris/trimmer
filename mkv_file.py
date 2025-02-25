#!/usr/bin/env python3
from result import Result, Err, Ok

#
# @file mkv_file.py
# @date 24-02-2025
# @author Maxim Kurylko <kurylko.m@ajax.systems>
#

from ffmpeg import VideoTrack, get_video_tracks, FFMpegRemuxer, Codec
import logging
import os
import shutil
from typing import Callable, Any
from utils import unique_bak_name

logger = logging.getLogger(__name__)

class MKVFile:
    def __init__(self, file: str, codec: Codec):
        self.file = file
        self.tracks = []
        self.duration_frames = None
        self.duration_seconds = None

        self.codec = codec
        self.preset = codec.preferred_preset
        self.tune = codec.preferred_tune
        self.profile = codec.preferred_profile

    def __estimate_duration(self):
        durations_sec = []
        fps = []

        for track in self.tracks:
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
            self.duration_seconds = 0
            self.duration_frames = 0
            self.fps = 0
        else:
            self.duration_seconds = duration_sec
            self.duration_frames = int(duration_sec * frame_rate)
            self.fps = frame_rate

    def parse(self, ffprobe: str) -> Result[Any, str]:
        self.tracks = get_video_tracks(ffprobe, self.file)
        if self.tracks.is_err():
            return Err(f"Unable to get list of tracks: {self.tracks.unwrap_err()}")
        self.tracks = self.tracks.unwrap()

        logger.debug('Tracks: %s', self.tracks)

        self.__estimate_duration()
        logger.debug('Duration in frames: %s', self.duration_frames)
        return Ok(None)

    def remux(self, ffmpeg: str, on_progress: Callable[[int, float], None]) -> Result[Any, str]:
        logger.debug('Processing file: %s', self.file)

        # Imitate work
        # import time
        # time.sleep(5)
        # return Ok(None)

        outfile = self.file + '.trimmed.mkv'
        logger.debug('Output file: %s', outfile)

        ffmpeg = FFMpegRemuxer(ffmpeg, self.file)
        ffmpeg.audio_as_is()
        ffmpeg.subtitles_as_is()
        ffmpeg.keep_all_attachments()
        for track in self.tracks:
            if isinstance(track, VideoTrack):
                if not track.is_h265():
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
            except Exception as e:
                pass

            return Err(f'Remuxer failed: {res.unwrap_err()}')

        logger.info('File %s processed successfully', self.file)

        # Backup original file
        bak = unique_bak_name(self.file)
        logger.info('Backing up original file to %s', bak)
        shutil.move(self.file, bak)

        # Replace original file with the trimmed one
        logger.info('Replacing original file with the trimmed one')
        shutil.move(outfile, self.file)
        return Ok(None)

