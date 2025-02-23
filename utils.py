#!/usr/bin/env python3

#
# @file utils.py
# @date 23-02-2025
# @author Maxim Kurylko <vk_vm@ukr.net>
#

import platform
import logging
import subprocess
from typing import List, Tuple

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

def get_gpu_name():
    if platform.system() == 'Windows':
        import wmi
        w = wmi.WMI(namespace="root\\CIMV2")
        for gpu in w.Win32_VideoController():
            return gpu.Name
    else:
        raise NotImplementedError('Only Windows is supported')