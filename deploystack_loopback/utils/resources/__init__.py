from .loopback import Loopback

def load_resources(config):

    return {
        name: Loopback(config.resource(name))
        for name in ("cinder", "manila")
    }