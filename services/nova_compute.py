# Configure an Compute Node

from ..utils.core.commands import run_command, run_sync_command_with_retry, run_command_sync
from ..utils.apt.apt import apt_install, apt_update
from ..utils.config.parser import parse_config, get, resolve_vars
from ..utils.config.setter import set_conf_option
from ..utils.core import colors

import os

nova_conf= "/etc/nova/nova.conf"
nova_compute_conf= "/etc/nova/nova-compute.conf"

def install_pkgs():

    packages = ["nova-compute"]

    if not apt_install(packages, ux_text=f"Installing Nova Compute package...") : return False

    return True

def conf_nova_compute(config):
      
    virt_type = get(config, "compute.NOVA_COMPUTE_VIRT_TYPE")

    set_conf_option(nova_compute_conf, "libvirt", "virt_type", virt_type)

    set_conf_option(nova_conf, "scheduler", "discover_hosts_in_cells_interval", "300")

def finalize():

    print()

    if not run_command(["systemctl", "restart", "nova-api", "nova-scheduler", "nova-compute", "apache2"], "Restarting Nova Compute services..."): return False
    
    cell_discover_hosts_migration_cmd = [
    "sudo", "-u", "nova",
    "nova-manage", "cell_v2", "discover_hosts", "--verbose"
]
    
    cell_discover_hosts_migration_cmd_result = run_command(cell_discover_hosts_migration_cmd, "Discovering the Compute Node on Cell0...")

    if not cell_discover_hosts_migration_cmd_result: return False

    return True

def create_default_flavors(config):
     
    print()
    
    ip_address = get(config, "network.HOST_IP")

    admin_password = get(config, "passwords.ADMIN_PASSWORD")
    demo_password = get(config, "passwords.DEMO_PASSWORD")
     
    os.environ["OS_USERNAME"] = "admin"
    os.environ["OS_PASSWORD"] = admin_password
    os.environ["OS_PROJECT_NAME"] = "admin"
    os.environ["OS_USER_DOMAIN_NAME"] = "Default"
    os.environ["OS_PROJECT_DOMAIN_NAME"] = "Default"
    os.environ["OS_AUTH_URL"] = f"http://{ip_address}:5000/v3"
    os.environ["OS_IDENTITY_API_VERSION"] = "3"

    default_flavors_create_cmds = [
       "openstack flavor create m1.tiny --id 1 --ram 512 --disk 1 --vcpus 1",
       "openstack flavor create m1.small --id 2 --ram 2048 --disk 20 --vcpus 1",
       "openstack flavor create m1.medium --id 3 --ram 4096 --disk 40 --vcpus 2",
       "openstack flavor create m1.large --id 4 --ram 8192 --disk 80 --vcpus 4",
       "openstack flavor create m1.xlarge --id 5 --ram 16384 --disk 160 --vcpus 8", 
    ]

    full_default_flavors_create_cmds = " ; ".join(default_flavors_create_cmds)

    full_default_flavors_create_cmds_result = run_command(["bash", "-c", full_default_flavors_create_cmds], "Creating default flavors...", True)

    return True
    
def run_setup_nova_compute(config):
     
     if not install_pkgs(): return False
     
     conf_nova_compute(config)
     
     if not finalize(): return False
     
     if not create_default_flavors(config): return False
     
     print(f"\n{colors.GREEN}Compute Node configured successfully!{colors.RESET}\n")
     return True