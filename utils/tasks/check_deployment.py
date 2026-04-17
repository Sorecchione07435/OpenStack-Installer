import subprocess
import os
import logging
from dataclasses import dataclass, field

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
#logger = logging.get#logger(__name__)

@dataclass
class CheckResult:
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.failed) == 0

    def __str__(self):
        lines = [f"✅ {s}" for s in self.passed] + [f"❌ {s}" for s in self.failed]
        return "\n".join(lines)


def is_package_installed(pkg_name: str) -> bool:
    try:
        result = subprocess.run(
            ["dpkg", "-l", pkg_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return result.returncode == 0
    except FileNotFoundError:
        #logger.error("'dpkg' not found — are you on a Debian-based system?")
        return False


def check_endpoint(service_name: str) -> bool:

    try:
        result = subprocess.run(
            ["openstack", "endpoint", "list", "--service", service_name,
             "-f", "value", "-c", "ID"],
            capture_output=True, text=True, timeout=10
        )
        return bool(result.stdout.strip())
    except FileNotFoundError:
        #logger.error("'openstack' CLI not found in PATH")
        return False
    except subprocess.TimeoutExpired:
        #logger.error(f"Timeout checking endpoint: {service_name}")
        return False


def check_service_active(svc: str) -> bool:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "--quiet", svc],
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        #logger.error(f"Error checking service {svc}: {e}")
        return False


def check_deployment(include_endpoints: bool = True):
    result = CheckResult()

    checks = [
        ("Services", ["apache2", "nova-api", "glance-api", "neutron-server", "cinder-volume"], check_service_active),
        ("Packages", ["apache2", "nova-common", "glance-api", "neutron-server", "cinder-common"], is_package_installed),
        ("Config files", [
            "/etc/keystone/keystone.conf", "/etc/glance/glance-api.conf",
            "/etc/nova/nova.conf", "/etc/neutron/neutron.conf", "/etc/cinder/cinder.conf"
        ], os.path.isfile),
    ]

    # 👇 SOLO se richiesto
    if include_endpoints:
        checks.append(
            ("Endpoints", ["identity", "compute", "image", "network", "volumev3"], check_endpoint)
        )

    for category, items, check_fn in checks:
        for item in items:
            label = f"[{category}] {item}"
            if check_fn(item):
                result.passed.append(label)
            else:
                result.failed.append(label)

    return result

def check_env_variables():
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
            error_msg.append(f"Variabili mancanti: {', '.join(missing)}")
        if empty:
            error_msg.append(f"Variabili vuote: {', '.join(empty)}")

        raise RuntimeError(" | ".join(error_msg))

if __name__ == "__main__":

    outcome = check_deployment(include_endpoints=False)
    print(outcome)

    if not outcome.ok:
        print("\n❌ Problemi nella configurazione base. Skip controllo OpenStack.")
        exit(1)

    try:
        check_env_variables()
        logging.info("Variabili d'ambiente OK")
    except RuntimeError as e:
        logging.error(f"Errore variabili d'ambiente: {e}")
        exit(1)

    endpoint_result = check_deployment(include_endpoints=True)
    print(endpoint_result)

    exit(0 if endpoint_result.ok else 1)