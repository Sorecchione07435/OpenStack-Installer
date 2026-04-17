import argparse
import ipaddress
import os
import shutil
import sys

from .deploy import deploy
from .utils.core import colors
from .utils.network.net_utils import get_active_interface, get_network_info, get_default_interface_ip
from .config_manager import generate_config_file, config_openstack, get_config_file_path
from .utils.tasks.check_deployment import check_deployment, check_env_variables
from .utils.tasks.launch_instance import launch

def print_banner():
    print(f"{colors.BRIGHT_BLUE}Welcome to Debian OpenStack Installer Utility{colors.RESET}\n")


def build_parser() -> argparse.ArgumentParser:

    global parser
    global launch_p

    parser = argparse.ArgumentParser(
        description="Debian OpenStack Installer Utility"
    )

    sub = parser.add_subparsers(
        dest="command",
        metavar="<command>",
        required=True
    )

    # deploy-allinone
    deploy_allinone_p = sub.add_parser(
        "deploy-allinone",
        help="Deploy a full OpenStack all-in-one"
    )

    deploy_allinone_p.add_argument(
        "--lvm-image-size-in-gb",
        type=int,
        default=5,
        help="Size of the Cinder LVM image in GB"
    )

    # deploy
    deploy_p = sub.add_parser(
        "deploy",
        help="Deploy OpenStack from a config file"
    )
    deploy_p.add_argument(
        "config_file",
        help="Path to the configuration file"
    )

    # generate-config
    gen_p = sub.add_parser(
        "generate-config",
        help="Generate a template configuration file"
    )
    gen_p.add_argument(
        "file",
        help="Output path (file or directory)"
    )

    # launch
    launch_p = sub.add_parser(
        "launch",
        help="Launch an OpenStack instance"
    )

    launch_p.add_argument("--name", default="cirros-instance")
    launch_p.add_argument("--image", default="cirros")
    launch_p.add_argument("--flavor", default="m1.tiny")
    launch_p.add_argument("--network", default="test")
    launch_p.add_argument("--password", default="")

    return parser

def cmd_generate_config(args):
    src_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "templates/conf_template.yaml")
    dst_file = os.path.join(args.file, "templates/conf_template.yaml") if os.path.isdir(args.file) else args.file
    shutil.copy(src_file, dst_file)
    print(f"Configuration file generated in '{dst_file}'")


def cmd_deploy(args):
    deploy(args.config_file)


def cmd_deploy_allinone(_args):

    size = _args.lvm_image_size_in_gb

    if size is not None and size <= 0:
        print(f"{colors.RED}Invalid LVM image size specified. It must be positive.{colors.RESET}")
        sys.exit(1)

    generate_config_file()

    config_openstack(size if size is not None else 5)

    deploy(get_config_file_path())


def cmd_launch(args):

    if args.command is None:
        parser.print_help()
        launch_p.exit()

    base_check = check_deployment(include_endpoints=False)
    if not base_check.ok:
        print(f"{colors.RED}OpenStack is not deployed yet.{colors.RESET}\n")
        print(f"{colors.YELLOW}  • Run 'deploy-allinone' for a full automated deployment{colors.RESET}")
        print(f"{colors.YELLOW}  • Or run 'deploy <config_file>' with a custom config{colors.RESET}\n")
        return

    try:
        check_env_variables()
    except RuntimeError:
        print(f"{colors.YELLOW}Shell is not authenticated. Source the environment file first:{colors.RESET}\n")
        print(f"  {colors.YELLOW}source /root/admin-openrc.sh{colors.RESET}  or")
        print(f"  {colors.GREEN}source /root/demo-openrc.sh{colors.RESET}\n")
        return

    endpoint_check = check_deployment(include_endpoints=True)
    if not endpoint_check.ok:
        print(f"{colors.RED}OpenStack is deployed but services are not fully operational:{colors.RESET}")
        print(endpoint_check)
        return

    launch(name=args.name, image=args.image, flavor=args.flavor, network=args.network, password=args.password)

    


COMMANDS = {
    "generate-config": cmd_generate_config,
    "deploy":          cmd_deploy,
    "deploy-allinone": cmd_deploy_allinone,
    "launch":          cmd_launch,
}


def main():
    print_banner()

    if os.geteuid() != 0:
        print(f"{colors.RED}This utility must be run as root.{colors.RESET}")
        print(f"{colors.YELLOW}Try: sudo <command>{colors.RESET}\n")
        sys.exit(1)

    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        print(f"{colors.YELLOW}No command provided. Available commands:{colors.RESET}\n")
        parser.print_help()
        parser.exit()

    COMMANDS[args.command](args)