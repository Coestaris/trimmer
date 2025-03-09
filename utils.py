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
import shutil
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
                           creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == 'Windows' else 0,
                           encoding='utf-8')
    stdout, stderr = process.communicate()
    output = stdout + stderr
    logger.debug('code: %d, output: [%s]', process.returncode, output)
    return process.returncode, output

def find_ffmpeg() -> Result[str, str]:
    ffmpeg = shutil.which('ffmpeg')
    if ffmpeg is None:
        return Err('ffmpeg not found')

    return Ok(ffmpeg)

def find_ffprobe() -> Result[str, str]:
    ffprobe = shutil.which('ffprobe')
    if ffprobe is None:
        return Err('ffprobe not found')

    return Ok(ffprobe)

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

    elif platform.system() == 'Darwin':
        code, output = run(['system_profiler', 'SPDisplaysDataType'])
        regex = re.compile(r'^\s+Chipset Model: (?P<model>.+)$')
        for line in output.splitlines():
            match = regex.match(line)
            if match:
                return Ok(match.group('model'))

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

def pretty_date(timestamp: float) -> str:
    return time.strftime('%d-%m-%Y %H:%M:%S', time.gmtime(timestamp))

class ETACalculator:
    def __init__(self, start_time: float, start_percent: float):
        self.reset(start_time, start_percent)

    def reset(self, start_time: float, start_percent: float):
        self.start_time = start_time
        self.prev_time = start_time
        self.prev_percent = start_percent
        self.eta = 0
        self.speed_avg = None  # Moving average of speed
        self.alpha = 0.2  # Higher initial smoothing for quick adaptation
        self.update_count = 0  # Track number of updates

    def feed(self, percent: float):
        current_time = time.time()
        time_diff = current_time - self.prev_time

        if time_diff <= 0 or percent <= self.prev_percent:
            return  # Avoid division by zero or incorrect values

        progress_diff = percent - self.prev_percent
        instant_speed = progress_diff / time_diff  # Percentage per second

        # Smooth the speed using exponential moving average
        if self.speed_avg is None:
            self.speed_avg = instant_speed  # Initialize on first valid speed
        else:
            self.speed_avg = (1 - self.alpha) * self.speed_avg + self.alpha * instant_speed

        # Reduce alpha over time for more stability after initial phase
        self.update_count += 1
        self.alpha = max(0.05, 0.2 / (1 + 0.1 * self.update_count))  # Adaptive smoothing

        if self.speed_avg > 0:
            new_eta = (100 - percent) / self.speed_avg  # Estimated time remaining

            # Ignore initial unreasonably high ETAs
            if new_eta > 10 * (current_time - self.start_time):  # Cap based on elapsed time
                new_eta = self.eta if self.eta > 0 else 0  # Use previous estimate if available

            if self.eta == 0:
                self.eta = new_eta
            else:
                self.eta = (1 - self.alpha) * self.eta + self.alpha * new_eta  # Smooth ETA

        self.prev_time = current_time
        self.prev_percent = percent

    def get(self) -> float:
        return self.eta

def suspend_os():
    if platform.system() == 'Windows':
        run(['rundll32.exe', 'powrprof.dll,SetSuspendState', '0,1,0'])
    elif platform.system() == 'Linux':
        run(['systemctl', 'suspend'])
    elif platform.system() == 'Darwin':
        run(['osascript', '-e', 'tell application "System Events" to sleep'])
    else:
        logger.error('Cannot suspend OS: unsupported OS')
