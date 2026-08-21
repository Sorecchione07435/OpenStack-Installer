def get_base_host(config):
    ip = config.get("network", {}).get("HOST_IP")
    domain = config.get("network", {}).get("HOST_DOMAIN") or None
    return domain or ip