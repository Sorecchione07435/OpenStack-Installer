import argparse

def build_detach_parser(subparsers):
    parser = subparsers.add_parser(
        "detach",
        help="Detach a loopback resource"
    )

    parser.add_argument(
        "resource",
        choices=["cinder", "manila"],
        help="Resource to detach"
    )

    return parser

def detach(args):
    print("detach")
    print(args.resource)