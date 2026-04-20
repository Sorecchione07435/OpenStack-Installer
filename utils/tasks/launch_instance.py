import subprocess
import os
import sys
import time
import logging
import uuid
import shutil
import base64
import crypt
import secrets
from pathlib import Path

from ..core import colors

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2] 

linux_yaml_cloud_config_template_file_path = os.path.join(BASE_DIR, "templates/cloud-config/linux.yaml")
linux_no_root_yaml_cloud_config_template_file_path = os.path.join(BASE_DIR, "templates/cloud-config/linux_no_root.yaml")

SSH_KEY_PATH = os.path.expanduser("~/.ssh/")
DEFAULT_FLAVOR  = "m1.tiny"
DEFAULT_IMAGE   = "cirros"
DEFAULT_NETWORK = "internal"
EXTERNAL_NET    = "public"

def _run(args: list[str], check=True) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            args, capture_output=True, text=True, timeout=60, check=check
        )
    except FileNotFoundError:
        logger.error("'openstack' CLI not found in PATH")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout executing: {' '.join(args)}")
        sys.exit(1)


def _os(*args) -> str:
    result = _run(["openstack"] + list(args))
    return result.stdout.strip()


def _os_value(*args) -> str:
    result = _run(["openstack"] + list(args) + ["-f", "value"])
    return result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""

def ensure_keypair(key_path: str = SSH_KEY_PATH, name: str = None) -> str:

    keypair_name = f"{name}-keypair"

    # Local key
    if not os.path.isfile(key_path):
        print(f"Creating local '{keypair_name}' ssh key at {key_path}")
        subprocess.run(
            ["ssh-keygen", "-t", "rsa", "-b", "2048", "-N", "", "-f", key_path],
            check=True, stdout=subprocess.DEVNULL
        )
    else:
        print(f"SSH key already exists: {key_path}")

    pub_key_path = key_path + ".pub"

    existing = _os("keypair", "list", "-f", "value", "-c", "Name")
    if keypair_name not in existing.splitlines():
        print(f"Registering keypair '{keypair_name}' in OpenStack ...")
        _os("keypair", "create", "--public-key", pub_key_path, keypair_name)
    else:
        print(f"Keypair '{keypair_name}' already exists in OpenStack")

    return keypair_name

def get_image_properties(image_id: str) -> dict:
    import json

    out = _os("image", "show", image_id, "-f", "json")
    data = json.loads(out)

    props = data.get("properties") or {}

    return {
        "name": data.get("name"),
        "os_distro": props.get("os_distro", "").lower(),
        "os_type": props.get("os_type", "").lower(),
        "os_version": props.get("os_version"),
        "os_admin_user": props.get("os_admin_user")
    }

def get_default_image(preferred: str = DEFAULT_IMAGE) -> str:

    out = _os("image", "list", "--status", "active", "-f", "value", "-c", "ID", "-c", "Name")
    for line in out.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2 and preferred.lower() in parts[1].lower():
            return parts[0]
    # fallback: first available image
    first = out.splitlines()[0].split()[0] if out else None
    if not first:
        logger.error("No images found. Upload one first using: openstack image create")
        sys.exit(1)
    return first


def get_default_flavor(preferred: str = DEFAULT_FLAVOR) -> str:
    out = _os("flavor", "list", "-f", "value", "-c", "ID", "-c", "Name")
    for line in out.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2 and preferred.lower() in parts[1].lower():
            return parts[0]
    return out.splitlines()[0].split()[0] if out else "1"


def get_default_network(preferred: str | None = None) -> str:

    out = _os("network", "list", "-f", "value", "-c", "ID", "-c", "Name")
    lines = [line.split(None, 1) for line in out.splitlines() if line.strip()]

    if preferred:
        for net_id, net_name in lines:
            if preferred.lower() in net_name.lower():
                if "public" in net_name.lower():
                    logger.warning("Cannot use public network by default; falling back to internal")
                    break
                return net_id

    for net_id, net_name in lines:
        if "internal" in net_name.lower():
            return net_id

    for net_id, net_name in lines:
        if "public" not in net_name.lower():
            return net_id

    logger.error("No suitable internal network found. Cannot use public network by default.")
    sys.exit(1)


def generate_user_config(ostype: str, default_user: str, password: str, public_key: str = None) -> str:
   
    linux_config_drive = ""
    password_b64 = base64.b64encode(password.encode('utf-16-le')).decode('ascii')

    windows_config_drive = f"""<powershell>
    $username = "{default_user}"
    $passwordB64 = "{password_b64}"

    $bytes = [System.Convert]::FromBase64String($passwordB64)
    $password = [System.Text.Encoding]::Unicode.GetString($bytes)
    $secure = ConvertTo-SecureString $password -AsPlainText -Force
    Set-LocalUser -Name $username -Password $secure
    Set-LocalUser -Name $username -PasswordNeverExpires $true
    Enable-LocalUser -Name $username
    </powershell>
    """

    salt = crypt.mksalt(crypt.METHOD_SHA512)
    password_hash = crypt.crypt(password, salt)

    template_path = linux_no_root_yaml_cloud_config_template_file_path if default_user != "root" else linux_yaml_cloud_config_template_file_path

    with open(template_path, "r") as f:
        template = f.read()
        linux_config_drive = template.format(
            default_user=default_user,
            password_hash=password_hash,
            public_key=public_key,
        )

    code = uuid.uuid4().hex
    base_path = f"/tmp/config_drive_{code}"
    openstack_path = os.path.join(base_path, "openstack", "latest")

    os.makedirs(openstack_path, exist_ok=True)

    ostype = (ostype or "").lower()

    if (ostype or "").lower() == "windows":
        content = windows_config_drive
    elif ostype == "linux":
        content = linux_config_drive
    else:
        raise ValueError("ostype must be 'windows' or 'linux'")

    file_path = os.path.join(openstack_path, "user_data")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return file_path
    

def create_server(name: str, image_id: str, flavor_id: str,
                  network_id: str, keypair_name: str) -> str:

    print(f"Launching instance '{name}' ...\n")

    result = _run([
        "openstack", "server", "create",
        "--image",   image_id,
        "--flavor",  flavor_id,
        "--network", network_id,
        "--key-name", keypair_name,
        "--wait",
        "-f", "value", "-c", "id",
        name
    ])
    server_id = result.stdout.strip()
    if not server_id:
        logger.error("Server creation failed:\n" + result.stderr)
        sys.exit(1)
    return server_id

def create_server_with_password(
    name: str,
    image_id: str,
    flavor_id: str,
    network_id: str,
    keypair_name: str,
    os_type: str,
    username: str,
    password: str,
    public_key: str = None,
) -> str:

    config_drive_file_path = generate_user_config(os_type, username, password)

    print(f"\nLaunching instance '{name}' ...\n")

    try:
        result = _run([
            "openstack", "server", "create",
            "--image", image_id,
            "--flavor", flavor_id,
            "--network", network_id,
            "--key-name", keypair_name,
            "--config-drive", "true",
            "--user-data", config_drive_file_path,
            "--wait",
            "-f", "value",
            "-c", "id",
            name
        ])

        server_id = result.stdout.strip()

        if not server_id:
            logger.error("Server creation failed:\n" + result.stderr)
            sys.exit(1)

        return server_id

    finally:
        if os.path.exists(config_drive_file_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(config_drive_file_path)))
            shutil.rmtree(base_dir, ignore_errors=True)

def allocate_floating_ip(external_net: str = EXTERNAL_NET) -> str:
    print("Allocating floating IP ...")
    fip = _os_value("floating", "ip", "create", "-c", "floating_ip_address", external_net)
    if not fip:
        logger.error("Unable to allocate floating IP")
        sys.exit(1)
    return fip


def attach_floating_ip(server_name: str, fip: str) -> None:
    print(f"Attaching floating IP {fip} to the instance ...\n")
    _os("server", "add", "floating", "ip", server_name, fip)

def wait_for_active(server_id: str, timeout: int = 120) -> None:

    deadline = time.time() + timeout
    while time.time() < deadline:
        status = _os_value("server", "show", server_id, "-c", "status")
        if status == "ACTIVE":
            return
        if status == "ERROR":
            logger.error(f"Server {server_id} is in ERROR state")
            sys.exit(1)
        time.sleep(5)
    logger.warning(f"Server {server_id} not ACTIVE after {timeout}s")


def print_summary(name: str, fip: str, key_path: str, is_password: bool,
                  username: str, password: str, os_type: str) -> None:

    os_type = (os_type or "").lower()

    print(f"{colors.GREEN}Instance '{name}' successfully started{colors.RESET}\n")
    print(f"Attached Floating IP : {fip}\n")

    if os_type == "linux":
        ssh_cmd = f"ssh -i {key_path} {username}@{fip}"
        print(f"You can connect to the instance with:\n  {ssh_cmd}\n")

    elif os_type == "windows":
        print(f"You can connect via RDP to: {fip}\n")
        print(
            f"{colors.YELLOW}IMPORTANT: ensure that a security group rule is configured "
            f"to allow inbound TCP port 3389 (RDP) from your public IP or network."
            f"{colors.RESET}\n"
        )

    if is_password:
        print(
            f"You can log in with credentials:\n"
            f"  username: {username}\n"
            f"  password: {password}"
        )

def launch(
    name: str           = "cirros-instance",
    image: str          = DEFAULT_IMAGE,
    flavor: str         = DEFAULT_FLAVOR,
    network: str        = DEFAULT_NETWORK,
    key_path: str       = SSH_KEY_PATH,
    external_net: str   = EXTERNAL_NET,
    password: str       = ""
) -> None:

    os.makedirs(SSH_KEY_PATH, exist_ok=True)
    key_path = os.path.join(SSH_KEY_PATH, f"id_{name}")

    keypair = ensure_keypair(key_path, name)

    image_id   = get_default_image(image)
    flavor_id  = get_default_flavor(flavor)
    network_id = get_default_network(network)

    props = get_image_properties(image_id) or {}

    os_type = (props.get("os_type") or "").lower()
    os_distro = (props.get("os_distro") or "").lower()
    image_name = (props.get("name") or "").lower()
    os_admin_user = (props.get("os_admin_user") or "")

    password_enabled = True

    with open(f"{key_path}.pub", "r") as f:
        public_key = f.read().strip()

    if "cirros" in image_name:
        password_enabled = False
        print(f"{colors.YELLOW}Info: CirrOS detected. Skipping password configuration (unsupported image).{colors.RESET}\n")

    elif not os_type or not os_distro:
        password_enabled = False
        print(f"{colors.YELLOW}Warning: Missing image metadata. Skipping password configuration for safety.{colors.RESET}\n")

    if password_enabled and password:
        server_id = create_server_with_password(
            name,
            image_id,
            flavor_id,
            network_id,
            keypair,
            os_type,
            os_admin_user,
            password,
            public_key
        )
    else:
        server_id = create_server(
            name,
            image_id,
            flavor_id,
            network_id,
            keypair
        )
    
    wait_for_active(server_id)

    fip = allocate_floating_ip(external_net)

    attach_floating_ip(name, fip)

    if password_enabled and password:
        print_summary(name, fip, key_path, True, os_admin_user, password, os_type)
    elif  "cirros" in image_name:
         print_summary(name, fip, key_path, False, "cirros", None, "linux")
    else:
         print_summary(name, fip, key_path, False, os_admin_user, None, os_type)
    