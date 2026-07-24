import configparser

def add_samba_option(conf_file, option, value):
    with open(conf_file) as f:
        lines = f.readlines()

    out = []
    in_global = False
    inserted = False

    for line in lines:
        if line.strip().lower() == "[global]":
            in_global = True

        elif line.startswith("[") and line.strip() != "[global]":
            if in_global and not inserted:
                out.append(f"{option} = {value}\n")
                inserted = True
            in_global = False

        out.append(line)

    if in_global and not inserted:
        out.append(f"{option} = {value}\n")

    with open(conf_file, "w") as f:
        f.writelines(out)

def set_conf_option(conf_file, section, option, value, interpolation = True):

    config = configparser.ConfigParser(
        interpolation=None if not interpolation else configparser.BasicInterpolation()
    )
    
    config.optionxform = str  # mantiene maiuscole/minuscole
    config.read(conf_file)

    if section not in config:
        config[section] = {}

    config[section][option] = value

    with open(conf_file, "w") as f:
        config.write(f)

def set_service_option(service_file, section, option, value):
    lines = []
    current_section = None
    option_set = False

    with open(service_file, 'r') as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                current_section = stripped[1:-1]
            if current_section == section and stripped.startswith(option + "="):
                line = f"{option}={value}\n"
                option_set = True
            lines.append(line)

    if not option_set:

        new_lines = []
        current_section = None
        for line in lines:
            new_lines.append(line)
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                current_section = stripped[1:-1]
            if current_section == section and not option_set:
                new_lines.append(f"{option}={value}\n")
                option_set = True
        lines = new_lines

    with open(service_file, 'w') as f:
        f.writelines(lines)