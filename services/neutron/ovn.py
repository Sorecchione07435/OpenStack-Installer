# Configure the Open Virtual Network (OVN) Driver for Neutron

from ...utils.core.commands import run_command, run_sync_command_with_retry, run_command_sync, run_command_output
from ...utils.apt.apt import apt_install, apt_update
from ...utils.config.parser import parse_config, get, resolve_vars
from ...utils.config.setter import set_conf_option
from ...utils.core.system_utils import nc_wait
from ...utils.core import colors

import os
import shutil
import json

current_dir = os.path.dirname(os.path.abspath(__file__)) 

BASE_DIR = os.path.dirname(os.path.dirname(current_dir))  

ovn_bridges_interfaces_template_file = os.path.join(BASE_DIR, "templates", "ovn_bridges_interfaces.tpl")

neutron_conf = "/etc/neutron/neutron.conf"
conf_ml2 = "/etc/neutron/plugins/ml2/ml2_conf.ini"
conf_metadata_agent = "/etc/neutron/metadata_agent.ini"
conf_nova = "/etc/nova/nova.conf"

def install_pkgs():

    print()

    ovn_packages = [
        "neutron-metadata-agent",   # still needed for VM metadata (Nova)
        "ovn-central",              # ovn-northd + NB/SB ovsdb-server
        "ovn-host",                 # ovn-controller on compute nodes
        "ovn-common",               # ovn-nbctl, ovn-sbctl tools
        "openvswitch-switch",       # OVS dataplane (required by OVN)
    ]

    if not apt_install(ovn_packages, ux_text="Installing Neutron OVN packages..."):
        return False

    return True

def conf_ovn_bridges(config):

    print()

    INTERFACES_FILE = "/etc/network/interfaces.d/openvswitch"

    public_iface = get(config, "neutron.ovn.OVN_PUBLIC_BRIDGE_INTERFACE")
    public_bridge = get(config, "neutron.ovn.OVN_PUBLIC_BRIDGE")       # e.g. br-ex
    internal_bridge = "br-int"   # e.g. br-int (managed by OVN)

    ip_address = get(config, "network.HOST_IP")
    ip_address_netmask = get(config, "network.HOST_IP_NETMASK")
    subnet_address_gateway = get(config, "public_network.PUBLIC_SUBNET_GATEWAY")
    subnet_address_dns_servers = get(config, "public_network.PUBLIC_SUBNET_DNS_SERVERS")

    # Flush existing interfaces/bridges
    for iface in [public_iface, public_bridge, internal_bridge]:
        check_cmd = ["ip", "link", "show", iface]
        if run_command(check_cmd, f"Checking if {iface} exists", ignore_errors=True):
            run_command(["ip", "addr", "flush", "dev", iface], f"Flushing IPs on {iface}", ignore_errors=True)
            run_command(["ip", "link", "set", iface, "down"], f"Bringing {iface} down", ignore_errors=True)

    run_command(["ovs-vsctl", "--if-exists", "del-port", public_bridge, public_iface],
                f"Removing port {public_iface} from {public_bridge}", ignore_errors=True)
    run_command(["ovs-vsctl", "--if-exists", "del-br", public_bridge],
                f"Deleting bridge {public_bridge}", ignore_errors=True)
    run_command(["ovs-vsctl", "--if-exists", "del-br", internal_bridge],
                f"Deleting bridge {internal_bridge}", ignore_errors=True)

    print()

    # Write network interfaces file
    with open(ovn_bridges_interfaces_template_file, "r") as f:
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

    # Backup other interface files
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

    # Create OVS bridges
    # NOTE: br-int is created and managed automatically by ovn-controller — do NOT create it manually
    run_command(["ovs-vsctl", "--may-exist", "add-br", public_bridge], f"Adding bridge {public_bridge}")
    run_command(["ovs-vsctl", "--may-exist", "add-port", public_bridge, public_iface],
                f"Adding port {public_iface} to {public_bridge}")
    run_command(["ip", "link", "set", public_iface, "up"], f"Bringing {public_iface} up")
    run_command(["ip", "link", "set", public_bridge, "up"], f"Bringing {public_bridge} up")

    print()

    networking_restart_cmds = [
        "systemctl disable systemd-networkd",
        "systemctl stop systemd-networkd",
        "systemctl enable networking",
        "systemctl restart networking",
    ]
    result = run_command(
        ["bash", "-c", " ; ".join(networking_restart_cmds)],
        "Restarting Networking service..."
    )
    if not result:
        return False

    return True

def conf_ovn_controller(config):

    ip_address = get(config, "network.HOST_IP")
    public_bridge = get(config, "neutron.ovn.OVN_PUBLIC_BRIDGE")

    ovn_sb_port = get(config, "neutron.ovn.OVN_SB_PORT")
    ovn_encap_type = get(config, "neutron.ovn.OVN_ENCAP_TYPE")
    
    provider_networks = get(config, "neutron.provider_networks", [])

    flat_networks  = [n["name"] for n in provider_networks if n["type"] == "flat"]
    vlan_networks  = [n["name"] for n in provider_networks if n["type"] == "vlan"]

    bridge_mappings = ",".join(f'{n["name"]}:{n["bridge"]}' for n in provider_networks)

    run_command(
        ["ovs-vsctl", "set", "open", ".",
         f"external-ids:ovn-remote=tcp:{ip_address}:{ovn_sb_port}"],
        "Setting OVN remote (SB DB)"
    )

    run_command(
        ["ovs-vsctl", "set", "open", ".",
         f"external-ids:ovn-encap-type={ovn_encap_type}",
         f"external-ids:ovn-encap-ip={ip_address}"],
        "Setting OVN encap type and IP"
    )

    run_command(
        ["ovs-vsctl", "set", "open", ".",
         f"external-ids:ovn-bridge-mappings={bridge_mappings}"],
        "Setting OVN bridge mappings"
    )

    run_command(
        ["ovs-vsctl", "set", "open", ".",
         "external-ids:ovn-cms-options=enable-chassis-as-gw"],
        "Enabling chassis as OVN gateway"
    )

    return True


def conf_ovn_db_connections(config):
    ip_address = get(config, "network.HOST_IP")

    ovn_sb_port = get(config, "neutron.ovn.OVN_SB_PORT")
    ovn_nb_port = get(config, "neutron.ovn.OVN_NB_PORT")

    run_command_sync(['ovs-vsctl', 'set-manager', 'ptcp:6640:127.0.0.1'])

    run_command(
        ["ovn-nbctl",
         "--db=unix:/var/run/ovn/ovnnb_db.sock",
         "set-connection", f"ptcp:{ovn_nb_port}:{ip_address}", "--",
         "set", "connection", ".", "inactivity_probe=60000"],
        f"Opening NB DB on TCP {ovn_nb_port}"
    )

    run_command(
        ["ovn-sbctl",
         "--db=unix:/var/run/ovn/ovnsb_db.sock",
         "set-connection", f"ptcp:{ovn_sb_port}:{ip_address}", "--",
         "set", "connection", ".", "inactivity_probe=60000"],
        f"Opening SB DB on TCP {ovn_sb_port}"
    )

    return True

def conf_ovn_neutron(config):

    ip_address = get(config, "network.HOST_IP")

    ovn_sb_port = get(config, "neutron.ovn.OVN_SB_PORT")
    ovn_nb_port = get(config, "neutron.ovn.OVN_NB_PORT")

    tenant_network_type = get(config, "neutron.tenant_network.TYPE")
    tenant_network_vni_range = get(config, "neutron.tenant_network.VNI_RANGE")
    
    ovn_l3_scheduler = get(config, "neutron.ovn.OVN_L3_SCHEDULER")

    ovn_public_bridge = get(config, "neutron.ovn.OVN_PUBLIC_BRIDGE")

    provider_networks = get(config, "neutron.provider_networks", [])

    flat_networks  = [n["name"] for n in provider_networks if n["type"] == "flat"]
    vlan_networks  = [n["name"] for n in provider_networks if n["type"] == "vlan"]

    #bridge_mappings = ",".join(f'{n["name"]}:{n["bridge"]}' for n in provider_networks)

    enable_distributed_floating_ip = get(config, "neutron.ovn.ENABLE_DISTRIBUTED_FLOATING_IP", "no") == "yes"

    flat_networks_str = ",".join(flat_networks)

    vlan_networks_str = ",".join(vlan_networks)

    set_conf_option(conf_ml2, "ml2", "mechanism_drivers", "ovn")

    # OVN supports flat, vlan, geneve (geneve is the overlay type for tenant nets)
    set_conf_option(conf_ml2, "ml2", "type_drivers", "flat,vlan,geneve,local")

    # geneve for self-service (tenant) networks; flat/vlan for provider networks
    set_conf_option(conf_ml2, "ml2", "tenant_network_types", tenant_network_type)

    set_conf_option(conf_ml2, "ml2", "extension_drivers", "port_security")

    # Geneve VNI range and header size (OVN requires at least 38)
    set_conf_option(conf_ml2, "ml2_type_geneve", "vni_ranges", tenant_network_vni_range)
    set_conf_option(conf_ml2, "ml2_type_geneve", "max_header_size", "38")

    if flat_networks_str:
        set_conf_option(conf_ml2, "ml2_type_flat", "flat_networks", flat_networks_str)

    if vlan_networks_str:
        set_conf_option(conf_ml2, "ml2_type_vlan", "network_vlan_ranges", vlan_networks_str)


    set_conf_option(conf_ml2, "securitygroup", "enable_ipset", "true")

    # OVN connection settings in ml2_conf.ini [ovn] section
    set_conf_option(conf_ml2, "ovn", "ovn_nb_connection", f"tcp:{ip_address}:{ovn_nb_port}")
    set_conf_option(conf_ml2, "ovn", "ovn_sb_connection", f"tcp:{ip_address}:{ovn_sb_port}")
    set_conf_option(conf_ml2, "ovn", "ovn_l3_mode", "true")
    set_conf_option(conf_ml2, "ovn", "ovn_l3_scheduler", ovn_l3_scheduler)
    set_conf_option(conf_ml2, "ovn", "ovn_metadata_enabled", "true")

    if enable_distributed_floating_ip:
        set_conf_option(neutron_conf, "ovn", "enable_distributed_floating_ip", "true")
    else:
        set_conf_option(neutron_conf, "ovn", "enable_distributed_floating_ip", "false")
    
    set_conf_option(conf_ml2, "ovn", "ovn_bridge_mappings", f"public:{ovn_public_bridge}")

    set_conf_option(conf_nova, "os_vif_ovs", "ovsdb_connection", "unix:/var/run/openvswitch/db.sock")

    set_conf_option(conf_nova, "neutron", "ovs_bridge", "br-int")

    return True

def finalize(config):
    print()

    ip_address = get(config, "network.HOST_IP")

    run_command_sync(["ovs-vsctl", "set-manager",
                      f"ptcp:6640:{ip_address}",
                      "punix:/var/run/openvswitch/db.sock"])
    
    run_command_sync(["chmod", "o+rw", "/var/run/openvswitch/db.sock"])

    if not run_command(["systemctl", "enable", "--now", "ovn-northd"],
                       "Starting ovn-northd...", False, None, 3, 5):
        return False

    if not run_command(["systemctl", "enable", "--now", "ovn-controller"],
                       "Starting ovn-controller...", False, None, 3, 5):
        return False

    if not run_command(["systemctl", "restart", "nova-api"],
                       "Restarting Nova API...", False, None, 3, 5):
        return False

    if not run_command(
        ["systemctl", "restart",
         "neutron-server",
         "neutron-metadata-agent",
         "nova-compute"],
        "Restarting Neutron and Nova services...", False, None, 3, 5
    ):
        return False

    for svc in ["neutron-l3-agent", "neutron-dhcp-agent", "neutron-openvswitch-agent"]:
        run_command(["systemctl", "disable", "--now", svc],
                    f"Disabling legacy agent {svc}", ignore_errors=True)
        
    udev_rule = 'SUBSYSTEM=="unix", ACTION=="add", DEVPATH=="/var/run/openvswitch/db.sock", MODE="0666"\n'
    with open("/etc/udev/rules.d/99-openvswitch.rules", "w") as f:
        f.write(udev_rule)
    run_command_sync(["udevadm", "control", "--reload-rules"])

    if not nc_wait(ip_address, 9696) : return False

    return True

def create_ovn_networks(config):
    print()

    ip_address = get(config, "network.HOST_IP")
    admin_password = get(config, "passwords.ADMIN_PASSWORD")

    public_subnet_range_start = get(config, "public_network.PUBLIC_SUBNET_RANGE_START")
    public_subnet_range_end = get(config, "public_network.PUBLIC_SUBNET_RANGE_END")
    public_subnet_gateway = get(config, "public_network.PUBLIC_SUBNET_GATEWAY")
    public_subnet_dns_servers = get(config, "public_network.PUBLIC_SUBNET_DNS_SERVERS")
    public_subnet_cidr = get(config, "public_network.PUBLIC_SUBNET_CIDR")

    ovn_public_bridge = get(config, "neutron.ovn.OVN_PUBLIC_BRIDGE")

    os.environ["OS_USERNAME"] = "admin"
    os.environ["OS_PASSWORD"] = admin_password
    os.environ["OS_PROJECT_NAME"] = "admin"
    os.environ["OS_USER_DOMAIN_NAME"] = "Default"
    os.environ["OS_PROJECT_DOMAIN_NAME"] = "Default"
    os.environ["OS_AUTH_URL"] = f"http://{ip_address}:5000/v3"
    os.environ["OS_IDENTITY_API_VERSION"] = "3"

    run_command_sync(["openstack", "router", "remove", "subnet", "internal_router", "internal_subnet"])
    run_command_sync(["openstack", "router", "unset", "--external-gateway", "internal_router"])
    run_command_sync(["openstack", "router", "delete", "internal_router"])
    run_command_sync(["openstack", "subnet", "delete", "public_subnet"])
    run_command_sync(["openstack", "subnet", "delete", "internal_subnet"])
    run_command_sync(["openstack", "network", "delete", "public"])
    run_command_sync(["openstack", "network", "delete", "internal"])

    run_command(
        ["openstack", "network", "create",
         "--share", "--external",
         "--provider-physical-network", "public",
         "--provider-network-type", "flat",
         "public"],
        "Creating public network...", ignore_errors=True)

    run_command(
        ["openstack", "subnet", "create",
         "--network", "public",
         "--allocation-pool", f"start={public_subnet_range_start},end={public_subnet_range_end}",
         "--dns-nameserver", public_subnet_dns_servers,
         "--gateway", public_subnet_gateway,
         "--subnet-range", public_subnet_cidr,
         "public_subnet"],
        "Creating public subnet...", ignore_errors=True)

    print()

    run_command(
        ["openstack", "network", "create",
         "--share",
         "--provider-network-type", "geneve",
         "internal"],
        "Creating internal (geneve) network...", ignore_errors=True)

    run_command(
        ["openstack", "subnet", "create",
         "--network", "internal",
         "--subnet-range", "10.0.0.0/24",
         "--gateway", "10.0.0.1",
         "--allocation-pool", "start=10.0.0.10,end=10.0.0.200",
         "--dns-nameserver", "8.8.8.8",
         "internal_subnet"],
        "Creating internal subnet...", ignore_errors=True)

    print()

    run_command(
        ["openstack", "router", "create", "internal_router"],
        "Creating router...", ignore_errors=True)

    run_command(
        ["openstack", "router", "set", "internal_router", "--external-gateway", "public"],
        "Setting external gateway...", ignore_errors=True)

    run_command(
        ["openstack", "router", "add", "subnet", "internal_router", "internal_subnet"],
        "Adding internal subnet to router...", ignore_errors=True)

    print()

    sg_list_json = run_command_output(["openstack", "security", "group", "list", "-f", "json"])
    sg_list = json.loads(sg_list_json)
    matching_sgs = [sg for sg in sg_list if sg["Name"] == "default"]
    if not matching_sgs:
        raise RuntimeError("No security group named 'default' found")
    sg_id = matching_sgs[0]["ID"]

    rules_json = run_command_output(
        ["openstack", "security", "group", "rule", "list", sg_id, "-f", "json"])
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
             "--proto", "tcp", "--dst-port", "22",
             "--remote-ip", "0.0.0.0/0", sg_id],
            "Allowing SSH access...", True)
    else:
        print(f"{colors.YELLOW}SSH rule already exists, skipping{colors.RESET}")

    icmp_rule_exists = any(rule.get("protocol") == "icmp" for rule in rules)
    if not icmp_rule_exists:
        run_command(
            ["openstack", "security", "group", "rule", "create",
             "--proto", "icmp", sg_id],
            "Allowing ICMP (ping)...", True)
    else:
        print(f"{colors.YELLOW}ICMP rule already exists, skipping{colors.RESET}")

    router_gw_ip = run_command_output([
    "openstack", "router", "show", "internal_router",
    "-f", "json"
    ])

    gw_data = json.loads(router_gw_ip)
    gw_ip = gw_data["external_gateway_info"]["external_fixed_ips"][0]["ip_address"]
    
    run_command_sync(["ip", "route", "replace", "10.0.0.0/24", "via", gw_ip, "dev", ovn_public_bridge])

    print()

    if not run_command([
    "neutron-ovn-db-sync-util",
    "--config-file", "/etc/neutron/neutron.conf",
    "--config-file", "/etc/neutron/plugins/ml2/ml2_conf.ini",
    "--ovn-neutron_sync_mode", "repair"
],
    "Resynchronizing the OVN Northd database..."): return False

    if not run_command(
        ["systemctl", "restart",
         "ovn-ovsdb-server-nb",
         "ovn-ovsdb-server-sb",
         "ovn-northd",
         "ovn-controller",
         "neutron-server",
         "nova-compute"],
        "Restarting OVN services...", False, None, 3, 5
    ):  return False

    return True

def run_setup_ovn_neutron(config):

    config_ovn_bridges = get(config, "neutron.ovn.CREATE_BRIDGES", "no") == "yes"

    if not install_pkgs():
        return False

    if config_ovn_bridges:
        if not conf_ovn_bridges(config):
            return False

    if not conf_ovn_neutron(config):
        return False

    # Open TCP ports on OVN DBs before starting neutron-server
    if not conf_ovn_db_connections(config):
        return False

    # Configure ovs-vsctl external-ids for ovn-controller
    if not conf_ovn_controller(config):
        return False

    if not finalize(config):
        return False

    if not create_ovn_networks(config):
        return False

    return True