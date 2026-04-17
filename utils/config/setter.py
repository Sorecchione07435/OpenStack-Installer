import configparser

def set_conf_option(conf_file, section, option, value):

    config = configparser.ConfigParser()
    config.optionxform = str  # mantiene maiuscole/minuscole
    config.read(conf_file)

    if section not in config:
        config[section] = {}

    config[section][option] = value

    with open(conf_file, "w") as f:
        config.write(f)