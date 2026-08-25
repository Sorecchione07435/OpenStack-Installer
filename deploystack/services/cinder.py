# Configure the Block Storage service (Cinder) (Controller + LVM Storage Node)

import pwd
import grp
import os
import subprocess

from pathlib import Path

from ..utils.core.commands import run_command, run_command_sync
from ..utils.apt.apt import apt_install
from ..utils.config.parser import get
from ..utils.config.setter import set_conf_option
from ..utils.core.system_utils import nc_wait
from ..utils.core import colors
from ..utils.core.system_utils import service_exists, is_debian, is_package_installed
from ..utils.lvm.loopback import write_loopback_lvm_env, setup_loopback_service
from ..utils.lvm import get_vg_for_pv, ensure_system_user_with_run_command

from ..utils.config.helpers import parse_bool

cinder_conf = "/etc/cinder/cinder.conf"
tgt_conf_path = "/etc/tgt/conf.d/cinder.conf"
lvm_conf_path = "/etc/lvm/lvm.conf"

def install_pkgs(config):

    install_cinder_backup = parse_bool(get(config, "cinder.ENABLE_CINDER_BACKUP", False))

    packages = ["cinder-scheduler", "cinder-api", "cinder-volume", "tgt"]

    if install_cinder_backup:
        packages.append("cinder-backup")

    if not apt_install(packages, ux_text=f"Installing Cinder packages...") : return False
    
    return True

def conf_lvm(config):

    os.makedirs("/var/lib/cinder/images", exist_ok=True)

    lvm_physical_volume = get(config, "cinder.lvm.PHYSICAL_VOLUME")
    lvm_image_file_path = get(config, "cinder.lvm.CINDER_VOLUME_LVM_IMAGE_FILE_PATH")
    lvm_loop_dev = get(config, "cinder.lvm.CINDER_VOLUME_LVM_PHYSICAL_PV_LOOP_PATH")
    lvm_image_size_in_gb = get(config, "cinder.lvm.CINDER_VOLUME_LVM_IMAGE_SIZE_IN_GB")

    VG_NAME = get(config, "cinder.lvm.VOLUME_GROUP")

    if lvm_physical_volume:
        lvm_dev = lvm_physical_volume
    else:
        lvm_dev = lvm_loop_dev

        if not os.path.exists(lvm_image_file_path):

            print() 

            truncate_cmd = [
                "truncate",
                "-s",
                f"{lvm_image_size_in_gb}G",
                lvm_image_file_path
            ]

            if not run_command(truncate_cmd, "Allocating LVM disk image..."):
                return False

            if not ensure_system_user_with_run_command("cinder"):
                return False

            uid = pwd.getpwnam("cinder").pw_uid
            gid = grp.getgrnam("cinder").gr_gid

            os.chown(lvm_image_file_path, uid, gid)
            os.chmod(lvm_image_file_path, 0o600)

            print()

        try:
            losetup_output = subprocess.check_output(
                ["losetup", "-j", lvm_image_file_path],
                text=True
            )
        except subprocess.CalledProcessError:
            losetup_output = ""

        if lvm_image_file_path not in losetup_output:
            if not run_command(
                ["losetup", lvm_loop_dev, lvm_image_file_path],
                f"Associating {lvm_image_file_path} to {lvm_loop_dev}..."
            ):
                return False
            
    vg = get_vg_for_pv(lvm_dev)

    if vg is None:

        print() 

        if not run_command(
            ["pvcreate", lvm_dev],
            f"Creating physical volume on {lvm_dev}..."
        ):
            return False

        if not run_command(
            ["vgcreate", VG_NAME, lvm_dev],
            f"Creating volume group {VG_NAME}..."
        ):
            return False

    elif vg == VG_NAME:
        pass

    else:
        print(
            f"{colors.RED}"
            f"{lvm_dev} already belongs to VG '{vg}', expected '{VG_NAME}'"
            f"{colors.RESET}"
        )
        return False
    
    os.makedirs(os.path.dirname(tgt_conf_path), exist_ok=True)

    if not os.path.exists(tgt_conf_path):
        with open(tgt_conf_path, "w") as f:
            f.write("include /var/lib/cinder/volumes/*")

    return True

def conf_cinder_backup(config):

    backup_driver = get(config, "cinder.backup.DRIVER").lower()

    backup_compression_algorithm = get(config, "cinder.backup.COMPRESSION_ALGORITHM").lower()

    backup_workers = get(config, "cinder.backup.BACKUP_WORKERS")

    backup_file_size = get(config, "cinder.backup.BACKUP_FILE_SIZE")
    backup_sha_block_size_bytes = get(config, "cinder.backup.BACKUP_SHA_BLOCK_SIZE_BYTES")

    if backup_driver == "posix":

        backup_filesystem_path = get(config, "cinder.backup.drivers.posix.BACKUP_PATH")

        os.makedirs(backup_filesystem_path, exist_ok=True)

        uid = pwd.getpwnam("cinder").pw_uid
        gid = grp.getgrnam("cinder").gr_gid
        os.chown(backup_filesystem_path, uid, gid)

        os.chmod(backup_filesystem_path, 0o750)

        run_command_sync(["sudo", "-u", "cinder", "touch", os.path.join(backup_filesystem_path, "test")])

        os.remove(os.path.join(backup_filesystem_path, "test"))

        set_conf_option(cinder_conf, "DEFAULT", "backup_driver", "cinder.backup.drivers.posix.PosixBackupDriver")
        set_conf_option(cinder_conf, "DEFAULT", "backup_posix_path", backup_filesystem_path)

    elif backup_driver == "nfs":

        nfs_share = get(config, "cinder.backup.drivers.nfs.NFS_SHARE")
        mount_point_base_dir = get(config, "cinder.backup.drivers.nfs.MOUNT_POINT_BASE")

        mount_options = get(config, "cinder.backup.drivers.nfs.MOUNT_OPTIONS") or None

        ip_address = get(config, "network.HOST_IP")

        if not is_package_installed("nfs-kernel-server"):
            print()

            if not apt_install(["nfs-kernel-server"], "Installing NFS Kernel Server package...") : return False

        exports_file = Path("/etc/exports")

        try:
            _, export_path = nfs_share.split(":", 1)
        except ValueError:
            return False

        os.makedirs(export_path, exist_ok=True)
        
        export_line = (f"{export_path} {ip_address}(rw,sync,no_subtree_check,no_root_squash)")

        lines = set()

        if exports_file.exists():
            with exports_file.open("r") as f:
                lines = {line.strip() for line in f}

        if export_line not in lines:
            with exports_file.open("a") as f:
                f.write(f"{export_line}\n")

            print()

            if not run_command(["exportfs", "-ra"], "Applying NFS exports...") : return False

        set_conf_option(cinder_conf, "DEFAULT", "backup_driver", "cinder.backup.drivers.nfs.NFSBackupDriver")

        set_conf_option(cinder_conf, "DEFAULT", "backup_mount_point_base", mount_point_base_dir)
        set_conf_option(cinder_conf, "DEFAULT", "backup_share", nfs_share)

        if mount_options:
            set_conf_option(cinder_conf, "DEFAULT", "backup_mount_options", mount_options)

    set_conf_option(cinder_conf, "DEFAULT", "backup_compression_algorithm", backup_compression_algorithm)
        
    set_conf_option(cinder_conf, "DEFAULT", "backup_workers", str(backup_workers))

    set_conf_option(cinder_conf, "DEFAULT", "backup_file_size", str(backup_file_size))
    set_conf_option(cinder_conf, "DEFAULT", "backup_sha_block_size_bytes", str(backup_sha_block_size_bytes))

    return True

def conf_cinder(config):

    print()
     
    db_password = get(config, "passwords.DATABASE_PASSWORD")
    rabbitmq_password = get(config, "passwords.RABBITMQ_PASSWORD")
    os_region_name = get(config, "openstack.REGION_NAME")

    service_password = get(config, "passwords.SERVICE_PASSWORD")

    ip_address = get(config, "network.HOST_IP")

    target_scsi_ip_address = get(config, "cinder.TARGET_IP_ADDRESS") or ip_address

    volume_clear = get(config, "cinder.VOLUME_CLEAR")
    volume_clear_size = int(get(config, "cinder.VOLUME_CLEAR_SIZE"))

    VG_NAME = get(config, "cinder.lvm.VOLUME_GROUP")

    if isinstance(target_scsi_ip_address, dict) or target_scsi_ip_address is None or "{network.HOST_IP}" in str(target_scsi_ip_address):
        target_scsi_ip_address = ip_address 

    target_scsi_ip_address = str(target_scsi_ip_address)

    set_conf_option(cinder_conf, "DEFAULT", "transport_url", f"rabbit://openstack:{rabbitmq_password}@{ip_address}:5672/")
    set_conf_option(cinder_conf, "DEFAULT", "glance_api_servers", f"http://{ip_address}:9292")
    set_conf_option(cinder_conf, "DEFAULT", "enabled_backends", "lvm")

    set_conf_option(cinder_conf, "DEFAULT", "my_ip", ip_address)
    set_conf_option(cinder_conf, "DEFAULT", "target_ip_address", target_scsi_ip_address)

    set_conf_option(cinder_conf, "keystone_authtoken", "memcached_servers", "127.0.0.1:11211")
    set_conf_option(cinder_conf, "keystone_authtoken", "www_authenticate_uri", f"http://{ip_address}:5000/")
    set_conf_option(cinder_conf, "keystone_authtoken", "region_name", os_region_name)
    set_conf_option(cinder_conf, "keystone_authtoken", "auth_url", f"http://{ip_address}:5000/")
    set_conf_option(cinder_conf, "keystone_authtoken", "auth_type", "password")
    set_conf_option(cinder_conf, "keystone_authtoken", "project_domain_name", "Default")
    set_conf_option(cinder_conf, "keystone_authtoken", "user_domain_name", "Default")
    set_conf_option(cinder_conf, "keystone_authtoken", "project_name", "service")
    set_conf_option(cinder_conf, "keystone_authtoken", "username", "cinder")
    set_conf_option(cinder_conf, "keystone_authtoken", "password", service_password)

    set_conf_option(cinder_conf, "lvm", "volume_driver", "cinder.volume.drivers.lvm.LVMVolumeDriver")
    set_conf_option(cinder_conf, "lvm", "volume_group", VG_NAME)
    set_conf_option(cinder_conf, "lvm", "volume_backend_name", "LVM")
    set_conf_option(cinder_conf, "lvm", "iscsi_protocol", "iscsi")
    set_conf_option(cinder_conf, "lvm", "iscsi_helper", "tgtadm")
    set_conf_option(cinder_conf, "lvm", "volume_clear", volume_clear)
    set_conf_option(cinder_conf, "lvm", "volume_clear_size", str(volume_clear_size))

    set_conf_option(cinder_conf, "service_user", "project_domain_name", "Default")
    set_conf_option(cinder_conf, "service_user", "project_name", "service")
    set_conf_option(cinder_conf, "service_user", "user_domain_name", "Default")
    set_conf_option(cinder_conf, "service_user", "password", service_password)
    set_conf_option(cinder_conf, "service_user", "username", "cinder")
    set_conf_option(cinder_conf, "service_user", "auth_url", f"http://{ip_address}:5000/v3")
    set_conf_option(cinder_conf, "service_user", "auth_type", "password")
    set_conf_option(cinder_conf, "service_user", "send_service_user_token", "True")

    set_conf_option(cinder_conf, "glance", "memcached_servers", "127.0.0.1:11211")
    set_conf_option(cinder_conf, "glance", "region_name", os_region_name)
    set_conf_option(cinder_conf, "glance", "project_domain_name", "Default")
    set_conf_option(cinder_conf, "glance", "project_name", "service")
    set_conf_option(cinder_conf, "glance", "www_authenticate_uri", f"http://{ip_address}:5000/v3")
    set_conf_option(cinder_conf, "glance", "user_domain_name", "Default")
    set_conf_option(cinder_conf, "glance", "password", service_password)
    set_conf_option(cinder_conf, "glance", "username", "glance")
    set_conf_option(cinder_conf, "glance", "auth_url", f"http://{ip_address}:5000/v3")
    set_conf_option(cinder_conf, "glance", "auth_type", "password")

    set_conf_option(cinder_conf, "nova", "region_name", os_region_name)
    set_conf_option(cinder_conf, "nova", "project_domain_name", "Default")
    set_conf_option(cinder_conf, "nova", "project_name", "service")
    set_conf_option(cinder_conf, "nova", "user_domain_name", "Default")
    set_conf_option(cinder_conf, "nova", "password", service_password)
    set_conf_option(cinder_conf, "nova", "username", "nova")
    set_conf_option(cinder_conf, "nova", "auth_url", f"http://{ip_address}:5000/v3")
    set_conf_option(cinder_conf, "nova", "auth_type", "password")

    set_conf_option(cinder_conf, "database", "connection", f"mysql+pymysql://cinder:{db_password}@{ip_address}/cinder")

    set_conf_option(cinder_conf, "oslo_concurrency", "lock_path", "/var/lib/cinder/tmp")

    set_conf_option(cinder_conf, "os_brick", "lock_path", "/var/lib/cinder/os-brick")

    db_migration_cmd = [
    "sudo", "-u", "cinder",
    "cinder-manage", "db", "sync"
    ]

    if not run_command(db_migration_cmd, "Running Cinder DB Migrations...") : return False
    
    return True

def finalize(config):

    ip_address = get(config, "network.HOST_IP")
    install_cinder_backup = parse_bool(get(config, "cinder.ENABLE_CINDER_BACKUP", False))

    print()

    cinder_services = [
        "cinder-scheduler",
        "cinder-volume", 
        "apache2", 
        "tgt"
    ]

    if install_cinder_backup:
        cinder_services.append("cinder-backup")

    if service_exists("cinder-api.service") and is_debian():
        cinder_services.append("cinder-api")

    if not run_command(["systemctl", "restart"] + cinder_services, "Restarting Cinder services...", False, None, 3, 5): return False
    
    if not nc_wait(ip_address, 8776) : return False

    return True

def run_setup_cinder(config):

    lvm_image_file_path = get(config, "cinder.lvm.CINDER_VOLUME_LVM_IMAGE_FILE_PATH")
    lvm_loop_dev = get(config, "cinder.lvm.CINDER_VOLUME_LVM_PHYSICAL_PV_LOOP_PATH")

    vg_name = get(config, "cinder.lvm.VOLUME_GROUP")

    install_cinder_backup = parse_bool(get(config, "cinder.ENABLE_CINDER_BACKUP", False))

    if not install_pkgs(config): return False 
    if not conf_lvm(config): return False

    if install_cinder_backup:
        if not conf_cinder_backup(config) : return False

    using_loopback = not get(config, "cinder.lvm.PHYSICAL_VOLUME")

    if using_loopback:
        if not write_loopback_lvm_env("cinder", lvm_image_file_path, lvm_loop_dev, vg_name, description="Cinder Loopback LVM", before_services="cinder-volume.service tgt.service"): return False   
        if not setup_loopback_service(lvm_image_file_path, lvm_loop_dev, vg_name, "cinder"): return False   

    if not conf_cinder(config): return False    
    if not finalize(config): return False
    
    print(f"\n{colors.GREEN}Cinder configured successfully!{colors.RESET}\n")
    return True
    