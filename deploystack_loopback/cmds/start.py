from ..utils.config import Config
from ..utils.resources.loopback import Loopback
from ..utils.resources.filter import LVMFilter

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

    config = Config()

    resource = Loopback(config.resource(args.resource))

    loop_dev = resource.attach()

    lvm_filter = LVMFilter(config.lvm_config)
    lvm_filter.add(loop_dev)

    resource.scan()
    resource.activate()

    print(f"Started {args.resource}")