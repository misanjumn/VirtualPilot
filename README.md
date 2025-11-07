# VirtualPilot - In-Progress
Lightweight Automation Framework for booting and validating virtual guests. It orchestrates QEMU and Libvirt to manage VM lifecycles.

## Setup
1. qemu, libvirt and kvm/tcg to be enabled
2. To install or add guest inside guests/qcows/guest.qcow2
3. (TBD) If running avocado suite style: `pip3 install avocado`

## Srcipts: src/*.py
1. guest_bringup.py:
    - Install guest via virt-install
    - Guest console login
    - Check for call traces after guest login
    - Check guest configurations (in progress)
2. guest_bringdown.py:
    - Shutdown guest
    - Destroy guest
    - Undefine guest

## Default yaml files created (for testing purpose): config/suites/*.yaml
kvm pseries guest
1. kvm_pseries_bringup.yaml
    - accelerator type: kvm
    - machine: pseries
2. kvm_pseries_bringdown.yaml
    - same as above, uninstall suite

tcg pseries guest
1. tcg_pseries_bringup.yaml
    - accelerator type: tcg
    - machine: pseries
2. tcg_pseries_bringdown.yaml
    - same as above, uninstall suite

## Command to run - single suite style
```python
python3 virtual-pilot.py --config config/suites/<suite>.yaml
```

## Command to run - multi suite avocado style (TBD)
```python
python3 virtual-pilot-avocado.py --config config/avocado-suites/<suite>.yaml
```
