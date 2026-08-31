from ..utils.config import Config

from ..utils.resources.loopback import Loopback
from ..utils.resources.filter import LVMFilter

def build_reconcile_parser(subparsers):

    parser = subparsers.add_parser(
        "reconcile",
        help="Reconcile loopback resources and LVM state"
    )

    parser.set_defaults(func=reconcile)

    return parser

def reconcile(args):

    config = Config()

    resources = [
        Loopback(config.resource(name))
        for name in config.resource_names()
    ]

    for resource in resources:
        status = resource.check()

        if not status["image_exists"]:
            continue

        if not status["attached"]:
            resource.attach()

    lvm_filter = LVMFilter(config.lvm_config)
    lvm_filter.rebuild(resources)

    for resource in resources:

        loop_dev = resource.loop_device()

        if not loop_dev:
            continue
        
        resource.scan()
        resource.activate()