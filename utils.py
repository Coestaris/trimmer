#!/usr/bin/env python3

#
# @file utils.py
# @date 23-02-2025
# @author Maxim Kurylko <vk_vm@ukr.net>
#

import os
import platform
import logging
import re
import subprocess
import time
from typing import List, Tuple

from result import Result, Err, Ok

logger = logging.getLogger(__name__)

def run(args: List[str]) -> Tuple[int, str]:
    logger.debug('Running command: [%s]', ' '.join(args))
    process = subprocess.Popen(args,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               universal_newlines=True,
                               encoding='utf-8')
    stdout, stderr = process.communicate()
    output = stdout + stderr
    logger.debug('code: %d, output: [%s]', process.returncode, output)
    return process.returncode, output

def unique_bak_name(file):
    i = 0
    while True:
        new_file = f'{file}.bak{i}'
        if not os.path.exists(new_file):
            return new_file
        i += 1

def get_gpu_name() -> Result[str, str]:
    if platform.system() == 'Windows':
        import wmi

        try:
            w = wmi.WMI(namespace="root\\CIMV2")
            for gpu in w.Win32_VideoController():
                return Ok(gpu.Name)
        except Exception as e:
            return Err(f"Failed to get GPU name: {e}")

        return Err("Failed to get GPU: No GPU found")

    elif platform.system() == 'Linux':
        code, output = run(['lspci', '-v'])
        regex = re.compile(r'(?P<device>\d+:\d+.\d+).*?(?P<description>[\w\s:\[\]]+)')
        for line in output.splitlines():
            match = regex.match(line)
            if match:
                device = match.group('device')
                description = match.group('description')
                if 'VGA' in description or '3D controller' in description:
                    return Ok(description.replace('VGA compatible controller: ', '').strip())

        return Err("Failed to get GPU: No GPU found")

    else:
        return Err("Failed to get GPU: Unsupported OS")

def pretty_duration(seconds: float) -> str:
    if seconds == 0:
        return "unknown"

    if seconds < 120:
        return f'{int(seconds):02} seconds'
    elif seconds < 3600:
        minutes, seconds = divmod(seconds, 60)
        return f'{int(minutes):02}:{int(seconds):02}'
    else:
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        return f'{int(hours):02}:{int(minutes):02}:{int(seconds):02}'

def pretty_size(size: int) -> str:
    if size < 1024:
        return f'{size} B'
    elif size < 1024 * 1024:
        return f'{size / 1024:.2f} KB'
    elif size < 1024 * 1024 * 1024:
        return f'{size / 1024 / 1024:.2f} MB'
    else:
        return f'{size / 1024 / 1024 / 1024:.2f} GB'

def pretty_errno(errno: int) -> str:
    if errno == 0:
        return "success"
    return os.strerror(errno)

class ETACalculator:
    def __init__(self, start_time: float, start_percent: float):
        self.reset(start_time, start_percent)

    def reset(self, start_time: float, start_percent: float):
        self.start_time = start_time
        self.prev_time = start_time
        self.percent = start_percent
        self.prev_percent = start_percent
        self.eta = 0

    def feed(self, percent: float):
        current_time = time.time()
        time_diff = current_time - self.prev_time

        if time_diff == 0 or percent <= self.prev_percent:
            return  # Avoid division by zero or incorrect values

        progress_diff = percent - self.prev_percent
        speed = progress_diff / time_diff  # Percentage per second

        if speed > 0:
            new_eta = (100 - percent) / speed  # Time remaining in seconds
            if self.eta == 0:
                self.eta = new_eta
            else:
                # Smooth ETA using an exponential moving average
                self.eta = 0.9 * self.eta + 0.1 * new_eta

        self.prev_time = current_time
        self.prev_percent = percent

    def get(self) -> float:
        return self.eta
