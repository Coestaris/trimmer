#!/usr/bin/env python3

#
# @file bak.py
# @date 08-02-2025
# @author Maxim Kurylko <vk_vm@ukr.net>
#

import argparse
import logging
import shutil
import os
import re

def setup_logging(args):
    class Fore:
        GREEN = "\x1b[32m"
        CYAN = "\x1b[36m"
        RED = "\x1b[31m"
        YELLOW = "\x1b[33m"
        RESET = "\x1b[39m"

    def get_format_string(colored: bool, details: bool) -> str:
        green = Fore.GREEN if colored else ""
        cyan = Fore.CYAN if colored else ""
        reset = Fore.RESET if colored else ""
        yellow = Fore.YELLOW if colored else ""

        if details:
            return f"{green}%(asctime)s{reset} - {cyan}%(name)s:%(funcName)s:%(lineno)d{reset} - {yellow}%(threadName)s{reset} - %(levelname)s - %(message)s"
        else:
            return f"{green}%(asctime)s{reset} - {cyan}%(name)s{reset} - {yellow}%(threadName)s{reset} - %(levelname)s - %(message)s"

    # Set up logging
    if not args.colorless:
        logging.addLevelName(logging.CRITICAL, f"{Fore.RED}{logging.getLevelName(logging.CRITICAL)}{Fore.RESET}")
        logging.addLevelName(logging.ERROR, f"{Fore.RED}{logging.getLevelName(logging.ERROR)}{Fore.RESET}")
        logging.addLevelName(logging.WARNING, f"{Fore.YELLOW}{logging.getLevelName(logging.WARNING)}{Fore.RESET}")
        logging.addLevelName(logging.INFO, f"{Fore.GREEN}{logging.getLevelName(logging.INFO)}{Fore.RESET}")
        logging.addLevelName(logging.DEBUG, f"{Fore.CYAN}{logging.getLevelName(logging.DEBUG)}{Fore.RESET}")

    logging.getLogger().setLevel(logging.getLevelName(args.log.upper()))
    # Output to file
    if args.log_file is not None:
        handler = logging.FileHandler(args.log_file)
    else:
        handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(get_format_string(not args.colorless, args.log == "debug")))
    logging.getLogger().addHandler(handler)


def main():
    parser = argparse.ArgumentParser(description='MKV Trimmer')
    parser.add_argument("--log-file", type=str, help="Log file")
    parser.add_argument("-l", "--log", type=str, default="info", choices=["debug", "info", "warning", "error", "critical"],
                        help="Log level. Note: 'debug' log level may print sensitive information,\n"
                             "produce a lot of output and program may run slower/incorectly")
    parser.add_argument("--colorless", action="store_true", help="Disable colored output")

    parser.add_argument('input', nargs='+', help='Input files or directories', type=str, action='append')

    args = parser.parse_args()

    setup_logging(args)

    # Flatten input
    args.input = [item for sublist in args.input for item in sublist]

    logging.info(args.input)

    files = []

    BAK_REGEX = re.compile(r'.*\.bak(\d+)?$')
    def process_token(input_token):
        # Do not use 'walk' because it freezes in some reason
        logging.debug(f'Processing token {input_token}')
        try:
            if os.path.isdir(input_token):
                for dir in os.listdir(input_token):
                    process_token(os.path.join(input_token, dir))
            elif os.path.isfile(input_token):
                if BAK_REGEX.match(input_token):
                    files.append(input_token)
            else:
                logging.error('Invalid input: %s', input_token)
                return
        except Exception as e:
            logging.warning('Error processing %s: %s', input_token, e)

    # Select .bak files
    for input_token in args.input:
        process_token(input_token)

    logging.info('Files to process (%d):', len(files))
    for file in files:
        logging.info(file)

    print('Select action:')
    print('  d - delete')
    print('  r - restore')
    print('  q - quit')
    action = input('Action: ').lower()
    if action == 'q':
        return
    elif action == 'd':
        for file in files:
            os.remove(file)
            logging.info('Removed %s', file)
    elif action == 'r':
        for file in files:
            # Find original file
            original_file = re.sub(r'\.bak(\d+)?$', '', file)
            if os.path.exists(original_file):
                logging.warning('Original file already exists: %s', original_file)
                os.remove(original_file)
            os.rename(file, original_file)
            logging.info('Restored %s', original_file)


if __name__ == '__main__':
    main()
