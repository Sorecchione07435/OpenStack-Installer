import os 

from ....utils.core.commands import run_command_sync
from ....utils.core import colors

manila_lvm_file_path = "/usr/lib/python3/dist-packages/manila/share/drivers/lvm.py"
manila_lvm_loopback_start_script = "/usr/local/bin/manila-loopback-start.sh"

def append_service_patch():
    with open(manila_lvm_loopback_start_script, "r") as f:
        script = f.read()

    script += f"""

# Automatic patching block for OpenStack Manila (Ubuntu Resolute)
python3 -c "
import os
p = '{manila_lvm_file_path}'
if os.path.exists(p):
    code = open(p).read()
    if 'use_direct_io=use_direct_io' in code:
        print('Re-patching Manila Share LVM for direct_io')
        open(p, 'w').write(code.replace('use_direct_io=use_direct_io', 'use_direct_io=False'))
        print('Patch completed successfully')
        os.system('systemctl restart manila-share')
    else:
        print('Patch already present')
"
"""

    with open(manila_lvm_loopback_start_script, "w") as f:
        f.write(script)

    return True

def patch_manila_directio():
    with open(manila_lvm_file_path, "r") as f:
        code = f.read()

    if "use_direct_io=use_direct_io" in code:
        print(f"{colors.YELLOW}Ubuntu Resolute detected, a patch will be applied to Manila Share to force direct_io to be disabled for snapshots to work properly.{colors.RESET}")
        
        new_code = code.replace("use_direct_io=use_direct_io", "use_direct_io=False")

        with open(manila_lvm_file_path, "w") as f:
            f.write(new_code)

        run_command_sync(["systemctl restart manila-share"])

    return True

def run_setup_directio_patch():

    if not patch_manila_directio() : return False

    if not append_service_patch(): return False

    return True


