import os
import shutil
import uuid
import yaml
from dotenv import dotenv_values
from .utils.network.net_utils import get_network_info
from .utils.core.system_utils import has_hw_virtualization, get_free_loop, generate_password
from .utils.config.parser import set

import ipaddress

config_file_path = ""

def generate_config_file():

    global config_file_path
    config_file_path = f"/root/openstack-config-{uuid.uuid4().hex}.yaml"
    script_dir = os.path.dirname(os.path.realpath(__file__))
    src_file = os.path.join(script_dir, "templates/conf_template.yaml")
    shutil.copy(src_file, config_file_path)

def config_openstack(lvm_image_size_in_gb=None):
    global config_file_path

    # carica yaml
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

    config_dict.setdefault("passwords", {})
    config_dict.setdefault("network", {})
    config_dict.setdefault("public_network", {})
    config_dict.setdefault("bridge", {})
    config_dict.setdefault("cinder", {})
    config_dict.setdefault("compute", {})

    config_dict["passwords"]["ADMIN_PASSWORD"] = generate_password()
    config_dict["passwords"]["SERVICE_PASSWORD"] = generate_password()
    config_dict["passwords"]["RABBITMQ_PASSWORD"] = generate_password()
    config_dict["passwords"]["DATABASE_PASSWORD"] = generate_password()
    config_dict["passwords"]["DEMO_PASSWORD"] = generate_password()

    config_dict["network"]["HOST_IP"] = ip
    config_dict["network"]["HOST_IP_NETMASK"] = netmask
    config_dict["network"]["HOST_IP_CIDR"] = ip_cidr

    config_dict["public_network"]["PUBLIC_SUBNET_CIDR"] = network
    config_dict["public_network"]["PUBLIC_SUBNET_RANGE_START"] = ip
    config_dict["public_network"]["PUBLIC_SUBNET_RANGE_END"] = last_ip
    config_dict["public_network"]["PUBLIC_SUBNET_GATEWAY"] = gateway
    config_dict["public_network"]["PUBLIC_SUBNET_DNS_SERVERS"] = "8.8.8.8"

    config_dict["bridge"]["CREATE_BRIDGES"] = "yes"
    config_dict["bridge"]["PUBLIC_BRIDGE_INTERFACE"] = iface

    config_dict["cinder"]["INSTALL_CINDER"] = "yes"
    config_dict["cinder"]["CINDER_VOLUME_LVM_PHYSICAL_PV_LOOP_NAME"] = get_free_loop()
    config_dict["cinder"]["CINDER_VOLUME_LVM_IMAGE_FILE_PATH"] = "/var/lib/cinder/images/cinder-volumes.img"

    config_dict["cinder"]["CINDER_VOLUME_LVM_IMAGE_SIZE_IN_GB"] = lvm_image_size_in_gb

    virt_type = "kvm" if has_hw_virtualization() else "qemu"
    config_dict["compute"]["NOVA_COMPUTE_VIRT_TYPE"] = virt_type

    with open(config_file_path, "w") as f:
        yaml.dump(config_dict, f, default_flow_style=False)

def get_config_file_path():
    return config_file_path