#!/usr/bin/env python3
import os
import shutil
from typing import Callable

#
# @file mkv_file.py
# @date 24-02-2025
# @author Maxim Kurylko <kurylko.m@ajax.systems>
#

from ffmpeg import VideoTrack, get_video_tracks, FFMpegRemuxer
import logging

from utils import unique_bak_name

logger = logging.getLogger(__name__)

class MKVFile:
    def __init__(self, file: str):
        self.file = file
        self.tracks = []
        self.duration_frames = None
        self.duration_seconds = None

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
        else:
            self.duration_seconds = duration_sec
            self.duration_frames = int(duration_sec * frame_rate)

    def parse(self, ffprobe: str) -> bool:
        self.tracks = get_video_tracks(ffprobe, self.file)
        if self.tracks is None:
            logger.error('Failed to get video tracks of file %s', self.file)
            return False
        logger.debug('Tracks: %s', self.tracks)

        self.__estimate_duration()
        logger.debug('Duration in frames: %s', self.duration_frames)
        pass

    def remux(self,
              ffmpeg: str,
              preset: str,
              encoder: str,
              on_progress: Callable[[int, float], None]) -> bool:
        logging.debug('Processing file: %s', self.file)

        outfile = self.file + '.trimmed.mkv'
        logging.debug('Output file: %s', outfile)

        ffmpeg = FFMpegRemuxer(ffmpeg, self.file)
        ffmpeg.audio_as_is()
        ffmpeg.subtitles_as_is()
        ffmpeg.keep_all_attachments()
        for track in self.tracks:
            if isinstance(track, VideoTrack):
                if not track.is_h265():
                    logging.debug('Converting video track %s to HEVC', track)
                    ffmpeg.video_to_hevc(track, preset, encoder)
                else:
                    logging.debug('Keeping video track %s as is', track)
                    ffmpeg.video_as_is(track)
            if track.keep:
                ffmpeg.keep_track(track)

        if not ffmpeg.process(outfile, on_progress):
            logging.error('Failed to process file %s', self.file)
            os.remove(outfile)
            return False

        logging.info('File %s processed successfully', self.file)

        # Backup original file
        bak = unique_bak_name(self.file)
        logging.info('Backing up original file to %s', bak)
        shutil.move(self.file, bak)

        # Replace original file with the trimmed one
        logging.info('Replacing original file with the trimmed one')
        shutil.move(outfile, self.file)
        return True

