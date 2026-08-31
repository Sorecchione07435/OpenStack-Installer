import argparse

from ..utils.config import Config
from ..utils.resources.loopback import Loopback

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

    config = Config()
    resource = Loopback(config.resource(args.resource))

    status = resource.check()

    print(f"Resource: {args.resource}")
    print(f"Image: {status['image']}")
    print(f"Image exists: {status['image_exists']}")
    print(f"Attached: {status['attached']}")
    print(f"Loop device: {status['loop_device'] or '-'}")