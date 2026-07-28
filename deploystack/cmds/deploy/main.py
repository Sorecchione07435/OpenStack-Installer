import argparse
import sys
import os

from ...utils.core import colors

from .generator import generate_config_file, config_openstack
from .runner import deploy as runner_deploy

def init_parser(subparsers):
     
    parser = subparsers.add_parser(
    "deploy",
    help="Start the OpenStack Deployment on the current node"
)

    general_options = parser.add_argument_group("General Options")
    group = general_options.add_mutually_exclusive_group(required=True)

    manila = parser.add_argument_group("Manila Options")
    cinder = parser.add_argument_group("Cinder Options")

    group.add_argument(
        "--allinone",
        action="store_true",
        help="Runs a complete OpenStack deployment using an automatically generated configuration."
    )

    group.add_argument(
        "--config-file",
        help="Path to the configuration file"
    )

    cinder.add_argument(
        "--install-cinder",
        type=str,
        choices=["yes", "no"],
        default="yes",
        help="Choosing whether to install Cinder (Block Storage) service (yes/no)"
    )

    general_options.add_argument(
        "--install-horizon",
        type=str,
        choices=["yes", "no"],
        default="yes",
        help="Choosing whether to install Horizon (Dashboard) service (yes/no)"
    )

    manila.add_argument(
            "--install-manila",
            type=str,
            choices=["yes", "no"],
            default="no",
            help="Choosing whether to install Manila (Shared Filesystems) service (yes/no)"
        )

    cinder.add_argument(
        "--cinder-lvm-image-size-in-gb",
        type=int,
        default=5,
        help="Size of the Cinder LVM image in GB (default: 5)"
    )

    cinder.add_argument(
        "--cinder-physical-volume",
        type=str,
        help="The physical volume to use for Cinder (example: /dev/sdb)"
    )

    manila_lvm_storage = manila.add_mutually_exclusive_group()

    manila_lvm_storage.add_argument(
        "--manila-lvm-physical-volume",
        type=str,
        help="The physical volume to use for Manila LVM (example: /dev/sdc)"
    )
    
    manila_lvm_storage.add_argument(
        "--manila-lvm-image-size-in-gb",
        type=int,
        help="Size of the Manila LVM image in GB (default: 5)"
    )

    general_options.add_argument(
        "--neutron-driver",
        type=str,
        choices=["ovs", "ovn"],
        default="ovs",
        dest="neutron_driver",
        help="The Neutron Driver that will be used to configure networks in OpenStack"
    )

    manila.add_argument(
        "--manila-backend",
        type=str,
        choices=["generic", "lvm"],
        default="lvm",
        dest="manila_backend",
        help="The Manila Backend that will be used to configure shares in OpenStack"
    )

    manila.add_argument(
        "--manila-share-protocols",
        nargs="+",
        choices=["nfs", "cifs"],
        default=["nfs"],
        dest="manila_share_protocols",
        help="One or more Manila share protocols (choices: nfs, cifs)."
    )

    general_options.add_argument(
        "--os-release",
        type=str,
        default="caracal",
        dest="os_release",
        help="The OpenStack release to install for deployment (default: caracal)"
    )

    general_options.add_argument(
        "--os-management-interface",
        type=str,
        help="Override the OpenStack management network interface used by services (example: eth0, ens18)"
    )

    general_options.add_argument(
        "--generate-only",
        action="store_true",
        help="Generates a pre-compiled configuration file for the current system without starting the deployment"
    )

    return parser

def deploy(parser, args) -> None:

    if args.allinone:
        config_file_path = generate_config_file()
        
        cinder_flag = args.install_cinder
        horizon_flag = args.install_horizon
        manila_flag = args.install_manila

        neutron_driver = args.neutron_driver if args.neutron_driver in ("ovs","ovn") else "ovs"
        manila_backend = args.manila_backend if args.manila_backend in ("generic", "lvm") else "lvm"

        manila_share_protocols = args.manila_share_protocols

        cinder_physical_volume = args.cinder_physical_volume if cinder_flag == "yes" else ""
        manila_lvm_physical_volume = (
            args.manila_lvm_physical_volume
            if manila_flag == "yes" and args.manila_lvm_physical_volume
            else ""
        )
        
        cinder_lvm_size = (args.cinder_lvm_image_size_in_gb if args.cinder_lvm_image_size_in_gb is not None else 5) if cinder_flag == "yes" else 0
        manila_lvm_size = (args.manila_lvm_image_size_in_gb if args.manila_lvm_image_size_in_gb is not None else 5) if manila_flag == "yes" else 0

        openstack_release = args.os_release

        if args.install_manila == "no" and (
            args.manila_lvm_physical_volume or
            args.manila_lvm_image_size_in_gb
        ):
            parser.error("Manila options require --install-manila yes")
        
        config_openstack(
            install_horizon=horizon_flag,
            install_cinder=cinder_flag,
            install_manila=manila_flag,
            config_file_path=config_file_path,
            cinder_physical_volume=cinder_physical_volume,
            manila_lvm_physical_volume=manila_lvm_physical_volume,
            cinder_lvm_image_size_in_gb=cinder_lvm_size,
            manila_lvm_image_size_in_gb=manila_lvm_size,
            neutron_driver=neutron_driver,
            manila_backend=manila_backend,
            manila_share_protocols=manila_share_protocols,
            os_mgmt_iface=args.os_management_interface,
            os_release=openstack_release
        )

        if args.generate_only:
            print(f"{colors.GREEN}Configuration file generated in '{config_file_path}{colors.RESET}'\n")
            print(f"You can start the deployment later with 'deploystack deploy --config-file {config_file_path}'")
            sys.exit(0)

        runner_deploy(config_file_path) 
    else:

        if args.config_file is None or not os.path.exists(args.config_file):
            print(f"{colors.RED}Configuration file not found. Generate it first using 'deploystack generate-config <file>'{colors.RESET}")
            sys.exit(1)
            
        runner_deploy(args.config_file) 
