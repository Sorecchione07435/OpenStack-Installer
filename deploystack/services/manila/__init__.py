from .backends.generic import run_setup_generic_backend
from .controller import run_setup_common_manila
from .backends.lvm import run_setup_lvm_backend

from ...utils.config.parser import get

def run_setup_manila(config, env):
    backend = (get(config, "manila.BACKEND") or "generic").lower().strip()
    backend_fn = run_setup_lvm_backend if backend == "lvm" else run_setup_generic_backend
    return run_setup_common_manila(config, backend_fn, env)