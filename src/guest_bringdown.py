import subprocess
import time
import logging


DEFAULTS = {
    "name": "fedora43-virtualpilot-kvm-pseries",
    "accelerator": "kvm",
    "disable_kvm": False
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


def restore_kvm(cfg):
    """
    Enable KVM modules on Host system.
    """

    try:
        print("Restoring KVM modules...")

        # Step 1: Remove blacklist config file
        print("Removing KVM blacklist configuration...")
        result = subprocess.run(
            "rm -rf /etc/modprobe.d/disable-kvm.conf",
            shell=True,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            return False, f"Failed to remove blacklist config: {result.stderr}"

        # Step 2: Load kvm module
        print("Loading kvm module...")
        result = subprocess.run(
            ["modprobe", "kvm"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            return False, f"Failed to load kvm module: {result.stderr}"

        # Step 3: Load kvm_hv module
        print("Loading kvm_hv module...")
        result = subprocess.run(
            ["modprobe", "kvm_hv"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            return False, f"Failed to load kvm_hv module: {result.stderr}"

        # Step 4: Verify KVM modules are loaded
        print("Verifying KVM is restored...")
        result = subprocess.run(
            "lsmod | grep kvm",
            shell=True,
            capture_output=True,
            text=True
        )

        # grep returns 0 when something is found (which is what we want)
        if result.returncode != 0:
            return False, "KVM modules not loaded after restore attempt"

        print(f"  Loaded modules:\n{result.stdout}")

        # Step 5: Restart libvirtd
        print("Restarting libvirtd...")
        result = subprocess.run(
            ["systemctl", "restart", "libvirtd"],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            return False, f"Failed to restart libvirtd: {result.stderr}"

        return True, None

    except Exception as e:
        return False, f"Error restoring KVM: {str(e)}"


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

    if cfg["accelerator"] == "tcg":
        destroy_status, destroy_result = virsh_destroy(cfg)
        if not destroy_status:
            status = False
            error = f"Shutdown failed: {result}, Destroy also failed: {destroy_result}"
        else:
            status = True
            error = None
    else:
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

    if cfg["disable_kvm"] == True:
        status, error = restore_kvm(cfg)
        if not status:
            return status, error

    return status, error
