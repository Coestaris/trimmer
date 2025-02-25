#!/usr/bin/env python3

#
# @file __version__.py
# @date 24-02-2025
# @author Maxim Kurylko <vk_vm@ukr.net>
#

__version__ = "1.0.0"
__author__ = "Maxim Kurylko <vk_vm@ukr.net>"
__description__ = (
     f"This is a small frontend for the 'ffmpeg' utility (version: {__version__})\n"
     f"for batch processing of video files.\n"
     f"It allows you to select streams you want to keep (using\n"
     f"manual section or filters) and then transcode them to a new file.\n"
     f"By default frontend will try to re-encode video streams to H.265/HEVC codec\n"
     f"using 'libx265' or any available hardware encoder (e.g. 'hevc_nvenc' for NVIDIA GPUs).\n"
     f"For any questions, please contact the author: {__author__}"
)