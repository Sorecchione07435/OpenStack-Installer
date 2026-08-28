import re

from ..utils.core.commands import run_command_output

def get_base_host(config):
    ip = config.get("network", {}).get("HOST_IP")
    domain = config.get("network", {}).get("HOST_DOMAIN") or None
    return domain or ip

def validate_os_release_available(release_name: str) -> bool:
    policy_output = run_command_output(["apt-cache", "policy", "keystone"])

    release_name = release_name.lower()

    candidate_match = re.search(
        r"Candidate:\s*(?P<version>\S+)",
        policy_output,
        re.MULTILINE,
    )

    if not candidate_match:
        return False

    candidate_version = candidate_match.group("version")

    pattern = re.compile(
        rf"^\s*{re.escape(candidate_version)}\s+\d+\s*$\n"
        rf"\s+\d+\s+\d+\s+\S+/{re.escape(release_name)}/\S+",
        re.MULTILINE,
    )

    return pattern.search(policy_output) is not None
