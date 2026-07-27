import psutil
import socket
import ipaddress
import subprocess

import os

def is_wifi_interface(iface: str) -> bool:
    try:

        type_path = f"/sys/class/net/{iface}/type"
        if os.path.exists(type_path):
            with open(type_path) as f:
                if f.read().strip() == "801":
                    return True

        if os.path.exists(f"/sys/class/net/{iface}/wireless"):
            return True

        with open("/proc/net/wireless") as f:
            wireless_interfaces = [line.split()[0].strip(":") for line in f.readlines()[2:]]
            if iface in wireless_interfaces:
                return True
    except Exception:
        pass
    return False

def get_default_interface_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()

def get_active_interface() -> tuple[str, str]:

    ip = get_default_interface_ip()
    for iface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == socket.AF_INET and addr.address == ip:
                return iface, ip
    return None, None

def get_network_info(interface_name: str = ""):
    interfaces = psutil.net_if_addrs()

    if interface_name:
        iface = interface_name
    else:
        iface, _ = get_active_interface()

    if iface not in interfaces:
        raise ValueError(f"Interface '{iface}' not found")

    ip = None
    netmask = None
    broadcast = None

    for addr in interfaces[iface]:
        if addr.family == socket.AF_INET:
            ip = addr.address
            netmask = addr.netmask
            broadcast = addr.broadcast
            break

    if ip is None:
        raise ValueError(f"No IPv4 address found on interface '{iface}'")

    cidr = (
        ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False).prefixlen
        if netmask else None
    )

    network_cidr = f"{ip}/{cidr}" if cidr else None

    network = (
        str(ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False))
        if netmask else None
    )

    gateway = None
    try:
        route = subprocess.run(
            ["ip", "route"],
            capture_output=True,
            text=True
        )

        for line in route.stdout.splitlines():
            if line.startswith("default") and f"dev {iface}" in line:
                gateway = line.split()[2]
                break

    except Exception:
        pass

    return {
        "interface": iface,
        "ip": ip,
        "netmask": netmask,
        "cidr": cidr,
        "broadcast": broadcast,
        "gateway": gateway,
        "network_cidr": network_cidr,
        "network": network,
        "is_wifi": is_wifi_interface(iface)
    }