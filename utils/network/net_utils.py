import psutil
import socket
import ipaddress
import subprocess

def is_wifi_interface(iface: str) -> bool:
    try:
        with open(f"/sys/class/net/{iface}/type") as f:
            return f.read().strip() == "801"
    except Exception:
        return False

def get_default_interface_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Non serve che sia raggiungibile davvero
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip

def netmask_to_cidr(netmask):
    return ipaddress.IPv4Network(f"0.0.0.0/{netmask}").prefixlen

def get_active_interface():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()

    for iface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == socket.AF_INET and addr.address == ip:
                return iface, ip
            

def get_network_info():
    # Trova IP dell'interfaccia di default
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()

    iface_name = None
    netmask = None
    broadcast = None
    cidr = None
    gateway = None
    network_cidr = None  # IP + CIDR
    network = None       # Network completo tipo 192.168.1.0/24

    # Trova interfaccia e netmask
    for iface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == socket.AF_INET and addr.address == ip:
                iface_name = iface
                netmask = addr.netmask
                broadcast = addr.broadcast
                if netmask:
                    # CIDR numerico
                    cidr = ipaddress.IPv4Network(f"0.0.0.0/{netmask}").prefixlen
                    # IP + CIDR
                    network_cidr = f"{ip}/{cidr}"
                    # Network completo (subnet)
                    network = str(ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False))

    # Trova gateway
    route = subprocess.check_output("ip route", shell=True).decode()
    for line in route.splitlines():
        if line.startswith("default"):
            gateway = line.split()[2]

    return iface_name, ip, netmask, cidr, broadcast, gateway, network_cidr, network