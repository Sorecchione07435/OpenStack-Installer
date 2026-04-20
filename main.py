import argparse
import ipaddress
import os
import shutil
import sys
import uuid

from .deploy import deploy
from .utils.core import colors
from .utils.network.net_utils import get_active_interface, get_network_info, get_default_interface_ip
from .config_manager import generate_config_file, config_openstack
from .utils.tasks.check_deployment import check_deployment, check_env_variables, MARKER_FILE
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

    # deploy
    deploy_p = sub.add_parser(
        "deploy",
        help="Start the OpenStack Deployment"
    )

    deploy_p.add_argument(
        "--allinone",
        action="store_true",
        help="Runs a complete OpenStack deployment using an automatically generated configuration."
    )

    deploy_p.add_argument(
        "--config-file",
        help="Path to the configuration file"
    )

    deploy_p.add_argument(
        "--install-cinder",
        type=str,
        default="yes",
        dest="install_cinder",
        help="Choosing whether to install the Cinder (Block Storage) service"
    )

    deploy_p.add_argument(
        "--lvm-image-size-in-gb",
        type=int,
        default=5,
        help="Size of the Cinder LVM image in GB"
    )

    # generate-config
    parser.add_argument(
        "--generate-config",
        help="Generate a template configuration file",
        metavar="FILE"
    )

    # launch
    launch_p = sub.add_parser(
        "launch",
        help="Launch an OpenStack instance"
    )

    launch_p.add_argument(
        "--name",
        default=f"instance-{uuid.uuid4().hex[:8]}",
        help="Name of the instance to launch. Defaults to a random generic instance name."
        )
    
    launch_p.add_argument(
        "--image",
        default="cirros",
        help="Name of the image to use for the instance. Defaults to 'cirros'."
    )
    launch_p.add_argument(
        "--flavor",
        default="m1.tiny",
        help="Flavor (size) of the instance. Defaults to 'm1.tiny'."
    )
    launch_p.add_argument(
        "--network",
        default="internal",
        help="Network to attach the instance to. Defaults to 'internal'."
    )
    launch_p.add_argument(
        "--password",
        default="",
        help="Password for the admin instance user."
    )

    return parser

def cmd_generate_config(args):
    src_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "templates/conf_template.yaml")
    dst_file = os.path.join(args.file, "templates/conf_template.yaml") if os.path.isdir(args.file) else args.file
    shutil.copy(src_file, dst_file)
    print(f"Configuration file generated in '{dst_file}'")

def cmd_deploy(args):

    if args.allinone:

        config_file_path = generate_config_file()

        if args.install_cinder == "yes":
            size = args.lvm_image_size_in_gb
            config_openstack("yes", config_file_path, size if size is not None else 5)
        else:
            config_openstack("no", config_file_path, None)

        deploy(config_file_path)

    elif args.config_file:
        deploy(args.config_file)
    else:
        print(f"{colors.RED}Error: you must specify either --allinone or --config-file.{colors.RESET}\n")
        print("To view all available arguments for the openstack install deploy command, run: 'openstack_installer deploy --help'")
              
        sys.exit(1)

def cmd_launch(args):

    if args.command is None:
        parser.print_help()
        launch_p.exit()

    base_check = check_deployment(include_endpoints=False)
    if not base_check.ok or not os.path.exists(MARKER_FILE):
        print(f"{colors.RED}OpenStack is not deployed yet.{colors.RESET}\n")
        print(f"{colors.YELLOW}  • Run 'deploy --allinone' for a full automated deployment{colors.RESET}")
        print(f"{colors.YELLOW}  • Or run 'deploy --config-file <config_file>' with a custom config{colors.RESET}\n")
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
    "--generate-config": cmd_generate_config,
    "deploy":          cmd_deploy,
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