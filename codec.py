#!/usr/bin/env python3

#
# @file codec.py
# @date 26-02-2025
# @author Maxim Kurylko <vk_vm@ukr.net>
#

from typing import List
from result import Result, Ok, Err
import logging

logger = logging.getLogger(__name__)


# TODO: Maybe get this from ffmpeg?
# Actually there's ffmpeg -h encoder=<...> that can be used to get the
# list of presets, tunes and profiles. But in some reason, libx265 doesn't
# show them all.
class Codec:
    def __init__(self, name: str,
                 presets: List[str],
                 preferred_preset: str,
                 tunes: List[str],
                 preferred_tune: str,
                 profiles: List[str],
                 preferred_profile: str):
        self.__name = name
        self.__presets = presets
        self.__preferred_preset = preferred_preset
        self.__tunes = tunes
        self.__preferred_tune = preferred_tune
        self.__profiles = profiles
        self.__preferred_profile = preferred_profile

    @property
    def name(self) -> str:
        return self.__name

    @property
    def presets(self) -> List[str]:
        return self.__presets

    @property
    def preferred_preset(self) -> str:
        return self.__preferred_preset

    @property
    def tunes(self) -> List[str]:
        return self.__tunes

    @property
    def preferred_tune(self) -> str:
        return self.__preferred_tune

    @property
    def profiles(self) -> List[str]:
        return self.__profiles

    @property
    def preferred_profile(self) -> str:
        return self.__preferred_profile

    def __str__(self):
        return f'Codec({self.name})'

    def __repr__(self):
        return self.__str__()

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

HEVC_VIDEOTOOLBOX_CODEC = Codec(
    'hevc_videotoolbox',
    [
        'default',
        'slow',
        'medium',
        'fast',
        'faster',
        'fastest',
    ],
    'medium',
    [
        'default',
    ],
    'default',
    [
        'main',
        'main10',
    ],
    'main'
)

KNOWN_CODECS = [
    LIBX265_CODEC,
    HEVC_NVENC_CODEC,
    HEVC_VIDEOTOOLBOX_CODEC,
]

def prefer_hevc_codec(codecs: List[str], gpu_name: str) -> Result[Codec, str]:
    if 'nvidia' in gpu_name.lower() and HEVC_NVENC_CODEC in codecs:
        logger.info("Preferred HEVC codec: %s", HEVC_NVENC_CODEC)
        return Ok(HEVC_NVENC_CODEC)

    # On Apple Silicon, libx265 seems to faster than hevc_videotoolbox
    # So prefer libx265
    if LIBX265_CODEC in codecs:
        logger.info("Preferred HEVC codec: %s", LIBX265_CODEC)
        return Ok(LIBX265_CODEC)

    return Err("Cannot find supported HEVC codec")
