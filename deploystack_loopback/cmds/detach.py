import argparse

from ..utils.config import Config
from ..utils.resources.loopback import Loopback

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

    parser.set_defaults(func=detach)

    return parser

def detach(args):

    config = Config()

    resource = Loopback(config.resource(args.resource))

    resource.detach()