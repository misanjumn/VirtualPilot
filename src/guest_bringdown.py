import subprocess
import time
import logging


DEFAULTS = {
    "name": "fedora42-virtualpilot-kvm-pseries",
}


def virsh_shutdown(cfg):
    """
    Shutdown VM gracefully - virsh shutdown <vm>
    """
    try:
        print(f"Shutting down guest: {cfg['name']}")
        result = subprocess.run(f"virsh shutdown {cfg['name']}", shell=True, capture_output=True, text=True)
        time.sleep(2)

        if result.returncode != 0:
            return False, result.stderr.strip()

        return True, result.stdout.strip()

    except Exception as e:
        return False, f"Unexpected error in shutdown: {str(e)}"


def virsh_destroy(cfg):
    """
    Force destroy VM - virsh destroy <vm>
    """
    try:
        print(f"Force destroying guest: {cfg['name']}")
        result = subprocess.run(f"virsh destroy {cfg['name']}", shell=True, capture_output=True, text=True)
        time.sleep(2)

        if result.returncode != 0:
            return False, result.stderr.strip()

        return True, result.stdout.strip()

    except Exception as e:
        return False, f"Unexpected error in destroy: {str(e)}"


def virsh_undefine(cfg):
    """
    Undefine VM - virsh undefine <vm>
    """
    try:
        print(f"Undefining guest: {cfg['name']}")
        result = subprocess.run(f"virsh undefine {cfg['name']}", shell=True, capture_output=True, text=True)
        time.sleep(2)

        if result.returncode != 0:
            return False, result.stderr.strip()

        return True, result.stdout.strip()

    except Exception as e:
        return False, f"Unexpected error in undefine: {str(e)}"


def run_tool(config: dict):
    """
    guest_bringdown.py
    1. Shutdown guest
    2. Destroy guest
    3. Undefine guest
    """
    status = True
    error = None

    # Merge config with defaults
    cfg = DEFAULTS.copy()
    cfg.update({k: v for k, v in config.items() if v is not None})

    status, result = virsh_shutdown(cfg)

    if not status:
        print(f"Graceful shutdown failed: {result}")
        destroy_status, destroy_result = virsh_destroy(cfg)

        if not destroy_status:
            status = False
            error = f"Shutdown failed: {result}, Destroy also failed: {destroy_result}"
        else:
            status = True
            error = None
    else:
        status = True
        error = None

    undefine_status, undefine_result = virsh_undefine(cfg)

    if not undefine_status:
        status = False
        error = f"Undefine failed: {undefine_result}"

    return status, error
