import argparse
import ipaddress
import os
import shutil
import sys
import uuid

from .utils.core import colors
from .cli import build_parser, cmds

def print_banner():
    print(f"{colors.BRIGHT_BLUE}Welcome to DeployStack Utility{colors.RESET}\n")

def main():
    print_banner()

    parser = build_parser()
    # Only parse known args to avoid automatic error exit
    args = parser.parse_args()

    if args.command is None:
        print(f"{colors.YELLOW}No command provided. Available commands:{colors.RESET}\n")
        parser.print_help()
        print(f"\nTip: Run '{colors.BRIGHT_BLUE}deploystack <command> --help{colors.RESET}' for detailed usage of each command.")
        sys.exit(1)

    cmds[args.command](parser, args)