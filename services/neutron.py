# Configure the Networking service (Neutron) with OVS bridges

from ..utils.core.commands import run_command, run_sync_command_with_retry, run_command_sync, run_command_output
from ..utils.apt.apt import apt_install, apt_update
from ..utils.config.parser import parse_config, get, resolve_vars
from ..utils.config.setter import set_conf_option
from ..utils import colors

import os
import shutil

import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
openvswitch_bridges_interfaces_template_file = os.path.join(BASE_DIR, "templates/openvswitch_bridges_interfaces.tpl")

neutron_conf="/etc/neutron/neutron.conf"
conf_ml2="/etc/neutron/plugins/ml2/ml2_conf.ini"
conf_openvswitch="/etc/neutron/plugins/ml2/openvswitch_agent.ini"
conf_dhcp_agent="/etc/neutron/dhcp_agent.ini"
conf_metadata_agent="/etc/neutron/metadata_agent.ini"
conf_l3_agent="/etc/neutron/l3_agent.ini"
conf_nova="/etc/nova/nova.conf"

def install_pkgs():

    apt_update()

    openvswitch_packages = ["neutron-server", "neutron-plugin-ml2", "neutron-openvswitch-agent", "neutron-dhcp-agent", "neutron-metadata-agent", "neutron-l3-agent", "openvswitch-switch"]

    if not apt_install(openvswitch_packages, ux_text=f"Installing Neutron packages...") : return False

    return True

def conf_openvswitch_bridges(config):

    print()
      
    INTERFACES_FILE = "/etc/network/interfaces.d/openvswitch"

    public_iface = get(config, "bridge.PUBLIC_BRIDGE_INTERFACE")
    public_bridge = get(config, "bridge.PUBLIC_BRIDGE")
    internal_bridge = get(config, "bridge.INTERNAL_BRIDGE")

    ip_address =  get(config, "network.HOST_IP")
    ip_address_netmask = get(config, "network.HOST_IP_NETMASK")

    subnet_address_gateway = get(config, "public_network.PUBLIC_SUBNET_GATEWAY")
    subnet_address_dns_servers = get(config, "public_network.PUBLIC_SUBNET_DNS_SERVERS")

    check_cmd = ["ip", "link", "show", public_iface]
    if run_command(check_cmd, f"Checking if interface {public_iface} exists", ignore_errors=True):
        run_command(["ip", "addr", "flush", "dev", public_iface], f"Flushing IPs on {public_iface}")
        run_command(["ip", "link", "set", public_iface, "down"], f"Bringing {public_iface} down")

    check_cmd = ["ip", "link", "show", public_bridge]
    if run_command(check_cmd, f"Checking if bridge {public_bridge} exists", ignore_errors=True):
        run_command(["ip", "addr", "flush", "dev", public_bridge], f"Flushing IPs on {public_bridge}")
        run_command(["ip", "link", "set", public_bridge, "down"], f"Bringing {public_bridge} down")

    # INTERNAL_BRIDGE
    check_cmd = ["ip", "link", "show", internal_bridge]
    if run_command(check_cmd, f"Checking if bridge {internal_bridge} exists", ignore_errors=True):
        run_command(["ip", "link", "set", internal_bridge, "down"], f"Bringing {internal_bridge} down")
    
        run_command(
        ["ovs-vsctl", "--if-exists", "del-port", public_bridge, public_iface],
        f"Deleting port {public_iface} from bridge {public_bridge} if exists",
        ignore_errors=True
    )
        
    print()

    run_command(
        ["ovs-vsctl", "--if-exists", "del-br", public_bridge],
        f"Deleting bridge {public_bridge} if exists",
        ignore_errors=True
    )

    run_command(
        ["ovs-vsctl", "--if-exists", "del-br", internal_bridge],
        f"Deleting bridge {internal_bridge} if exists",
        ignore_errors=True
    )

    print()

    with open(openvswitch_bridges_interfaces_template_file, "r") as f:
        template = f.read()

    bridges_interfaces_content = template.format(
        public_iface=public_iface,
        public_bridge=public_bridge,
        ip_address=ip_address,
        ip_address_netmask=ip_address_netmask,
        subnet_address_gateway=subnet_address_gateway,
        subnet_address_dns_servers=subnet_address_dns_servers,
        internal_bridge=internal_bridge
    )

    with open(INTERFACES_FILE, "w") as f:
     f.write(bridges_interfaces_content)
        
    interfaces_dir = "/etc/network/interfaces.d/"
    backup_dir = "/root/net-backup"
    os.makedirs(backup_dir, exist_ok=True)

    for f in os.listdir(interfaces_dir):
        full_path = os.path.join(interfaces_dir, f)
        backup_path = os.path.join(backup_dir, f)

        if full_path != INTERFACES_FILE and os.path.isfile(full_path):

            if os.path.exists(backup_path):
                os.remove(backup_path)

            shutil.move(full_path, backup_path)

    print()

    run_command(["ovs-vsctl", "--may-exist", "add-br", public_bridge], f"Adding bridge {public_bridge}")
    run_command(["ovs-vsctl", "--may-exist", "add-port", public_bridge, public_iface], f"Adding port {public_iface} to {public_bridge}")

    print()

    run_command(["ip", "link", "set", public_iface, "up"], f"Bringing interface {public_iface} up")
    run_command(["ip", "link", "set", public_bridge, "up"], f"Bringing bridge {public_bridge} up")

    run_command(["ovs-vsctl", "--may-exist", "add-br", internal_bridge], f"Adding bridge {internal_bridge}")
    run_command(["ip", "link", "set", internal_bridge, "up"], f"Bringing bridge {internal_bridge} up")

    print()

    networking_restart_cmds = [
        "systemctl disable systemd-networkd",
        "systemctl stop systemd-networkd",
        "systemctl enable networking",
        "systemctl restart networking",
    ]

    full_networking_restart_cmds = " ; ".join(networking_restart_cmds)

    full_networking_restart_cmds_result = run_command(["bash", "-c", full_networking_restart_cmds], "Restarting Networking service...")

    if not full_networking_restart_cmds_result: return False

    return True

def conf_neutron(config):

    database_password = get(config, "passwords.DATABASE_PASSWORD")
    rabbitmq_password = get(config, "passwords.RABBITMQ_PASSWORD")

    service_password = get(config, "passwords.SERVICE_PASSWORD")

    ip_address = get(config, "network.HOST_IP")

    public_bridge = get(config, "bridge.PUBLIC_BRIDGE")
    internal_bridge = get(config, "bridge.INTERNAL_BRIDGE")
     
    set_conf_option(neutron_conf, "database", "connection", f"mysql+pymysql://neutron:{database_password}@{ip_address}/neutron")

    set_conf_option(neutron_conf, "DEFAULT", "core_plugin", "ml2")
    set_conf_option(neutron_conf, "DEFAULT", "transport_url", f"rabbit://openstack:{rabbitmq_password}@{ip_address}")
    set_conf_option(neutron_conf, "DEFAULT", "auth_strategy", "keystone")
    set_conf_option(neutron_conf, "DEFAULT", "service_plugins", "router")
    set_conf_option(neutron_conf, "DEFAULT", "notify_nova_on_port_status_changes", "true")
    set_conf_option(neutron_conf, "DEFAULT", "notify_nova_on_port_data_changes", "true")

    set_conf_option(neutron_conf, "keystone_authtoken", "www_authenticate_uri", f"http://{ip_address}:5000")
    set_conf_option(neutron_conf, "keystone_authtoken", "auth_url", f"http://{ip_address}:5000")
    set_conf_option(neutron_conf, "keystone_authtoken", "memcached_servers", "127.0.0.1:11211")
    set_conf_option(neutron_conf, "keystone_authtoken", "auth_type", "password")
    set_conf_option(neutron_conf, "keystone_authtoken", "project_domain_name", "default")
    set_conf_option(neutron_conf, "keystone_authtoken", "user_domain_name", "default")
    set_conf_option(neutron_conf, "keystone_authtoken", "project_name", "service")
    set_conf_option(neutron_conf, "keystone_authtoken", "username", "neutron")
    set_conf_option(neutron_conf, "keystone_authtoken", "password", service_password)

    set_conf_option(neutron_conf, "nova", "auth_url", f"http://{ip_address}:5000")
    set_conf_option(neutron_conf, "nova", "auth_type", "password")
    set_conf_option(neutron_conf, "nova", "project_domain_name", "default")
    set_conf_option(neutron_conf, "nova", "user_domain_name", "default")
    set_conf_option(neutron_conf, "nova", "region_name", "RegionOne")
    set_conf_option(neutron_conf, "nova", "project_name", "service")
    set_conf_option(neutron_conf, "nova", "username", "nova")
    set_conf_option(neutron_conf, "nova", "password", service_password)

    set_conf_option(neutron_conf, "oslo_concurrency", "lock_path", "/var/lib/neutron/tmp")

    set_conf_option(conf_ml2, "ml2", "type_drivers", "flat,vlan,local")
    set_conf_option(conf_ml2, "ml2", "tenant_network_types", "flat,vlan,local")
    set_conf_option(conf_ml2, "ml2", "extension_drivers", "port_security")
    set_conf_option(conf_ml2, "ml2_type_flat", "flat_networks", "public,internal")
    set_conf_option(conf_ml2, "securitygroup", "enable_ipset", "true")
    set_conf_option(conf_ml2, "ml2", "mechanism_drivers", "openvswitch")

    set_conf_option(conf_openvswitch, "ovs", "integration_bridge", "br-int")
    set_conf_option(conf_openvswitch, "ovs", "bridge_mappings", f"public:{public_bridge},internal:{internal_bridge}")
    set_conf_option(conf_openvswitch, "securitygroup", "enable_security_group", "true")
    set_conf_option(conf_openvswitch, "securitygroup", "firewall_driver", "openvswitch")

    set_conf_option(conf_dhcp_agent, "DEFAULT", "interface_driver", "neutron.agent.linux.interface.OVSInterfaceDriver")
    set_conf_option(conf_dhcp_agent, "DEFAULT", "dhcp_driver", "neutron.agent.linux.dhcp.Dnsmasq")
    set_conf_option(conf_dhcp_agent, "DEFAULT", "enable_isolated_metadata", "true")

    set_conf_option(conf_metadata_agent, "DEFAULT", "nova_metadata_host", ip_address)
    set_conf_option(conf_metadata_agent, "DEFAULT", "metadata_proxy_shared_secret", service_password)

    set_conf_option(conf_l3_agent, "DEFAULT", "interface_driver", "neutron.agent.linux.interface.OVSInterfaceDriver")
    set_conf_option(conf_l3_agent, "DEFAULT", "external_network_bridge", "")
    set_conf_option(conf_l3_agent, "DEFAULT", "use_namespaces", "true")
    set_conf_option(conf_l3_agent, "DEFAULT", "debug", "true")

    set_conf_option(conf_nova, "neutron", "auth_url", f"http://{ip_address}:5000")
    set_conf_option(conf_nova, "neutron", "auth_type", "password")
    set_conf_option(conf_nova, "neutron", "project_domain_name", "default")
    set_conf_option(conf_nova, "neutron", "user_domain_name", "default")
    set_conf_option(conf_nova, "neutron", "region_name", "RegionOne")
    set_conf_option(conf_nova, "neutron", "project_name", "service")
    set_conf_option(conf_nova, "neutron", "username", "neutron")
    set_conf_option(conf_nova, "neutron", "password", service_password)
    set_conf_option(conf_nova, "neutron", "service_metadata_proxy", "true")
    set_conf_option(conf_nova, "neutron", "metadata_proxy_shared_secret", service_password)

    if not os.path.exists("/etc/neutron/plugin.ini"):
        os.symlink(conf_ml2, "/etc/neutron/plugin.ini")

    neutron_db_migration_cmd = [
    "sudo", "-u", "neutron",
    "neutron-db-manage", "--config-file", neutron_conf,  "--config-file", conf_ml2, "upgrade", "head"
]
    
    if not run_command(neutron_db_migration_cmd, "Running Neutron DB Migrations...") : return False

    return True

def finalize():
           
    print()

    if not run_command(["systemctl", "restart", "nova-api"], "Restarting Nova API service...", False, None, 3, 5): return False
    
    if not run_command(["systemctl", "restart", "neutron-server", "neutron-openvswitch-agent", "neutron-dhcp-agent", "neutron-metadata-agent", "neutron-l3-agent", "nova-compute"], "Restarting Neutron services...", False, None, 3, 5): return False

    return True

def create_networks(config):
     
    print()
    
    ip_address = get(config, "network.HOST_IP")

    admin_password = get(config, "passwords.ADMIN_PASSWORD")

    public_subnet_range_start = get(config, "public_network.PUBLIC_SUBNET_RANGE_START")
    public_subnet_range_end = get(config, "public_network.PUBLIC_SUBNET_RANGE_END")

    public_subnet_gateway = get(config, "public_network.PUBLIC_SUBNET_GATEWAY")
     
    public_subnet_dns_servers = get(config, "public_network.PUBLIC_SUBNET_DNS_SERVERS")

    public_subnet_cidr = get(config, "public_network.PUBLIC_SUBNET_CIDR")    

    os.environ["OS_USERNAME"] = "admin"
    os.environ["OS_PASSWORD"] = admin_password
    os.environ["OS_PROJECT_NAME"] = "admin"
    os.environ["OS_USER_DOMAIN_NAME"] = "Default"
    os.environ["OS_PROJECT_DOMAIN_NAME"] = "Default"
    os.environ["OS_AUTH_URL"] = f"http://{ip_address}:5000/v3"
    os.environ["OS_IDENTITY_API_VERSION"] = "3"

    run_command_sync(["openstack", "subnet", "delete", "public_subnet"])
    run_command_sync(["openstack", "subnet", "delete", "internal_subnet"])

    run_command_sync(["openstack", "network", "delete", "public"])
    run_command_sync(["openstack", "network", "delete", "internal"])

    run_command(
        ["openstack", "network", "create", "--share", "--external",
         "--provider-physical-network", "public",
         "--provider-network-type", "flat", "public"],
        "Creating public network...",
        ignore_errors=True)

    run_command(
        ["openstack", "subnet", "create", "--network", "public",
         "--allocation-pool", f"start={public_subnet_range_start},end={public_subnet_range_end}",
         "--dns-nameserver", public_subnet_dns_servers,
         "--gateway", public_subnet_gateway,
         "--subnet-range", public_subnet_cidr,
         "public_subnet"],
        "Creating public subnet...",
        ignore_errors=True)
    
    print()

    run_command(
        ["openstack", "network", "create", "--share",
            "--provider-physical-network", "internal",
            "--provider-network-type", "flat", "internal"],
        "Creating internal network...",
        ignore_errors=True)

    run_command(
        ["openstack", "subnet", "create", "--network", "internal",
         "--subnet-range", "10.0.0.0/24",
         "--gateway", "10.0.0.1",
         "--allocation-pool", "start=10.0.0.10,end=10.0.0.200",
         "--dns-nameserver", "8.8.8.8",
         "internal_subnet"],
        "Creating internal subnet...",
        ignore_errors=True)
    
    print()

    run_command_sync(["openstack", "router", "remove", "subnet", "internal_router", "internal_subnet"])
    run_command_sync(["openstack", "router", "delete", "internal_router"])

    run_command(
        ["openstack", "router", "create", "internal_router"],
        "Creating internal router...",
        ignore_errors=True)
         

    run_command(
        ["openstack", "router", "set", "internal_router", "--external-gateway", "public"],
        "Setting external gateway for internal router...",
        ignore_errors=True)
    
    print()

    run_command(
        ["openstack", "router", "add", "subnet", "internal_router", "internal_subnet"],
        "Adding internal subnet to router...",
        ignore_errors=True)
    
    print()

    sg_list_json = run_command_output(["openstack", "security", "group", "list", "-f", "json"])
    sg_list = json.loads(sg_list_json)

    matching_sgs = [sg for sg in sg_list if sg["Name"] == "default"]
    if not matching_sgs:
        raise RuntimeError("No security group named 'default' found")
    sg_id = matching_sgs[0]["ID"]

    rules_json = run_command_output(["openstack", "security", "group", "rule", "list", sg_id, "-f", "json"])
    rules = json.loads(rules_json)

    ssh_rule_exists = any(
        rule.get("protocol") == "tcp" and 
        (rule.get("port_range") == "22" or
        (rule.get("port_range_min") == 22 and rule.get("port_range_max") == 22))
        for rule in rules
    )

    if not ssh_rule_exists:
        run_command(
            ["openstack", "security", "group", "rule", "create",
            "--proto", "tcp",
            "--dst-port", "22",
            "--remote-ip", public_subnet_cidr,
            sg_id],
            "Allowing SSH access...")
    else:
        print(f"{colors.YELLOW}The SSH rule already exists, skipping this step{colors.RESET}")

    return True

def run_setup_neutron(config):
     
     config_openvswitch_bridges = get(config, "bridge.CREATE_BRIDGES", "no") == "yes"

     if not install_pkgs(): return False
     
     if config_openvswitch_bridges:
        if not conf_openvswitch_bridges(config) : return False
        
     if not conf_neutron(config) : return False
     
     if not finalize() : return False
     
     if not create_networks(config): return False
     
     print(f"\n{colors.GREEN}Neutron configured successfully!{colors.RESET}\n")
     return True
