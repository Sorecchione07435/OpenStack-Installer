import argparse

def build_start_parser(subparsers):

    parser = subparsers.add_parser(
        "start",
        help="Start a loopback resource"
    )

    parser.add_argument(
        "resource",
        choices=["cinder", "manila", "all"],
        default="all",
        help="Resource to start"
    )

    parser.set_defaults(func=start)

    return parser

def start(args):
    print("start")
    print(args.resource)