import argparse

def build_attach_subparser(subparsers):

    parser = subparsers.add_parser(
        "attach"
    )

    parser.add_argument(
        "resource",
        nargs="?",
        choices=["cinder" , "manila", "all"]
        default="all"
    )

    return parser

def attach(args):

