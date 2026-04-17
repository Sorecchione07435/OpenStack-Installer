# Configure the Placement service (Placement)

from ..utils.core.commands import run_command, run_sync_command_with_retry, run_command_sync
from ..utils.apt.apt import apt_install, apt_update
from ..utils.config.parser import parse_config, get, resolve_vars
from ..utils.config.setter import set_conf_option
from ..utils import colors

placement_conf = "/etc/placement/placement.conf"

def install_pkgs():

    packages = ["placement-api"]

    if not apt_install(packages, ux_text=f"Installing Placement package..."): return False
    
    return True

def conf_placement(config):

    print()

    db_password = get(config, "passwords.DATABASE_PASSWORD")
    rabbitmq_password = get(config, "passwords.RABBITMQ_PASSWORD")

    service_password = get(config, "passwords.SERVICE_PASSWORD")

    ip_address = get(config, "network.HOST_IP")
      
    set_conf_option(placement_conf, "keystone_authtoken", "www_authenticate_uri", f"http://{ip_address}:5000/")
    set_conf_option(placement_conf, "keystone_authtoken", "auth_url", f"http://{ip_address}:5000/")
    set_conf_option(placement_conf, "keystone_authtoken", "memcached_servers", "127.0.0.1:11211")
    set_conf_option(placement_conf, "keystone_authtoken", "auth_type", "password")
    set_conf_option(placement_conf, "keystone_authtoken", "project_domain_name", "Default")
    set_conf_option(placement_conf, "keystone_authtoken", "user_domain_name", "Default")
    set_conf_option(placement_conf, "keystone_authtoken", "project_name", "service")
    set_conf_option(placement_conf, "keystone_authtoken", "username", "placement")
    set_conf_option(placement_conf, "keystone_authtoken", "password", service_password)

    db_migration_cmd = [
    "sudo", "-u", "placement",
    "placement-manage", "db", "sync"
]
    if not run_command(db_migration_cmd, "Running Placement DB Migrations...") : return False
    
    return True

def finalize():
     
    print()

    if not run_command(["systemctl", "restart", "apache2"], "Restarting Apache2..."): return False
    
    return True

def run_setup_placement(config):
     
     if not install_pkgs(): return False
     
     if not conf_placement(config): return False
     
     if not finalize(): return False
     
     print(f"\n{colors.GREEN}Placement configured successfully!{colors.RESET}\n")
     return True