import argparse

def build_check_parser(subparsers):
    parser = subparsers.add_parser(
        "check",
        help="Check loopback resources"
    )

    parser.add_argument(
        "resource",
        nargs="?",
        choices=["cinder", "manila", "all"],
        default="all"
    )

    parser.set_defaults(func=check)

    return parser

def check(args):
    print("check")
    print(args.resource)
    