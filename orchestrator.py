import yaml
import importlib.util
import os

def run_suite_from_config(yaml_path: str) -> bool:
    """
    loads YAML, imports script module, and calls run_tool(config)
    """

    with open(yaml_path) as f:
        cfg = yaml.safe_load(f)
    params = cfg.get("params", {})
    script_name = cfg.get("script")

    orchestrator_dir = os.path.dirname(os.path.abspath(__file__))

    # If nested, use run_suite_on_L0.py
    if cfg.get("nested") == True:
        script_path = os.path.join(orchestrator_dir, "utils", "run_suite_on_L0.py")
        spec = importlib.util.spec_from_file_location("run_suite_on_L0", script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        print(f"Orchestrate | running nested {script_name} on l0 with params: {params}")

    # Else, import the script directly
    else:
        script_path = os.path.join(orchestrator_dir, f"{script_name}.py")
        spec = importlib.util.spec_from_file_location(script_name, script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        print(f"Orchestrate | running {script_name} with params: {params}")

    # Call run_tool from the imported module
    status, error = module.run_tool(params)
    return status, error
