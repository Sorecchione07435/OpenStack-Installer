from ..utils.core.commands import run_command
from ..utils.apt.apt import apt_install, apt_update
from ..utils.config.parser import parse_config, get
from ..utils.core import colors

import subprocess

def set_openstack_release(config):
    release = get(config, "openstack.OPENSTACK_RELEASE", "caracal")
    message = f"Adding repository for {release} OpenStack Release..."
    cmd = ["add-apt-repository", f"cloud-archive:{release}", "-y"]

    _ = run_command(cmd, message, ignore_errors=True)

def install_pkgs():

    print()
    
    apt_update()

    packages = ["wget", "rabbitmq-server", "python3-openstackclient", "memcached"]

    if not apt_install(packages, ux_text=f"Installing prerequisite packages..."): return False

    return True


def add_rabbitmq_openstack_user(config):
     
    print()

    rabbitmq_password = get(config, "passwords.RABBITMQ_PASSWORD")

    try:
        output = subprocess.check_output(["rabbitmqctl", "list_users"], text=True)
        user_exists = "openstack" in output
    except subprocess.CalledProcessError:
        user_exists = False

    if not user_exists:
        if not run_command(
            ["rabbitmqctl", "add_user", "openstack", rabbitmq_password],
            "Creating RabbitMQ OpenStack User..."
        ): return False

    if not run_command(
        ["rabbitmqctl", "set_permissions", "openstack", ".*", ".*", ".*"],
        "Setting permissions for RabbitMQ OpenStack User..."
    ): return False
    
    return True

def run_setup_prereqs(config):

    set_openstack_release(config)

    if not install_pkgs(): return False
    
    if not add_rabbitmq_openstack_user(config): return False

    print(f"\n{colors.GREEN}Prerequisites configured successfully!{colors.RESET}\n")
    return True