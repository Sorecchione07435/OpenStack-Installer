# Configure the Image service (Glance)

from ..utils.core.commands import run_command, run_command_sync
from ..utils.apt.apt import apt_install, apt_update
from ..utils.config.parser import parse_config, get, resolve_vars
from ..utils.config.setter import set_conf_option
from ..utils import colors

import urllib.request
import os

glance_conf= "/etc/glance/glance-api.conf"

cirros_image_url = "http://download.cirros-cloud.net/0.4.0/cirros-0.4.0-x86_64-disk.img"

def install_pkgs():

    packages = ["glance-api"]

    if not apt_install(packages, ux_text=f"Installing Glance package..."): return False

    return True

def conf_glance(config):
      
    db_password = get(config, "passwords.DATABASE_PASSWORD")
    service_password = get(config, "passwords.SERVICE_PASSWORD")

    ip_address = get(config, "network.HOST_IP")
      
    set_conf_option(glance_conf, "database", "connection", f"mysql+pymysql://glance:{db_password}@{ip_address}/glance")

    set_conf_option(glance_conf, "keystone_authtoken", "www_authenticate_uri", f"http://{ip_address}:5000")
    set_conf_option(glance_conf, "keystone_authtoken", "auth_url", f"http://{ip_address}:5000")
    set_conf_option(glance_conf, "keystone_authtoken", "memcached_servers", "127.0.0.1:11211")
    set_conf_option(glance_conf, "keystone_authtoken", "auth_type", "password")
    set_conf_option(glance_conf, "keystone_authtoken", "project_domain_name", "Default")
    set_conf_option(glance_conf, "keystone_authtoken", "user_domain_name", "Default")
    set_conf_option(glance_conf, "keystone_authtoken", "project_name", "service")
    set_conf_option(glance_conf, "keystone_authtoken", "username", "glance")
    set_conf_option(glance_conf, "keystone_authtoken", "password", service_password)

    set_conf_option(glance_conf, "paste_deploy", "flavor", "keystone")

    set_conf_option(glance_conf, "glance_store", "stores", "file,http")
    set_conf_option(glance_conf, "glance_store", "default_store", "file")
    set_conf_option(glance_conf, "glance_store", "filesystem_store_datadir", "/var/lib/glance/images/")

    db_migration_cmd = [
    "sudo", "-u", "glance",
    "env",
    "PATH=/usr/bin:/usr/local/bin",
    "glance-manage", "db_sync"
]
    migration_result = run_command(db_migration_cmd, "Configuring Glance...")
    return True

def finalize():
    restart_cmd = ["systemctl", "restart", "glance-api"]

    if not run_command_sync(restart_cmd) : return False

    return True

def upload_cirros_image(config):

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

    image_name = "cirros"
    image_file_path = "/tmp/cirros-0.4.0-x86_64-disk.img"
    
    if not run_command_sync([ "wget", "-O", image_file_path, cirros_image_url]) : return False
    
    run_command_sync(["openstack", "image", "delete", "cirros"])

    create_cirros_image_cmd = [
        "glance", "image-create",
        "--name", image_name,
        "--file", image_file_path,
        "--disk-format", "qcow2",
        "--container-format", "bare",
        "--visibility", "public"
    ]

    create_image_result = run_command(create_cirros_image_cmd, f"Adding cirros image...")

    if not create_image_result : return False
    
    os.remove(image_file_path)

    return True
    
    
def run_setup_glance(config):
     
     if not install_pkgs(): return False
     
     if not conf_glance(config): return False
     
     if not finalize(): return False
     
     if not upload_cirros_image(config): return False

     print(f"\n{colors.GREEN}Glance configured successfully!{colors.RESET}\n")
     return True