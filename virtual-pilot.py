# python3 main.py --config config/custom_suite.yaml

import argparse
from orchestrator import run_suite_from_config

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="config/suites/kvm_pseries_bringup.yaml",
        help="Path to YAML file listing which tests to run"
    )
    args = parser.parse_args()

    result, error = run_suite_from_config(args.config)
    if not result:
        print(f"\nTest failed: {args.config}\nFailure: {error}")

if __name__ == "__main__":
    main()
