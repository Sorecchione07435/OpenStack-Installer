from ..utils.config import Config
from ..utils.resources.loopback import Loopback

def build_attach_subparser(subparsers):

    parser = subparsers.add_parser(
        "attach"
    )

    parser.add_argument(
        "resource",
        nargs="?",
        choices=["cinder", "manila", "all"],
        default="all"
    )

    parser.set_defaults(func=attach)

    return parser

def attach(args):

    config = Config()
    resource = Loopback(config.resource(args.resource))

    loop_dev = resource.attach()
    
    print(f"Attached {resource.image} to {loop_dev}")
