# Configure the Block Storage service (Cinder)

from ..utils.core.commands import run_command, run_sync_command_with_retry, run_command_sync
from ..utils.apt.apt import apt_install, apt_update
from ..utils.config.parser import parse_config, get, resolve_vars
from ..utils.config.setter import set_conf_option
from ..utils import colors

import pwd
import grp
import os
import subprocess

cinder_conf = "/etc/cinder/cinder.conf"

def ensure_system_user_with_run_command(username="cinder"):
    success = True

    try:
        grp.getgrnam(username)
    except KeyError:
        if not run_command(
            ["groupadd", username],
            message=f"Creating group {username}",
            ignore_errors=False
        ):
            success = False

    try:
        pwd.getpwnam(username)
    except KeyError:
        if not run_command(
            ["useradd", "-r", "-s", "/bin/false", username],
            message=f"Creating system user {username}",
            ignore_errors=False
        ):
            success = False

    return success

def install_pkgs():

    packages = ["cinder-scheduler", "cinder-api", "cinder-volume", "tgt"]

    if not apt_install(packages, ux_text=f"Installing Cinder packages...") : return False
    
    return True

def conf_lvm(config):

    print()

    cinder_conf_path = "/etc/tgt/conf.d/cinder.conf"
    line = "include /var/lib/cinder/volumes/*\n"
      
    lvm_image_file_path = get(config, "cinder.CINDER_VOLUME_LVM_IMAGE_FILE_PATH")
    lvm_loop_dev = get(config, "cinder.CINDER_VOLUME_LVM_PHYSICAL_PV_LOOP_NAME")

    lvm_image_size_in_gb = get(config, "cinder.CINDER_VOLUME_LVM_IMAGE_SIZE_IN_GB")

    VG_NAME="cinder-volumes"

    os.makedirs("/var/lib/cinder/images", exist_ok=True)

    if not os.path.exists(lvm_image_file_path):
         fallocate_cmd = ["fallocate", "-l", f"{lvm_image_size_in_gb}G", lvm_image_file_path]

         fallocate_cmd_result = run_command(fallocate_cmd, "Allocating LVM Disk Image...")

         if not fallocate_cmd_result: return False
         
         if not ensure_system_user_with_run_command("cinder"): return False
         
         uid = pwd.getpwnam("cinder").pw_uid
         gid = grp.getgrnam("cinder").gr_gid
         os.chown(lvm_image_file_path, uid, gid)

         os.chmod(lvm_image_file_path, 0o600)
    
    if not run_command(["losetup", lvm_loop_dev], message=f"Checking {lvm_loop_dev}", ignore_errors=True):
       if not run_command(
            ["losetup", lvm_loop_dev, lvm_image_file_path],
            message=f"Associating {lvm_image_file_path} to {lvm_loop_dev}"
        ): return False
    
    check_cmd = ["pvs"]
    pvs_result = run_command_sync(
        check_cmd,
    )

    try:
        output = subprocess.check_output(["pvs"], text=True)
    except subprocess.CalledProcessError:
        output = ""

    if lvm_loop_dev not in output:
       if not  run_command(
            ["pvcreate", lvm_loop_dev],
            message=f"Creating physical volume on {lvm_loop_dev}"
        ): return False
    
    try:
        output = subprocess.check_output(["vgs"], text=True)
    except subprocess.CalledProcessError:
        output = ""

    if VG_NAME not in output:
        if not run_command(
            ["vgcreate", VG_NAME, lvm_loop_dev],
            message=f"Creating volume group {VG_NAME}"
        ): return False
    
    with open(cinder_conf_path, "w") as fconf:
        fconf.write(line)

    return True

def setup_loopback_service(config):

    print()

    SERVICE_PATH = "/etc/systemd/system/cinder-loopback.service"
       
    lvm_image_file_path = get(config, "cinder.CINDER_VOLUME_LVM_IMAGE_FILE_PATH")
    lvm_loop_dev = get(config, "cinder.CINDER_VOLUME_LVM_PHYSICAL_PV_LOOP_NAME")

    lvm_image_size_in_gb = get(config, "cinder.CINDER_VOLUME_LVM_IMAGE_SIZE_IN_GB")

    VG_NAME="cinder-volumes"

     
    service_content = f"""[Unit]
Description=Cinder LVM loopback device
Before=cinder-volume.service tgt.service
DefaultDependencies=no
After=local-fs.target

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'if ! losetup {lvm_loop_dev} | grep -q cinder-volumes.img; then /sbin/losetup {lvm_loop_dev} {lvm_image_file_path}; fi'
ExecStart=/sbin/vgchange -ay {VG_NAME}
ExecStop=/sbin/vgchange -an {VG_NAME}
ExecStop=/bin/bash -c 'if losetup {lvm_loop_dev} | grep -q cinder-volumes.img; then /sbin/losetup -d {lvm_loop_dev}; fi'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
"""

    with open(SERVICE_PATH, "w") as f:
        f.write(service_content)

    if not run_command(["systemctl", "daemon-reload"], "Reloading systemd daemon..."): return False

    return True

def conf_cinder(config):

    print()
     
    db_password = get(config, "passwords.DATABASE_PASSWORD")
    rabbitmq_password = get(config, "passwords.RABBITMQ_PASSWORD")

    service_password = get(config, "passwords.SERVICE_PASSWORD")

    ip_address = get(config, "network.HOST_IP")

    set_conf_option(cinder_conf, "DEFAULT", "transport_url", f"rabbit://openstack:{rabbitmq_password}@{ip_address}:5672/")
    set_conf_option(cinder_conf, "DEFAULT", "glance_api_servers", f"http://{ip_address}:9292")
    set_conf_option(cinder_conf, "DEFAULT", "enabled_backends", "lvm")

    set_conf_option(cinder_conf, "keystone_authtoken", "www_authenticate_uri", f"http://{ip_address}:5000/")
    set_conf_option(cinder_conf, "keystone_authtoken", "auth_url", f"http://{ip_address}:5000/")
    set_conf_option(cinder_conf, "keystone_authtoken", "memcached_servers", "127.0.0.1:11211")
    set_conf_option(cinder_conf, "keystone_authtoken", "auth_type", "password")
    set_conf_option(cinder_conf, "keystone_authtoken", "project_domain_name", "Default")
    set_conf_option(cinder_conf, "keystone_authtoken", "user_domain_name", "Default")
    set_conf_option(cinder_conf, "keystone_authtoken", "project_name", "service")
    set_conf_option(cinder_conf, "keystone_authtoken", "username", "cinder")
    set_conf_option(cinder_conf, "keystone_authtoken", "password", service_password)

    set_conf_option(cinder_conf, "lvm", "volume_driver", "cinder.volume.drivers.lvm.LVMVolumeDriver")
    set_conf_option(cinder_conf, "lvm", "volume_group", "cinder-volumes")
    set_conf_option(cinder_conf, "lvm", "volume_backend_name", "LVM")
    set_conf_option(cinder_conf, "lvm", "iscsi_protocol", "iscsi")
    set_conf_option(cinder_conf, "lvm", "iscsi_helper", "tgtadm")
    set_conf_option(cinder_conf, "lvm", "volume_clear", "zero")
    set_conf_option(cinder_conf, "lvm", "volume_clear_size", "1")

    set_conf_option(cinder_conf, "database", "connection", f"mysql+pymysql://cinder:{db_password}@{ip_address}/cinder")

    set_conf_option(cinder_conf, "oslo_concurrency", "lock_path", "/var/lib/cinder/tmp")

    db_migration_cmd = [
    "sudo", "-u", "cinder",
    "cinder-manage", "db", "sync"
]
    migration_result = run_command(db_migration_cmd, "Running Cinder DB Migrations...")

    if not migration_result: return False
    
    return True

def finalize():

    print()

    if not run_command(["systemctl", "restart", "cinder-scheduler", "cinder-volume", "apache2", "tgt"], "Restarting Cinder services...", False, None, 3, 5): return False
    
    return True

def run_setup_cinder(config):

    if not install_pkgs(): return False
    
    if not conf_lvm(config): return False
    
    if not setup_loopback_service(config): return False
    
    if not conf_cinder(config): return False
    
    if not finalize(): return False
    
    print(f"\n{colors.GREEN}Cinder configured successfully!{colors.RESET}\n")
    return True
    
