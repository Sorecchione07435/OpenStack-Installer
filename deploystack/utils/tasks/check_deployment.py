import subprocess
import os
import logging
import time
import json

from dataclasses import dataclass, field

from ..config.parser import get_conf_option

from ..core.commands import run_command_output

from ..core.system_utils import service_exists, is_debian, is_ubuntu_release

from ..core import colors

MARKER_FILE = "/var/lib/openstack_installer/deploy_complete"

logger = logging.getLogger(__name__)

cinder_pkgs = ["cinder-api", "cinder-scheduler", "cinder-volume", "tgt"]
manila_pkgs = ["manila-api", "manila-scheduler", "python3-manilaclient", "manila-share"]

class CheckCategory:
    SERVICES = "Services"
    PACKAGES = "Packages"
    CONFIG = "Config files"
    ENDPOINTS = "Endpoints"

@dataclass
class CheckResult:
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.failed) == 0

    def __str__(self):
        lines = [f"{colors.GREEN}PASSED:{colors.RESET} {s}" for s in self.passed] + [f"{colors.RED}FAILED:{colors.RESET} {s}" for s in self.failed]
        return "\n".join(lines)

def check_keystone_auth() -> tuple[bool, str]:
    logger.debug("Checking Keystone authentication...")
    try:
        token = run_command_output(["openstack", "token", "issue", "-f", "value", "-c", "id"])

        if token.strip():
            logger.info("Keystone authentication successful, token received.")
            return True, ""

        logger.warning("Keystone authentication returned an empty token.")
        return False, "Empty Keystone token received"
    except subprocess.CalledProcessError as e:
        logger.error(f"Keystone authentication failed: {e}")
        return False, "Keystone authentication failed. Check credentials or OS_* environment variables"

    except subprocess.TimeoutExpired:
        logger.error("Keystone request timed out.")
        return False, "Keystone request timed out. Check Keystone service availability"

    except FileNotFoundError:
        logger.error("OpenStack client command not found.")
        return False, "OpenStack client command not found"

    except Exception as e:
        logger.exception("Unexpected Keystone authentication error")
        return False, str(e)

def is_package_installed(pkg_name: str) -> bool:
    logger.debug(f"Checking if package '{pkg_name}' is installed...")
    try:
        result = subprocess.run(
            ["dpkg-query", "-W", "-f=${Status}", pkg_name],
            capture_output=True, text=True, check=True
        )
        installed = "install ok installed" in result.stdout
        logger.debug(f"Package '{pkg_name}' installed: {installed}")
        return installed
    except subprocess.CalledProcessError:
        logger.debug(f"Package '{pkg_name}' is not installed (dpkg-query failed).")
        return False

def check_endpoint(service_name: str) -> bool:
    logger.debug(f"Checking endpoint for service '{service_name}'...")
    try:
        output = run_command_output(["openstack", "endpoint", "list", "--service", service_name, "-f", "json", "-c Enabled"])

        result = bool(json.loads(output))
        logger.debug(f"Endpoint check for '{service_name}': {result}")
        return result

    except (
        json.JSONDecodeError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError
    ) as e:
        logger.warning(f"Endpoint check failed for '{service_name}': {e}")
        return False

def check_service_active(svc: str) -> bool:
    logger.debug(f"Checking if service '{svc}' is active...")
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "--quiet", svc],
            timeout=5
        )
        active = result.returncode == 0
        logger.debug(f"Service '{svc}' active: {active}")
        return active
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.warning(f"Service check failed for '{svc}': {e}")
        return False

def check_deployment(include_endpoints: bool = True):
    logger.info(f"Starting deployment check (include_endpoints={include_endpoints})...")
    result = CheckResult()

    services_list = ["apache2", "glance-api"]

    if service_exists("nova-api.service") and is_package_installed("nova-api"):
        logger.debug("nova-api service detected, adding to services list.")
        services_list.append("nova-api.service")

    if service_exists("neutron-server.service"):
        logger.debug("neutron-server service detected.")
        services_list.append("neutron-server")
    elif service_exists("neutron-api.service"):
        logger.debug("neutron-api service detected.")
        services_list.append("neutron-api")
    elif service_exists("neutron-periodic-workers.service"):
        logger.debug("neutron-periodic-workers service detected.")
        services_list.append("neutron-periodic-workers")

    checks = [
        (CheckCategory.SERVICES, services_list, check_service_active),
        (CheckCategory.PACKAGES, ["apache2", "nova-common", "glance-api", "neutron-server"], is_package_installed),
        (CheckCategory.CONFIG, [
            "/etc/keystone/keystone.conf", "/etc/glance/glance-api.conf",
            "/etc/nova/nova.conf", "/etc/neutron/neutron.conf"
        ], os.path.isfile),
    ]

    def add_check(category, items, fn):
        logger.debug(f"Adding check category '{category}' with items: {items}")
        checks.append((category, items, fn))

    def add_packages_check(items):
        add_check(CheckCategory.PACKAGES, items, is_package_installed)

    def add_services_check(items):
        add_check(CheckCategory.SERVICES, items, check_service_active)

    def add_config_files_check(items):
        add_check(CheckCategory.CONFIG, items, os.path.isfile)

    def add_endpoints_check(items):
        add_check(CheckCategory.ENDPOINTS, items, check_endpoint)

    if all(is_package_installed(pkg) for pkg in cinder_pkgs):
        logger.info("Cinder packages detected, adding Cinder checks.")
        add_services_check(["cinder-scheduler", "cinder-volume", "tgt"])
        add_packages_check(cinder_pkgs)
        add_config_files_check(["/etc/cinder/cinder.conf", "/etc/tgt/conf.d/cinder.conf"])

        if include_endpoints:
            add_endpoints_check(["volumev3"])
    else:
        logger.debug("Cinder packages not fully installed, skipping Cinder checks.")

    if all(is_package_installed(pkg) for pkg in manila_pkgs):
        logger.info("Manila packages detected, adding Manila checks.")
        manila_conf = "/etc/manila/manila.conf"

        add_config_files_check([manila_conf])
        add_services_check(["manila-api", "manila-scheduler", "manila-share"])

        if include_endpoints:
            add_endpoints_check(["sharev2"])

            if not is_debian() and not is_ubuntu_release("26.04"):
                add_endpoints_check(["share"])

        manila_backend = (get_conf_option(manila_conf, "DEFAULT", "enabled_share_backends") or "").lower()
        manila_protocols_list = (get_conf_option(manila_conf, "DEFAULT", "enabled_share_protocols") or "").lower()

        manila_protocols = [protocol for protocol in manila_protocols_list.split(",") if protocol]
        logger.debug(f"Manila backend: '{manila_backend}', protocols: {manila_protocols}")

        if manila_backend == "lvm":
            logger.info("LVM backend detected for Manila.")
            add_packages_check(["lvm2", "nfs-kernel-server"])

            if "cifs" in manila_protocols:
                logger.info("CIFS protocol enabled, adding Samba checks.")
                smb_conf = "/etc/samba/smb.conf"

                samba_services = ["smbd.service"]

                if service_exists("nmbd.service"):
                    samba_services.append("nmbd.service")

                add_packages_check(["samba", "samba-common-bin"])
                add_config_files_check([smb_conf])
                add_services_check(samba_services)

            if "nfs" in manila_protocols:
                logger.info("NFS protocol enabled (LVM backend), adding NFS checks.")
                nfs_services = ["nfs-server.service"]

                if service_exists("nmbd.service"):
                    samba_services.append("nmbd.service")

                    add_packages_check(["nfs-server"])
                    add_services_check(nfs_services)

        if "nfs" in manila_protocols:
            logger.info("NFS protocol enabled, adding generic NFS checks.")
            add_packages_check(["nfs-kernel-server", "nfs-common"])
            add_services_check(["nfs-server"])
    else:
        logger.debug("Manila packages not fully installed, skipping Manila checks.")

    if include_endpoints:
        logger.debug("Adding core endpoint checks (identity, compute, image, network).")
        add_endpoints_check(["identity", "compute", "image", "network"])

    for category, items, check_fn in checks:
        for item in items:
            label = f"[{category}] {item}"
            if check_fn(item):
                logger.debug(f"CHECK PASSED: {label}")
                result.passed.append(label)
            else:
                logger.warning(f"CHECK FAILED: {label}")
                result.failed.append(label)

    logger.info(f"Deployment check completed. Passed: {len(result.passed)}, Failed: {len(result.failed)}")
    return result

def check_env_variables():
    logger.debug("Checking required environment variables...")
    required_vars = [
        "OS_PROJECT_DOMAIN_NAME",
        "OS_USER_DOMAIN_NAME",
        "OS_PROJECT_NAME",
        "OS_USERNAME",
        "OS_PASSWORD",
        "OS_AUTH_URL",
        "OS_IDENTITY_API_VERSION",
        "OS_IMAGE_API_VERSION"
    ]

    missing = []
    empty = []

    for var in required_vars:
        value = os.environ.get(var)
        if value is None:
            missing.append(var)
        elif value.strip() == "":
            empty.append(var)

    if missing or empty:
        error_msg = []

        if missing:
            error_msg.append(f"Missing vars: {', '.join(missing)}")
        if empty:
            error_msg.append(f"Empty vars: {', '.join(empty)}")

        logger.error(f"Environment variable check failed: {' | '.join(error_msg)}")
        raise RuntimeError(" | ".join(error_msg))

    logger.info("All required environment variables are set.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("=== Starting base deployment check (no endpoints) ===")

    outcome = check_deployment(include_endpoints=False)
    print(outcome)

    if not outcome.ok:
        logger.error("Base deployment check failed. Exiting with code 1.")
        exit(1)

    try:
        check_env_variables()
    except RuntimeError as e:
        logger.error(f"Environment variables error: {e}")
        exit(1)

    logger.info("=== Starting full deployment check (with endpoints) ===")
    endpoint_result = check_deployment(include_endpoints=True)
    print(endpoint_result)

    if endpoint_result.ok:
        logger.info("Full deployment check passed.")
    else:
        logger.error("Full deployment check failed.")

    exit(0 if endpoint_result.ok else 1)

def check_cinder_available() -> bool:
    logger.debug("Checking Cinder availability...")

    if not all(is_package_installed(pkg) for pkg in cinder_pkgs):
        logger.debug("Cinder packages not fully installed.")
        return False

    if not check_endpoint("volumev3"):
        logger.debug("Cinder 'volumev3' endpoint not available.")
        return False

    if not all(check_service_active(service) for service in ["cinder-scheduler", "cinder-volume", "tgt"]):
        logger.debug("One or more Cinder services are not active.")
        return False

    logger.info("Cinder is fully available.")
    return True

def is_cinder_available() -> bool:
    if not check_cinder_available():
        logger.warning("Cinder service is not installed or not available.")
        print(f"{colors.RED}Cinder service is not installed or not available.{colors.RESET}\n")
        print(f"{colors.YELLOW}  • If you want block storage support, run 'deploystack deploy --allinone' or include Cinder in your deployment{colors.RESET}")
        print(f"{colors.YELLOW}  • Alternatively, continue without Cinder, but volume-based features will not be available{colors.RESET}\n")
        return False

    return True

def is_openstack_ready() -> bool:
    logger.info("Checking whether OpenStack is ready...")

    if not os.path.exists(MARKER_FILE):
        logger.debug(f"Marker file '{MARKER_FILE}' not found. Deployment not complete.")
        return False

    try:
        check_env_variables()
    except RuntimeError:
        logger.warning("Shell is not authenticated (missing environment variables).")
        print(f"{colors.YELLOW}Shell is not authenticated. Source the environment file first:{colors.RESET}\n")
        print(f"  {colors.YELLOW}source /root/admin-openrc.sh{colors.RESET}  or")
        print(f"  {colors.GREEN}source /root/demo-openrc.sh{colors.RESET}\n")
        return False

    auth_ok, auth_error = check_keystone_auth()

    if not auth_ok:
        logger.error(f"OpenStack authentication failed: {auth_error}")
        print(f"{colors.RED}OpenStack authentication failed.{colors.RESET}\n")
        print(f"{colors.YELLOW}  • {auth_error}{colors.RESET}")
        print(f"{colors.YELLOW}  • Verify your OpenStack credentials and environment variables.{colors.RESET}")
        print(f"{colors.YELLOW}  • Source an admin environment file first:{colors.RESET}")
        print(f"    {colors.GREEN}source /root/admin-openrc.sh{colors.RESET}\n")
        return False

    base_check = check_deployment(include_endpoints=False)
    if not base_check.ok:
        logger.warning("OpenStack is not deployed yet (base check failed).")
        print(f"{colors.RED}OpenStack is not deployed yet.{colors.RESET}\n")
        print(f"{colors.YELLOW}  • Run 'deploy --allinone' for a full automated deployment{colors.RESET}")
        print(f"{colors.YELLOW}  • Or run 'deploy --config-file <config_file>' with a custom config{colors.RESET}\n")
        return False

    endpoint_check = check_deployment(include_endpoints=True)
    if not endpoint_check.ok:
        logger.error("OpenStack deployed but services not fully operational.")
        print(f"{colors.RED}OpenStack is deployed but services are not fully operational:{colors.RESET}")
        print(endpoint_check)
        return False

    logger.info("OpenStack is ready.")
    return True

def mark_deployment_complete():
    logger.info(f"Marking deployment as complete in '{MARKER_FILE}'.")
    os.makedirs(os.path.dirname(MARKER_FILE), exist_ok=True)
    with open(MARKER_FILE, "w") as f:
        f.write(f"Deployment completed at {time.ctime()}\n")