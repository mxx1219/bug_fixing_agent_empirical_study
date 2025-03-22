import os
import json
import matplotlib.pyplot as plt
from upsetplot import from_contents, UpSet

# Configuration constants
NAME_MAPPING = {
    "20241213_devlo": "devlo",
    "20241221_codestory_midwit_claude-3-5-sonnet_swe-search": "Midwit Agent",
    "20241223_emergent": "Emergent E1",
    "20250110_blackboxai_agent_v1.1": "Blackbox AI Agent",
    "20250110_learn_by_interact_claude3.5": "Learn-by-interact",
    "20250117_wandb_programmer_o1_crosscheck5": "W&B Programmer"
}

EXPERIMENTS_DIR = "../experiments/"
RESULTS_SUBPATH = "results/results.json"
BENCHMARK_FILE = "../swe_bench_verified.json"
OUTPUT_FILES = {
    "repair_data": "repair_statistics.json",
    "analysis_results": "overall_repair_info.json",
    "visualization": "repair_statistics.png"
}

def load_json_data(file_path: str) -> dict:
    """Load and parse JSON data from a file with error handling."""
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading {file_path}: {str(e)}")
        return {}

def collect_repair_data() -> dict:
    """Collect resolved instances from all experiment results."""
    repair_data = {}
    
    for exp_name in os.listdir(EXPERIMENTS_DIR):
        exp_path = os.path.join(EXPERIMENTS_DIR, exp_name)
        if not os.path.isdir(exp_path):
            continue
            
        result_file = os.path.join(exp_path, RESULTS_SUBPATH)
        if not os.path.exists(result_file):
            continue
            
        data = load_json_data(result_file)
        if not data:
            continue
            
        # Get display name using mapping
        display_name = NAME_MAPPING.get(exp_name, exp_name)
        repair_data[display_name] = data.get("resolved", [])
    
    return repair_data

def analyze_repair_coverage(repair_data: dict) -> dict:
    """Calculate comprehensive repair coverage statistics."""
    # Load benchmark instances
    benchmark_entries = load_json_data(BENCHMARK_FILE)
    all_instances = {entry["instance_id"] for entry in benchmark_entries}
    
    # Calculate set operations
    resolved_sets = [set(instances) for instances in repair_data.values()]
    
    return {
        "all_resolve_set": sorted(set.intersection(*resolved_sets)) if resolved_sets else [],
        "no_one_resolve_set": sorted(all_instances - set.union(*resolved_sets)) if resolved_sets else sorted(all_instances),
        "all_set": sorted(all_instances)
    }

def generate_upset_plot(data: dict, output_path: str) -> None:
    """Generate and save an UpSet plot visualization."""
    plot_data = from_contents(data)
    UpSet(plot_data, subset_size="count", show_counts=True).plot()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()

def main():
    # Phase 1: Data Collection
    repair_results = collect_repair_data()
    with open(OUTPUT_FILES["repair_data"], "w") as f:
        json.dump(repair_results, f, indent=4)
    
    # Phase 2: Data Analysis
    coverage_stats = analyze_repair_coverage(repair_results)
    with open(OUTPUT_FILES["analysis_results"], "w") as f:
        json.dump(coverage_stats, f, indent=4)
    
    # Phase 3: Visualization
    generate_upset_plot(repair_results, OUTPUT_FILES["visualization"])

if __name__ == "__main__":
    main()