import argparse

def build_reconcile_parser(subparsers):

    parser = subparsers.add_parser(
        "reconcile",
        help="Reconcile loopback resources and LVM state"
    )

    return parser

def reconcile(args):
    print("reconcile")