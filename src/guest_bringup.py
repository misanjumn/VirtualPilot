import subprocess
import time
import pexpect
import logging
from datetime import datetime


DEFAULTS = {
    'accelerator': 'kvm',
    'machine': 'pseries',
    'memory': 4096,
    'cpu': 'POWER11',
    'vcpus': 4,
    'qcow_path': './guests/qcows/large-fedora43.qcow2',
    'os_variant': 'fedora43',
    'name': 'fedora42-virtualpilot-kvm-pseries',
    'kernel': None,
    'initrd': None,
    'cmdline': None,
    'network_bridge': 'virbr0',
    'username': 'root',
    'password': '123456',
    'login_prompt': '\\w+ login: ',
    'password_prompt': '[Pp]assword: ',
    'shell_prompt': '.*[#$] ',
    'boot_timeout': 40,
    'virt_install_timeout': 10,
    'disable_kvm': False
}


def restart_libvirtd(cfg):
    """
    Restart libvirtd service on the host system.
    """

    try:
        print("Restarting libvirtd service...")
        result = subprocess.run(
            ["systemctl", "restart", "libvirtd"],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            return False, f"Failed to restart libvirtd: {result.stderr}"

        return True, None

    except Exception as e:
        return False, f"Error restarting libvirtd: {str(e)}"


def disable_kvm(cfg):
    """
    Disable KVM modules on the host system.
    """
    
    try:
        print("Disabling KVM modules...")

        # Step 1: Add blacklist entries using echo
        print("Adding blacklist entries to /etc/modprobe.d/disable-kvm.conf")
        result = subprocess.run(
            'echo "install kvm /bin/false" >> /etc/modprobe.d/disable-kvm.conf',
            shell=True,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            return False, f"Failed to blacklist kvm: {result.stderr}"
        result = subprocess.run(
            'echo "install kvm_hv /bin/false" >> /etc/modprobe.d/disable-kvm.conf',
            shell=True,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            return False, f"Failed to blacklist kvm_hv: {result.stderr}"

        # Step 2: Remove kvm_hv module
        print("Removing kvm_hv module...")
        subprocess.run(["modprobe", "-r", "kvm_hv"], capture_output=True)

        # Step 3: Remove kvm module
        print("Removing kvm module...")
        subprocess.run(["modprobe", "-r", "kvm"], capture_output=True)

        # Step 4: Verify KVM modules are not loaded
        print("Verifying KVM is disabled...")
        result = subprocess.run(
            "lsmod | grep kvm",
            shell=True,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return False, "KVM modules still loaded"

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
        return False, f"Error disabling KVM: {str(e)}"


def console_login(cfg, log_file):
    """
    Get into guest console via - virsh start <vm> --console
    """

    console_cmd = f"virsh start {cfg['name']} --console"

    try:
        print(f"Starting console with: {console_cmd}")

        # Start virsh console with pexpect
        child = pexpect.spawn(console_cmd, timeout=cfg['boot_timeout'])
        child.expect(cfg['login_prompt'])
        stdout = child.before.decode('utf-8')

        child.sendline(cfg['username'])
        child.expect(cfg['password_prompt'])
        child.sendline(cfg['password'])
        child.expect(cfg['shell_prompt'])

        # Write to log file
        log_file.write(stdout)
        log_file.flush()

        time.sleep(2)

        return True, None

    except pexpect.TIMEOUT as e:
        print(f"Timeout in console interaction: {e}")
        return False, f"Console timeout: {str(e)}"
    except pexpect.EOF as e:
        print(f"Console connection closed: {e}")
        return False, f"Console connection closed: {str(e)}"
    except Exception as e:
        print(f"Unexpected error in console login: {e}")
        return False, f"Console error: {str(e)}"


def virt_install(cfg):
    """
    Start the VM using - virt-install ..
    """

    try:
        if cfg.get("host_kernel", False):
            if cfg["kernel"] is None:  cfg["kernel"]  = "/boot/vmlinuz"
            if cfg["initrd"] is None: cfg["initrd"] = "/boot/initramfs.img"
            if cfg["cmdline"] is None:
                with open("/proc/cmdline") as f:
                    cfg["cmdline"] = f.read().strip()

        accel = "kvm" if cfg["accelerator"].lower() == "kvm" else "tcg"

        virt_install_cmd = [
            "virt-install",
            "--connect=qemu:///system",
            "--hvm",
            f"--name={cfg['name']}",
            f"--machine={cfg['machine']}",
            f"--memory={cfg['memory']}",
            f"--cpu={cfg['cpu']}",
            f"--vcpu={cfg['vcpus']}",
            "--import",
            "--nographics",
            "--noautoconsole",
            f"--os-variant={cfg['os_variant']}",
            "--console", "pty,target_type=serial",
            "--memballoon", "model=virtio",
            "--controller", "type=scsi,model=virtio-scsi",
            f"--disk=path={cfg['qcow_path']},bus=scsi,format=qcow2",
            f"--network=bridge={cfg['network_bridge']},model=virtio",
            f"--boot=emulator=/usr/bin/qemu-system-ppc64"
        ]

        if accel == "kvm":
            virt_install_cmd.append("--accelerate")
        if accel == "tcg":
            virt_install_cmd.append("--virt-type=qemu")

        if cfg["kernel"] and cfg["initrd"] and cfg["cmdline"]:
            virt_install_cmd.extend([
                "--boot",
                f"kernel={cfg['kernel']},initrd={cfg['initrd']},cmdline='{cfg['cmdline']}'"
            ])

        virt_install_cmd.append("--noreboot")

        print(f"Starting guest VM: {cfg['name']}")
        virt_install_cmd_string = " ".join(virt_install_cmd)
        print(f"virt-install command: {virt_install_cmd_string}")
        time.sleep(2)

        # Start virt-install in background
        virt_install_process = subprocess.Popen(
            virt_install_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        # Wait for process to complete or timeout
        time.sleep(cfg['virt_install_timeout'])

        virt_install_process.poll()
        if virt_install_process.returncode is not None and virt_install_process.returncode != 0:
            stderr = virt_install_process.stderr.read()
            return False, stderr

        return True, virt_install_process

    except subprocess.CalledProcessError as e:
        return False, f"virt-install failed: {e.stderr}"
    except Exception as e:
        return False, f"Unexpected error in virt_install: {str(e)}"


def check_call_traces(cfg, log_file):
    """
    Check if any call traces are present in the console log
    """

    # Define patterns to search for
    error_patterns = [
        # Kernel panics and oops
        "Kernel panic",
        "kernel BUG at",
        "BUG: unable to handle",
        "Oops:",
        
        # Call traces
        "Call Trace:",
        "Call trace:",
        "Backtrace:",
        
        # Segmentation faults
        "segmentation fault",
        "segfault",
        "SIGSEGV",
        
        # Other critical errors
        "general protection fault",
        "unable to mount root",
        "VFS: Cannot open root device",
        "Kernel panic - not syncing",
        
        # Out of memory
        "Out of memory",
        "OOM killer",
        "oom-killer",
        
        # Hardware errors
        "Machine check exception",
        "MCE:",

        # Soft lockup / hard lockup
        "soft lockup",
        "hard lockup",
        "hung task",
        
        # Stack corruption
        "stack-protector",
        "stack overflow",
        
        # RCU stalls
        "rcu_sched detected stalls",
        "rcu_preempt detected stalls",
    ]
    
    try:
        log_file_path = log_file.name
        with open(log_file_path, 'r') as f:
            log_content = f.read()
        
        # Check for each error pattern
        found_errors = []
        for pattern in error_patterns:
            if pattern.lower() in log_content.lower():
                found_errors.append(pattern)

        if found_errors:
            error_msg = f"Found {len(found_errors)} error pattern(s) in console log: {', '.join(found_errors)}"
            return False, error_msg

        return True, None

    except Exception as e:
        error_msg = f"Error while checking log file: {str(e)}"
        return False, error_msg
  

def check_guest_config(cfg, log_file):
    """
    Check if guest configurations are right
    """

    # Define dictonary to check for guest config


def run_tool(config: dict):
    """
    guest_bringup.py
    1. Install guest via virt-install
    2. Guest console login
    3. Check for call traces after guest login
    4. Check guest configurations
    """
    status = True
    error = None

    # Merge config with defaults
    cfg = DEFAULTS.copy()
    cfg.update({k: v for k, v in config.items() if v is not None})

    # Setup console log file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    console_log_file = f"console_{cfg['name']}_{timestamp}.log"
    log_file = open(console_log_file, 'w')
    log_file.write(f"Console log for {cfg['name']} - Started at {datetime.now()}\n")
    log_file.flush()

    try:
        # Restart libvirtd to ensure a clean state
        status, error = restart_libvirtd(cfg)
        if not status:
            return status, error

        # Disable KVM module in case of tcg mode
        if cfg["disable_kvm"] == True:
            status, error = disable_kvm(cfg)
            if not status:
                return status, error

        # Start VM using virt_install function
        status, result = virt_install(cfg)
        if not status:
            error = result
            return status, error

        # Get into the guest console via console_login function
        status, error = console_login(cfg, log_file)
        if not status:
            return status, error

        # Check for any call traces in the log_file
        status, error = check_call_traces(cfg, log_file)
        if not status:
            return status, error

    except Exception as e:
        status = False
        error = f"Unexpected error: {str(e)}"
    finally:
        log_file.write(f"\nConsole log ended at {datetime.now()}\n")
        log_file.write(f"Final status: {'SUCCESS' if status else 'FAILED'}\n")
        if error:
            log_file.write(f"Error: {error}\n")
        log_file.close()
        print(f"Console log saved to: {console_log_file}")

    # Return simple status and error as expected by main.py and avocado-main.py
    return status, error
