
import random
import string

import subprocess

def has_hw_virtualization():
    try:
        with open("/proc/cpuinfo") as f:
            cpuinfo = f.read()

        cpu_support = ("vmx" in cpuinfo) or ("svm" in cpuinfo)

        kvm_available = False
        try:
            open("/dev/kvm").close()
            kvm_available = True
        except:
            pass

        return cpu_support and kvm_available

    except:
        return False

def get_free_loop():
    loop = subprocess.check_output(["losetup", "-f"]).decode().strip()
    return loop

def generate_password(length=12):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))
