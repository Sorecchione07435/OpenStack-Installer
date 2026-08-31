import os
import sys

from .utils import colors
from .cli import build_parser

def main():

    if os.geteuid() != 0:
        print(f"{colors.RED}This utility must be run as root.{colors.RESET}")
        sys.exit(1)

    parser = build_parser()
    args = parser.parse_args()

    args.func(args)