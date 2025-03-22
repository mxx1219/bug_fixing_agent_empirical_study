import os
import json
import matplotlib.pyplot as plt
from upsetplot import from_contents, UpSet

# Constants for maintainability
NAME_MAPPING = {
    "20241213_devlo": "devlo",
    "20241221_codestory_midwit_claude-3-5-sonnet_swe-search": "Midwit Agent",
    "20241223_emergent": "Emergent E1",
    "20250110_blackboxai_agent_v1.1": "Blackbox AI Agent",
    "20250110_learn_by_interact_claude3.5": "Learn-by-interact",
    "20250117_wandb_programmer_o1_crosscheck5": "W&B Programmer"
}

PREDICTIONS_DIR = "./exp_predictions/"
GOLDEN_FILES_PATH = "golden_files.json"
OUTPUT_FILES = {
    "full_coverage": "hit_all_files.json",
    "partial_coverage": "hit_at_least_one_file.json"
}


def load_json_file(file_path: str) -> dict:
    """Load JSON data from a file."""
    with open(file_path, "r") as f:
        return json.load(f)


def calculate_metrics(gt_info: dict, predictions: dict) -> tuple:
    """
    Calculate precision, recall, and F1-score for predictions against ground truth.
    
    Returns:
        tuple: (precision, recall, f1_score, covered_instances, fully_covered_instances)
    """
    hit_count = 0
    all_pred_count = 0
    all_gt_count = 0
    covered_instances = []
    fully_covered_instances = []

    for instance_id, gt_files in gt_info.items():
        all_gt_count += len(gt_files)
        pred_files = predictions.get(instance_id, [])
        all_pred_count += len(pred_files)
        
        # Find common files between predictions and ground truth
        common_files = set(gt_files) & set(pred_files)
        common_count = len(common_files)
        
        hit_count += common_count
        
        if common_count > 0:
            covered_instances.append(instance_id)
        if common_count == len(gt_files):
            fully_covered_instances.append(instance_id)

    # Handle division by zero cases
    precision = hit_count / all_pred_count if all_pred_count > 0 else 0
    recall = hit_count / all_gt_count if all_gt_count > 0 else 0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    return (
        round(precision, 3),
        round(recall, 3),
        round(f1_score, 3),
        covered_instances,
        fully_covered_instances
    )


def generate_upset_plot(data: dict, output_filename: str) -> None:
    """Generate and save an UpSet plot from the given data."""
    results = from_contents(data)
    UpSet(results, subset_size="count", show_counts=True).plot()
    plt.savefig(output_filename, dpi=300, bbox_inches='tight')
    plt.close()


def main():
    # Load ground truth data
    gt_info = load_json_file(GOLDEN_FILES_PATH)
    
    full_coverage_results = {}
    partial_coverage_results = {}

    # Process each prediction file
    for filename in os.listdir(PREDICTIONS_DIR):
        if not filename.endswith(".json"):
            continue

        tech_key = filename[:-5]  # Remove .json extension
        tech_name = NAME_MAPPING.get(tech_key, tech_key)
        print(f"Processing {tech_name}...")

        # Load predictions
        predictions = load_json_file(os.path.join(PREDICTIONS_DIR, filename))
        
        # Calculate performance metrics
        precision, recall, f1_score, covered, fully_covered = calculate_metrics(gt_info, predictions)
        
        # Format result entry
        result_label = f"{tech_name} (p-{precision}, r-{recall}, f-{f1_score})"
        
        # Store results
        partial_coverage_results[result_label] = covered
        full_coverage_results[result_label] = fully_covered

        # Print metrics
        print(f"Covered instances: {len(covered)}")
        print(f"Precision: {precision}, Recall: {recall}, F1: {f1_score}\n")

    # Save results to JSON files
    with open(OUTPUT_FILES["full_coverage"], "w") as f:
        json.dump(full_coverage_results, f, indent=4)
    
    with open(OUTPUT_FILES["partial_coverage"], "w") as f:
        json.dump(partial_coverage_results, f, indent=4)

    # Generate visualization plots
    generate_upset_plot(partial_coverage_results, "hit_at_least_one_file.png")
    generate_upset_plot(full_coverage_results, "hit_all_files.png")


if __name__ == "__main__":
    main()