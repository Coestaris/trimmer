#!/usr/bin/env python3

#
# @file track.py
# @date 26-02-2025
# @author Maxim Kurylko <vk_vm@ukr.net>
#

class Track:
    def __init__(self, index: int, codec: str, language: str, title: str, duration: float):
        self.__index = index
        self.__codec = codec
        self.__language = language
        self.__title = title
        self.__duration = duration
        self.__keep = True

    @property
    def index(self) -> int:
        return self.__index

    @property
    def codec(self) -> str:
        return self.__codec

    @property
    def language(self) -> str:
        return self.__language

    @language.setter
    def language(self, language: str):
        self.__language = language

    @property
    def title(self) -> str:
        return self.__title

    @title.setter
    def title(self, title: str):
        self.__title = title

    @property
    def duration(self) -> float:
        return self.__duration

    @property
    def keep(self) -> bool:
        return self.__keep

    @keep.setter
    def keep(self, keep: bool):
        self.__keep = keep

    def __str__(self):
        return f'{self.index}; codec={self.codec}, lang={self.language}, title=\"{self.title}\", duration={self.duration:.2f}'

    def __repr__(self):
        return self.__str__()

class VideoTrack(Track):
    def __init__(self, index: int, codec: str, language: str, title: str, duration: float, frame_rate: float):
        super().__init__(index, codec, language, title, duration)
        self.__frame_rate = frame_rate

    @property
    def frame_rate(self) -> float:
        return self.__frame_rate

    @property
    def is_h265(self) -> bool:
        return 'hevc' in self.codec or 'h265' in self.codec

    def __str__(self):
        return f'VideoTrack({super().__str__()}, fps={self.frame_rate:.2f})'

class AudioTrack(Track):
    def __init__(self, index: int, codec: str, language: str, title: str, duration: float, channels: int):
        super().__init__(index, codec, language, title, duration)
        self.__channels = channels

    @property
    def channels(self) -> int:
        return self.__channels

    def __str__(self):
        return f'AudioTrack({super().__str__()}, channels={self.channels})'

class SubtitleTrack(Track):
    def __init__(self, index: int, codec: str, language: str, title: str, duration: float):
        super().__init__(index, codec, language, title, duration)

    def __str__(self):
        return f'SubtitleTrack({super().__str__()})'

class AttachmentTrack(Track):
    def __init__(self, index: int, codec: str, title: str):
        super().__init__(index, codec, 'und', title, 0)

    def __str__(self):
        return f'AttachmentTrack({super().__str__()})'