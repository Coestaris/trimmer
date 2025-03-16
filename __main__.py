#!/usr/bin/env python3

#
# @file __main__.py
# @date 23-02-2025
# @author Maxim Kurylko <vk_vm@ukr.net>
#

import argparse
import logging
import os
from typing import List

from PyQt5 import QtWidgets

from __version__ import __version__, __author__, __description__
from gui.backup_tool_dialog import BackupTool
from gui.colors import Colors
from gui.icons import render_svg, APP_ICON
from gui.main_window import MainWindow
from gui.series_tool_dialog import SeriesTool


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
            return f"{green}%(asctime)s{reset} - {cyan}%(name)s:%(funcName)s:%(lineno)d{reset} - %(levelname)s - %(message)s"
        else:
            return f"{green}%(asctime)s{reset} - {cyan}%(name)s{reset} - %(levelname)s - %(message)s"

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

def run_gui(backup_tool: bool, series_tool: bool, start_files: List[str]) -> int:
    app = QtWidgets.QApplication([])
    Colors.set_dark_mode(app.palette().window().color().value() <
                         app.palette().windowText().color().value())
    app.setWindowIcon(render_svg(APP_ICON, 32, Colors.get_icon_color()))

    if backup_tool:
        gui = BackupTool(start_files)
    elif series_tool:
        gui = SeriesTool(start_files)
    else:
        gui = MainWindow(start_files)

    gui.show()
    return app.exec_()

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter, prog=os.path.basename(__file__))
    parser.description = __description__
    parser.add_argument("--log-file", type=str, help="Log file")
    parser.add_argument("-l", "--log", type=str, default="info", choices=["debug", "info", "warning", "error", "critical"],
                        help="Log level. Note: 'debug' log level may print sensitive information,\n" 
                             "produce a lot of output and program may run slower/incorectly")
    parser.add_argument("--colorless", action="store_true", help="Disable colored output")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--backup-tool", action="store_true", help="Run backup tool without Main Window")
    group.add_argument("--series-tool", action="store_true", help="Run series tool without Main Window")
    parser.add_argument("input", help="Path to the input files", nargs="*", action="append", default=[])
    args = parser.parse_args()

    # Flatten the list of lists
    if args.input is not None and len(args.input) > 0:
        args.input = [item for sublist in args.input for item in sublist]

    setup_logging(args)

    logging.info("Trimmer. Version: %s", __version__)

    return run_gui(args.backup_tool, args.series_tool, args.input)

if __name__ == '__main__':
    exit(main())
