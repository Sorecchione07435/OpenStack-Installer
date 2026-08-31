
from ..utils.config import Config
from ..utils.resources.loopback import Loopback
from ..utils.resources.filter import LVMFilter

def build_stop_parser(subparsers):

    parser = subparsers.add_parser(
        "stop",
        help="Stop a loopback resource"
    )

    parser.add_argument(
        "resource",
        choices=["cinder", "manila", "all"],
        default="all",
        help="Resource to stop"
    )

    parser.set_defaults(func=stop)

    return parser

def stop(args):

    config = Config()

    resource = Loopback(config.resource(args.resource))

    resource.deactivate()

    status = resource.check()

    if status["attached"]:

        loop_dev = status["loop_device"]

        lvm_filter = LVMFilter(config.lvm_config)
        lvm_filter.remove(loop_dev)

        resource.detach()

    print(f"Stopped {args.resource}")