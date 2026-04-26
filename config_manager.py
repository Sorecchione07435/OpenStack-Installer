import os
import shutil
import uuid
import yaml
from .utils.network.net_utils import get_network_info
from .utils.core.system_utils import has_hw_virtualization, get_free_loop, generate_password

import ipaddress

config_file_path = ""

def generate_config_file() -> str:

    global config_file_path
    config_file_path = f"/root/openstack-config-{uuid.uuid4().hex}.yaml"
    script_dir = os.path.dirname(os.path.realpath(__file__))
    src_file = os.path.join(script_dir, "templates/conf_template.yaml")
    shutil.copy(src_file, config_file_path)

    return config_file_path


def config_openstack(
    install_cinder: str = "yes",
    config_file_path: str = "",
    lvm_image_size_in_gb=None,
    neutron_driver: str = "ovs"   # "ovs" | "ovn"
):

    try:
        with open(config_file_path, "r") as f:
            config_dict = yaml.safe_load(f) or {}
    except FileNotFoundError:
        config_dict = {}

    iface, ip, netmask, cidr, broadcast, gateway, ip_cidr, network = get_network_info()

    last_ip = str(
        ipaddress.IPv4Address(
            ipaddress.IPv4Network(ip_cidr, strict=False).broadcast_address - 1
        )
    )

    if lvm_image_size_in_gb is None:
        lvm_image_size_in_gb = 5

    virt_type = "kvm" if has_hw_virtualization() else "qemu"

    # -------------------------------------------------------------------------
    # Passwords
    # -------------------------------------------------------------------------
    config_dict.setdefault("passwords", {})
    config_dict["passwords"]["ADMIN_PASSWORD"]    = generate_password()
    config_dict["passwords"]["SERVICE_PASSWORD"]  = generate_password()
    config_dict["passwords"]["RABBITMQ_PASSWORD"] = generate_password()
    config_dict["passwords"]["DATABASE_PASSWORD"] = generate_password()
    config_dict["passwords"]["DEMO_PASSWORD"]     = generate_password()

    # -------------------------------------------------------------------------
    # Network
    # -------------------------------------------------------------------------
    config_dict.setdefault("network", {})
    config_dict["network"]["HOST_IP"]         = ip
    config_dict["network"]["HOST_IP_NETMASK"] = netmask
    config_dict["network"]["HOST_IP_CIDR"]    = ip_cidr

    # -------------------------------------------------------------------------
    # Public network
    # -------------------------------------------------------------------------
    config_dict.setdefault("public_network", {})
    config_dict["public_network"]["PUBLIC_SUBNET_CIDR"]        = network
    config_dict["public_network"]["PUBLIC_SUBNET_RANGE_START"] = ip
    config_dict["public_network"]["PUBLIC_SUBNET_RANGE_END"]   = last_ip
    config_dict["public_network"]["PUBLIC_SUBNET_GATEWAY"]     = gateway
    config_dict["public_network"]["PUBLIC_SUBNET_DNS_SERVERS"] = "8.8.8.8"

    # -------------------------------------------------------------------------
    # Neutron - driver + driver-specific defaults
    # -------------------------------------------------------------------------
    config_dict.setdefault("neutron", {})
    config_dict["neutron"]["DRIVER"] = neutron_driver

    # OVS defaults
    config_dict["neutron"].setdefault("ovs", {})
    config_dict["neutron"]["ovs"]["CREATE_BRIDGES"]        = "yes" if neutron_driver == "ovs" else "no"
    config_dict["neutron"]["ovs"]["PUBLIC_BRIDGE_INTERFACE"] = iface if neutron_driver == "ovs" else ""
    config_dict["neutron"]["ovs"]["PUBLIC_BRIDGE"]         = "br-ex" if neutron_driver == "ovs" else ""
    config_dict["neutron"]["ovs"]["INTERNAL_BRIDGE"]       = "br-internal" if neutron_driver == "ovs" else ""

    # OVN defaults
    config_dict["neutron"].setdefault("ovn", {})
    config_dict["neutron"]["ovn"]["CREATE_BRIDGES"]            = "yes"
    config_dict["neutron"]["ovn"]["OVN_NB_PORT"]               = 6641
    config_dict["neutron"]["ovn"]["OVN_SB_PORT"]               = 6642
    config_dict["neutron"]["ovn"]["OVN_PUBLIC_BRIDGE_INTERFACE"] = iface
    config_dict["neutron"]["ovn"]["OVN_PUBLIC_BRIDGE"]         = "br-ex"
    config_dict["neutron"]["ovn"]["OVN_ENCAP_TYPE"]            = "geneve"
    config_dict["neutron"]["ovn"]["OVN_L3_SCHEDULER"]          = "leastloaded"
    config_dict["neutron"]["ovn"]["ENABLE_DISTRIBUTED_FLOATING_IP"] = False

    # Tenant network - type depends on driver
    config_dict["neutron"].setdefault("tenant_network", {})
    config_dict["neutron"]["tenant_network"]["TYPE"]      = "geneve" if neutron_driver == "ovn" else "flat"
    config_dict["neutron"]["tenant_network"]["VNI_RANGE"] = "1:65536"

    if neutron_driver == "ovs":

        config_dict["neutron"]["provider_networks"] = [
            {
                "name":   "public",
                "bridge": "br-ex",
                "type":   "flat"
            },
            {
                "name":   "internal",
                "bridge": "br-internal",
                "type":   "flat"
            }
        ]

    else:

        config_dict["neutron"]["provider_networks"] = [
            {
                "name":   "public",
                "bridge": "br-ex",
                "type":   "flat"
            }
        ]


    config_dict.setdefault("cinder", {})
    config_dict["optional_services"]["INSTALL_CINDER"] = "yes" if install_cinder == "yes" else "no"
    config_dict["cinder"]["lvm"]["CINDER_VOLUME_LVM_PHYSICAL_PV_LOOP_NAME"] = get_free_loop()
    config_dict["cinder"]["lvm"]["CINDER_VOLUME_LVM_IMAGE_FILE_PATH"]       = "/var/lib/cinder/images/cinder-volumes.img"
    config_dict["cinder"]["lvm"]["CINDER_VOLUME_LVM_IMAGE_SIZE_IN_GB"]      = lvm_image_size_in_gb

    # -------------------------------------------------------------------------
    # Compute
    # -------------------------------------------------------------------------
    config_dict.setdefault("compute", {})
    config_dict["compute"]["NOVA_COMPUTE_VIRT_TYPE"]   = virt_type
    config_dict["compute"]["CPU_ALLOCATION_RATIO"]     = 4.0
    config_dict["compute"]["RAM_ALLOCATION_RATIO"]     = 1.5
    config_dict["compute"]["DISK_ALLOCATION_RATIO"]    = 1.0

    # -------------------------------------------------------------------------
    # Optional services
    # -------------------------------------------------------------------------
    config_dict.setdefault("optional_services", {})
    config_dict["optional_services"]["INSTALL_HORIZON"] = "yes"

    # -------------------------------------------------------------------------
    # OpenStack release
    # -------------------------------------------------------------------------
    config_dict.setdefault("openstack", {})
    config_dict["openstack"].setdefault("OPENSTACK_RELEASE", "caracal")
    config_dict["openstack"].setdefault("REGION_NAME", "RegionOne")

    # -------------------------------------------------------------------------
    # Write config
    # -------------------------------------------------------------------------
    with open(config_file_path, "w") as f:
        yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)