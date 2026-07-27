import json
import time
import pwd
import grp
import subprocess

from .....utils.core.commands import os_run_output
from .....utils.core import colors

def user_in_group(username, groupname):
    try:
        user = pwd.getpwnam(username)
        group = grp.getgrnam(groupname)

        return (
            user.pw_gid == group.gr_gid or
            username in group.gr_mem
        )
    except KeyError:
        return False

def user_exists(username):
    try:
        pwd.getpwnam(username)
        return True
    except KeyError:
        return False

def samba_user_exists(username):
    try:
        result = subprocess.run(
            ["pdbedit", "-L"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return False

    return any(line.partition(":")[0] == username for line in result.stdout.splitlines())


def wait_manila_backend(env, timeout=120, interval=5):
    print("\nWaiting for Share Service to become UP ...", end="", flush=True)

    deadline = time.time() + timeout
    spinner = "|/-\\"
    spinner_index = 0
    last_check = 0

    while time.time() < deadline:
        now = time.time()

        if now - last_check >= interval:
            last_check = now

            try:
                services = json.loads(
                    os_run_output(
                        ["openstack", "share", "service", "list", "-f", "json"],
                        env=env
                    ) or "[]"
                )

                for service in services:
                    if (
                        service.get("Binary", "").lower() == "manila-share"
                        and service.get("Status", "").lower() == "enabled"
                        and service.get("State", "").lower() == "up"
                    ):
                        print(
                            f"\rWaiting for Share Service to become UP "
                            f"[ {colors.YELLOW}DONE{colors.RESET} ]"
                        )
                        return service

            except Exception:
                pass

        print(f"\b{spinner[spinner_index]}", end="", flush=True)
        spinner_index = (spinner_index + 1) % len(spinner)

        time.sleep(0.1)

    print(
        f"\rWaiting for Share Service to become UP "
        f"[ {colors.RED}TIMEOUT{colors.RESET} ]"
    )

    print(
        f"\n{colors.YELLOW}"
        "Check Manila logs for more details:\n"
        "  journalctl -u manila-share -n 100 --no-pager\n"
        "or:\n"
        "  /var/log/manila/manila-share.log"
        f"{colors.RESET}\n"
    )

    return None

def wait_share_available(share_name, env, timeout=120, interval=5):
    print(f"\nWaiting for share '{share_name}' to become available... ", end="", flush=True)

    deadline = time.time() + timeout
    spinner = "|/-\\"
    spinner_index = 0
    last_check = 0
    status = ""

    while time.time() < deadline:
        now = time.time()

        if now - last_check >= interval:
            last_check = now

            try:
                share_info = json.loads(
                    os_run_output(
                        ["openstack", "share", "show", share_name, "-f", "json"],
                        env=env
                    ) or "{}"
                )

                status = share_info.get("status", "").lower()

                if status == "available":
                    print(
                        f"\rWaiting for share '{share_name}' to become available "
                        f"[ {colors.YELLOW}DONE{colors.RESET} ]"
                    )
                    return share_info

                if status in ("error", "error_deleting"):
                    print(
                        f"\rWaiting for share '{share_name}' to become available "
                        f"[ {colors.RED}ERROR{colors.RED} ]"
                        f"\n\n{colors.RED}"
                        f"ERROR: {share_name} entered error state: {status}"
                        f"{colors.RESET}\n"
                    )

                    print(f"{colors.YELLOW}"
                        "Check Manila logs for more details:\n"
                        "  journalctl -u manila-share -n 100 --no-pager\n"
                        "or:\n"
                        "  /var/log/manila/manila-share.log"
                        f"{colors.RESET}\n"
                    )
                    return None

            except Exception:
                pass

        print(f"\b{spinner[spinner_index]}", end="", flush=True)
        spinner_index = (spinner_index + 1) % len(spinner)

        time.sleep(0.1)

    print(
        f"\n{colors.RED}ERROR: {share_name} did not become available "
        f"within {timeout}s (last status: {status}){colors.RESET}"
    )

    return None

def wait_dhss_share_available(share_name, env, timeout=600, interval=10):
    print(f"\nWaiting for share '{share_name}' to become available... ", end="", flush=True)

    deadline = time.time() + timeout
    spinner = "|/-\\"
    spinner_index = 0
    last_check = 0
    status = ""

    while time.time() < deadline:
        now = time.time()

        if now - last_check >= interval:
            last_check = now

            try:
                share_info = json.loads(
                    os_run_output(
                        ["openstack", "share", "show", share_name, "-f", "json"],
                        env=env
                    ) or "{}"
                )

                status = share_info.get("status", "").lower()

                if status == "available":
                    print(f"\rWaiting for share '{share_name}' to become available [ {colors.YELLOW}DONE{colors.RESET} ]")
                    return share_info

                if status in ("error", "error_deleting"):
                    print(
                        f"\rWaiting for share '{share_name}' to become available "
                        f"[ {colors.RED}ERROR{colors.RED} ]"
                    )

                    print(
                        f"{colors.YELLOW}"
                        "Check Manila logs for more details:\n"
                        "  journalctl -u manila-share -n 100 --no-pager\n"
                        "or:\n"
                        "  /var/log/manila/manila-share.log"
                        f"{colors.RESET}\n"
                    )

                    return None

            except Exception:
                pass

        # Spinner aggiornato rapidamente
        print(f"\b{spinner[spinner_index]}", end="", flush=True)
        spinner_index = (spinner_index + 1) % len(spinner)

        time.sleep(0.1)

    print(
        f"\n{colors.RED}"
        f"ERROR: timeout waiting for share '{share_name}' "
        f"(last status: {status})"
        f"{colors.RESET}"
    )

    return None