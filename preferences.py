#!/usr/bin/env python3

#
# @file preferences.py
# @date 25-02-2025
# @author Maxim Kurylko <vk_vm@ukr.net>
#

import logging
from typing import List
from result import Result, Ok, Err
from ffmpeg import HEVC_NVENC_CODEC, LIBX265_CODEC, Codec

logger = logging.getLogger(__name__)

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
