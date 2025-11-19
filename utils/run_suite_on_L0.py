import subprocess
import paramiko
import os
import time
from scp import SCPClient


DEFAULTS = {
    'l0_name': 'fedora43-virtualpilot-tcg-pseries',
    'l0_username': 'root',
    'l0_password': '123456',
    'l0_location': '/home/VirtualPilot/',
    'host_virtualpilot': 'virtualpilot.py',
    'host_orchestrator': 'orchestrator.py',
    'host_script': 'src/guest_bringup.py',
    'host_suite': 'config/suites/nested_kvm_pseries_bringup.yaml',
    'nested_guest_image': 'guests/qcows/small-fedora43.qcow2',
}


def create_ssh_client(server, user, password):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(server, username=user, password=password)
    return client


def get_l0_ip(cfg):
    """
    Try to get IP address of l0_name via 'virsh domifaddr'.
    """
    try:
        print(f"Getting IP address of L0 VM: {cfg['l0_name']}")
        cmd = f"virsh domifaddr {cfg['l0_name']} --source agent --interface virbr0 --full"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return False, f"Failed to run virsh domifaddr: {result.stderr.strip()}"

        for line in result.stdout.splitlines():
            if 'ipv4' in line:
                parts = line.split()
                for part in parts:
                    if '/' in part:
                        ip = part.split('/')[0]
                        print(f"Found L0 IP: {ip}")
                        return True, ip
        print("No IP address found in virsh domifaddr output")
        return False, "No IP address found in virsh domifaddr output"

    except Exception as e:
        print(f"Exception in get_l0_ip: {str(e)}")
        return False, f"Exception in get_l0_ip: {str(e)}"


def scp_to_l0(cfg, ip_addr):
    """
    SCP necessary files to l0_guest VM under l0_location
    """
    try:
        ssh = create_ssh_client(ip_addr, cfg['l0_username'], cfg['l0_password'])
        # Create dir on remote if not exists
        stdin, stdout, stderr = ssh.exec_command(f"mkdir -p {cfg['l0_location']}")
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            return False, f"Failed to create directory {cfg['l0_location']}: {stderr.read().decode()}"

        # SCP files:
        files_to_copy = [
            (cfg['host_virtualpilot'], os.path.join(cfg['l0_location'], os.path.basename(cfg['host_virtualpilot']))),
            (cfg['host_orchestrator'], os.path.join(cfg['l0_location'], os.path.basename(cfg['host_orchestrator']))),
            (cfg['nested_guest_image'], os.path.join(cfg['l0_location'], os.path.basename(cfg['nested_guest_image']))),
            (cfg['host_script'], os.path.join(cfg['l0_location'], os.path.basename(cfg['host_script']))),
            (cfg['host_suite'], os.path.join(cfg['l0_location'], os.path.basename(cfg['host_suite'])))
        ]

        scp = SCPClient(ssh.get_transport())
        for src, dest in files_to_copy:
            if not os.path.exists(src):
                return False, f"Source file not found: {src}"
            print(f"SCPing to L0: {src} to {dest} on L0")
            scp.put(src, dest)
        scp.close()
        ssh.close()
        return True, None

    except Exception as e:
        return False, f"SCP to L0 failed: {str(e)}"


def ssh_and_run(cfg, ip_addr):
    """
    SSH to L0 and run virtualpilot.py with suite argument
    """
    try:
        ssh = create_ssh_client(ip_addr, cfg['l0_username'], cfg['l0_password'])
        virtualpilot_dir = cfg['l0_location']
        virtualpilot_path = os.path.join(cfg['l0_location'], os.path.basename(cfg['host_virtualpilot']))
        suite_path = os.path.join(cfg['l0_location'], os.path.basename(cfg['host_suite']))

        edit_nested_param = f"sed -i 's/nested: true/nested: false/' {suite_path}"
        run_virtualpilot = f"cd {virtualpilot_dir} && python3 {virtualpilot_path} --config {suite_path}"

        # First, edit the suite to set nested: false
        print(f"Editing suite file on L0 to set nested: false: {suite_path}")
        stdin, stdout, stderr = ssh.exec_command(edit_nested_param)
        out = stdout.read().decode()
        err = stderr.read().decode()

        exit_code = stdout.channel.recv_exit_status()
        if exit_code != 0:
            ssh.close()
            return False, f"Failed to edit suite file on L0 with exit code {exit_code}, stderr: {err}"

        # Now run virtualpilot
        print(f"Running VirtualPilot on L0: {virtualpilot_path} with suite {suite_path}")
        print(f"Command: {run_virtualpilot}")
        stdin, stdout, stderr = ssh.exec_command(run_virtualpilot)
        out = stdout.read().decode()
        err = stderr.read().decode()

        exit_code = stdout.channel.recv_exit_status()
        ssh.close()

        if exit_code != 0:
            return False, f"Command failed with exit code {exit_code}, stderr: {err}"
        return True, None

    except Exception as e:
        return False, f"SSH and run failed: {str(e)}"


def copy_logs_back(cfg, ip_addr):
    """
    SCP console logs from l0 l0_location to host system in cwd
    """
    try:
        ssh = create_ssh_client(ip_addr, cfg['l0_username'], cfg['l0_password'])
        scp = SCPClient(ssh.get_transport())

        # Assuming console logs have a fixed pattern or name
        # List files remote
        remote_dir = cfg['l0_location']
        stdin, stdout, stderr = ssh.exec_command(f"ls {remote_dir}console_*.log")
        files = stdout.read().decode().strip().split()
        if not files:
            return False, "No console log files found on L0"

        for remote_file in files:
            local_file = os.path.basename(remote_file)
            print(f"Copying log file from L0: {remote_file} to host: {local_file}")
            scp.get(remote_file, local_file)

        scp.close()
        ssh.close()
        return True, None

    except Exception as e:
        return False, f"Copy logs back failed: {str(e)}"


def cleanup_l0(cfg, ip_addr):
    """
    Cleanup files on l0_location
    """
    try:
        ssh = create_ssh_client(ip_addr, cfg['l0_username'], cfg['l0_password'])
        cmd = f"rm -rf {cfg['l0_location']}*"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        exit_status = stdout.channel.recv_exit_status()
        ssh.close()
        if exit_status != 0:
            return False, f"Cleanup failed: {stderr.read().decode()}"
        return True, None

    except Exception as e:
        return False, f"Cleanup L0 failed: {str(e)}"


def run_tool(config: dict):
    """
    run_script_on_L0.py
    1. Get ip address of L0
    2. SCP guest image to L0
    3. SCP script to L0
    4. SSH to L0 and run script
    5. Copy console logs back l0 to host
    6. if pass, return True, None
       else return False, "error message"
    """
    status = True
    error = None

    cfg = DEFAULTS.copy()
    cfg.update({k: v for k, v in config.items() if v is not None})

    # Step 1: Get L0 IP
    print("\n*************** STEP 1 *****************")
    print("Step1: Get L0 IP address")
    status, ip_addr = get_l0_ip(cfg)
    if not status:
        error = ip_addr
        print(f"Step1: Error getting L0 IP: {error}")
        return status, error
    print(f"L0 IP Address: {ip_addr}")
    print("Step1: Get L0 IP completed successfully")

    # Step 2: SCP files to L0
    print("\n*************** STEP 2 *****************")
    print("Step2: SCP files to L0")
    status, error = scp_to_l0(cfg, ip_addr)
    if not status:
        print(f"Step2: Error SCP to L0: {error}")
        print("Cleanup: Cleaning up L0 after SCP failure")
        cleanup_status, cleanup_error = cleanup_l0(cfg, ip_addr)
        if not cleanup_status:
            print(f"Cleanup: Error during cleanup: {cleanup_error}")
            error += f" | Cleanup error: {cleanup_error}"
        return status, error
    print("Step2: SCP to L0 completed successfully")

    # Step 3: SSH and run
    print("\n*************** STEP 3 *****************")
    print("Step3: SSH and run on L0")
    status, error = ssh_and_run(cfg, ip_addr)
    if not status:
        print(f"Step3: Error SSH and run on L0: {error}")
        print("Cleanup: Cleaning up L0 after ssh failure")
        cleanup_status, cleanup_error = cleanup_l0(cfg, ip_addr)
        if not cleanup_status:
            print(f"Cleanup: Error during cleanup: {cleanup_error}")
            error += f" | Cleanup error: {cleanup_error}"
        return status, error
    print("Step3: SSH and run on L0 completed successfully")

    # Step 4: Copy logs back
    print("\n*************** STEP 4 *****************")
    print("Step4: Copy logs back from L0")
    status, error = copy_logs_back(cfg, ip_addr)
    if not status:
        print(f"Step4: Error copying logs back from L0: {error}")
        print("Cleanup: Cleaning up L0 after SCP failure")
        cleanup_status, cleanup_error = cleanup_l0(cfg, ip_addr)
        if not cleanup_status:
            print(f"Cleanup: Error during cleanup: {cleanup_error}")
            error += f" | Cleanup error: {cleanup_error}"
        return status, error
    print("Step4: Copy logs back from L0 completed successfully")

    # Step 5: Cleanup L0
    print("\n************* CLEAN UP *****************")
    cleanup_status, cleanup_error = cleanup_l0(cfg, ip_addr)
    if not cleanup_status:
        print(f"Cleanup: Error during final cleanup: {cleanup_error}")
        error = cleanup_error
    print("Cleanup: Final Cleanup L0 completed successfully")

    return status, error
