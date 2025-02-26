#!/usr/bin/env python3

#
# @file colors.py
# @date 26-02-2025
# @author Maxim Kurylko <vk_vm@ukr.net>
#

import logging
from typing import Dict, List

from track import AttachmentTrack, VideoTrack, AudioTrack, SubtitleTrack

logger = logging.getLogger(__name__)

class Colors:
    is_dark = False

    @staticmethod
    def set_dark_mode(dark: bool):
        logger.info('Dark mode: %s', dark)
        Colors.is_dark = dark

    @staticmethod
    def get_type_colors() -> Dict[type, str]:
        if Colors.is_dark:
            return {
                # Dark-like colors
                VideoTrack: '#1c4d1e',
                AudioTrack: '#856024',
                SubtitleTrack: '#6b1414',
                AttachmentTrack: '#424242'
            }
        else:
            return {
                # Pale white-like colors
                VideoTrack: '#CEEAD6',
                AudioTrack: '#FEEFC3',
                SubtitleTrack: '#FAD2CF',
                AttachmentTrack: '#D4E6F1'
            }

    @staticmethod
    def get_language_colors() -> List[str]:
        if Colors.is_dark:
            return [
                '#1c4d1e', # Green
                '#856024', # Brown
                '#6b1414', # Red
                '#424242', # Dark gray
                '#455A64', # Blue
            ]
        else:
            return [
                '#CEEAD6', # Green
                '#D4E6F1', # Blue
                '#E2E2E2', # Gray
                '#FAD2CF', # Red
                '#FEEFC3', # Yellow
                '#F5F5F5', # Light gray
                '#F8F8F8', # Lighter gray
                '#F0F0F0', # Lightest gray
            ]

    @staticmethod
    def get_status_colors() -> Dict[str, str]:
        if Colors.is_dark:
            return {
                'pending': '#424242',
                'working': '#455A64',
                'done': '#1c4d1e',
                'error': '#856024'
            }
        else:
            return {
                'pending': '#F5F5F5',
                'working': '#D4E6F1',
                'done': '#CEEAD6',
                'error': '#FEEFC3'
            }

    @staticmethod
    def get_icon_color() -> str:
        if Colors.is_dark:
            # Light gray
            return '#F5F5F5'
        else:
            return '#000000'
