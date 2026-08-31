import argparse

from ..utils.config import Config
from ..utils.resources.loopback import Loopback

def print_status(name, status):

    print(f"Resource: {name}")
    print(f"  Image: {status['image']}")
    print(f"  Image exists: {status['image_exists']}")
    print(f"  Attached: {status['attached']}")
    print(f"  Loop device: {status['loop_device'] or '-'}")

def build_check_parser(subparsers):
    parser = subparsers.add_parser(
        "check",
        help="Check loopback resources"
    )

    parser.add_argument(
        "resource",
        nargs="?",
        choices=["cinder", "manila"],
        default=None
    )

    parser.set_defaults(func=check)

    return parser

def check(args):

    config = Config()

    if args.resource is None:
        for name in ("cinder", "manila"):
            resource = Loopback(config.resource(name))
            status = resource.check()

            print_status(name, status)

        return
            
    resource = Loopback(config.resource(args.resource))
    status = resource.check()

    print_status(args.resource, status)