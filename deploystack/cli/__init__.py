import argparse

from .parser import ColoredArgumentParser

from ..cmds.deploy.main import deploy
from ..cmds.launch.main import launch
from ..cmds.generate_config import generate_config
from ..cmds.image import image
from ..cmds.volume import volume

from ..cmds.deploy.main import init_parser as deploy_parser
from ..cmds.launch.main import init_parser as launch_parser
from ..cmds.generate_config import init_parser as generate_config_parser

from ..cmds.image import init_parser as image_config_parser

from ..cmds.volume import init_parser as volume_config_parser

def build_parser() -> argparse.ArgumentParser:

    parser = ColoredArgumentParser(
        description="DeployStack Utility"
    )

    subparsers = parser.add_subparsers(
        dest="command",
        metavar="<command>",
        required=True
    )

    deploy_parser(subparsers)
    launch_parser(subparsers)
    generate_config_parser(subparsers)
    image_config_parser(subparsers)
    volume_config_parser(subparsers)

    return parser

cmds = {
    "generate-config": generate_config,
    "deploy":          deploy,
    "launch":          launch,
    "image":           image,
    "volume":          volume 
}
