
import os

from ....utils.core.commands import run_command

def enable_ipv4_forwarding() -> bool:
    with open("/proc/sys/net/ipv4/ip_forward") as f:
        ip_forward = int(f.read().strip())

    if ip_forward != 1:

        if not run_command(
            ["sysctl", "-w", "net.ipv4.ip_forward=1"],
            "Enabling IPv4 IP Forwarding..."
        ):
            return False

    sysctl_file = "/etc/sysctl.d/99-openstack-forwarding.conf"

    if not os.path.exists(sysctl_file):
        with open(sysctl_file, "w") as f:
            f.write("net.ipv4.ip_forward = 1\n")

    print()

    return True
