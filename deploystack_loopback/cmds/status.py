from .check import print_status

from ..utils.config import Config
from ..utils.resources.loopback import Loopback

def build_status_parser(subparsers):

    parser = subparsers.add_parser(
        "status",
        help="Show loopback resources status"
    )

    parser.add_argument(
        "resource",
        nargs="?",
        choices=["cinder", "manila"],
        default=None,
        help="Resource to show"
    )

    parser.set_defaults(func=status)

    return parser

def status(args):

    config = Config()

    if args.resource:
        resources = {
            args.resource: Loopback(config.resource(args.resource))
        }
    else:
        resources = {
            name: Loopback(config.resource(name))
            for name in config.resource_names()
        }

    for name, resource in resources.items():
        status = resource.check()

        print_status(name, status)

