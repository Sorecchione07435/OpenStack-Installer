import argparse

from ..cmds.attach import build_attach_subparser
from ..cmds.check import build_check_parser
from ..cmds.detach import build_detach_parser
from ..cmds.filter import build_filter_parser
from ..cmds.reconcile import build_reconcile_parser
from ..cmds.start import build_start_parser
from ..cmds.status import build_status_parser
from ..cmds.stop import build_stop_parser

def build_parser() -> argparse.ArgumentParser:

    parser = argparse.ArgumentParser(
        prog="deploystack-loopback",
        description="Manage Deploystack LVM loopback storage"
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True
    )

    build_attach_subparser(subparsers)
    build_check_parser(subparsers)
    build_detach_parser(subparsers)
    build_filter_parser(subparsers)
    build_reconcile_parser(subparsers)
    build_start_parser(subparsers)
    build_status_parser(subparsers)
    build_stop_parser(subparsers)

    return parser