import os
import json
import pandas as pd
from collections import Counter
from matplotlib import pyplot as plt
from upsetplot import UpSet, from_contents

# --------------------------
# Configuration Constants
# --------------------------
META_DATA_DIR = "./data/techniques/"
EXP_DATA_DIR = "./exp_buggy_line_info"
META_PATH = "../swe_bench_verified.json"
ANNOTATION_FILE = 'verified-code-entity-annotation.xlsx'
EXCLUDE_IMPORTS = True

# --------------------------
# Name Translation Mapping
# --------------------------
MODEL_NAME_MAPPING = {
    "20241213_devlo": "devlo",
    "20241221_codestory_midwit_claude-3-5-sonnet_swe-search": "Midwit Agent",
    "20241223_emergent": "Emergent E1",
    "20250110_blackboxai_agent_v1.1": "Blackbox AI Agent",
    "20250110_learn_by_interact_claude3.5": "Learn-by-interact",
    "20250117_wandb_programmer_o1_crosscheck5": "W&B Programmer"
}

# --------------------------
# Core Utility Functions
# --------------------------

def parse_line_ranges(line_range_str: str) -> list[int]:
    """Parse a line range string into a list of integers.
    
    Args:
        line_range_str: String containing line ranges (e.g., '1-3,5')
    
    Returns:
        List of expanded line numbers
    """
    ranges = line_range_str.split(',')
    line_numbers = []
    for part in ranges:
        if '-' in part:
            start, end = map(int, part.split('-'))
            line_numbers.extend(range(start, end + 1))
        else:
            line_numbers.append(int(part))
    return line_numbers

def calculate_precision_recall(hits: list, predictions: list, ground_truth: list) -> tuple[float, float]:
    """Calculate precision and recall metrics.
    
    Args:
        hits: List of correctly predicted items
        predictions: List of all predicted items
        ground_truth: List of all ground truth items
    
    Returns:
        Tuple of (precision, recall) as floats
    """
    precision = len(hits) / len(predictions) if predictions else 0.0
    recall = len(hits) / len(ground_truth) if ground_truth else 0.0
    return round(precision, 3), round(recall, 3)

def validate_non_empty_lines(buggy_lines: list[str], predicted_lines: list[int]) -> list[int]:
    """Filter out empty lines from predicted line numbers.
    
    Args:
        buggy_lines: List of lines from original file
        predicted_lines: List of predicted line numbers
    
    Returns:
        Filtered list of non-empty line numbers
    """
    valid_lines = []
    for line_num in predicted_lines:
        try:
            if buggy_lines[line_num-1].strip():
                valid_lines.append(line_num)
        except IndexError:
            continue
    return valid_lines

# --------------------------
# Data Processing Functions
# --------------------------

def load_metadata() -> tuple[list, dict]:
    """Load and prepare metadata from JSON file.
    
    Returns:
        Tuple of (instance_ids, meta_data)
    """
    with open(META_PATH) as f:
        meta_data = json.load(f)
    return [item["instance_id"] for item in meta_data], meta_data

def process_entity_file(entity_path: str) -> list[dict]:
    """Load and process entity JSON file.
    
    Args:
        entity_path: Path to entity JSON file
    
    Returns:
        List of processed entities
    """
    if not os.path.exists(entity_path):
        return []
    
    with open(entity_path) as f:
        entities = json.load(f)
    
    if EXCLUDE_IMPORTS:
        return [e for e in entities if e["type"] != "imports"]
    return entities

def generate_predictions(case_id: str, content: dict, df: pd.DataFrame) -> tuple[list, list]:
    """Generate prediction list for a given test case.
    
    Args:
        case_id: ID of the test case
        content: Loaded experiment data
        df: DataFrame with annotation data
    
    Returns:
        Tuple of (predict_list, ground_truth_list)
    """
    # Get ground truth from annotations
    gt_entities = df.loc[df['Case-IDs'] == case_id, 'Buggy Entities']
    ground_truth = gt_entities.tolist()[0].split("\n") if not gt_entities.empty else []
    
    if EXCLUDE_IMPORTS:
        ground_truth = [e for e in ground_truth if "imports(" not in e]

    # Process predictions
    predictions = []
    if case_id not in content:
        return [], ground_truth
    
    for file_path, pred_lines in content[case_id].items():
        if not file_path.endswith(".py"):
            continue
        
        formatted_name = file_path.replace("/", "__")
        base_path = os.path.join(META_DATA_DIR, case_id)
        
        # Validate file paths
        buggy_path = os.path.join(base_path, "buggy_files", formatted_name)
        entity_path = os.path.join(base_path, "entities", formatted_name[:-3] + ".json")
        
        if not os.path.exists(buggy_path) or not os.path.exists(entity_path):
            continue
        
        # Read file contents
        with open(buggy_path) as f:
            buggy_lines = f.readlines()
        
        # Process entities and predictions
        entities = process_entity_file(entity_path)
        valid_lines = validate_non_empty_lines(buggy_lines, pred_lines)
        
        for entity in entities:
            entity_lines = parse_line_ranges(entity["line_range"])
            if set(valid_lines) & set(entity_lines):
                entity_desc = f"{formatted_name[:-3]}:{entity['type']}({entity['line_range']})"
                predictions.append(entity_desc)
    
    return sorted(list(set(predictions))), ground_truth

# --------------------------
# Analysis & Reporting
# --------------------------

def calculate_metrics(predictions: list, ground_truth: list) -> tuple:
    """Calculate evaluation metrics for a single test case.
    
    Returns:
        Tuple containing (hits, num_predictions, num_ground_truth, precision, recall)
    """
    hits = [e for e in predictions if e in ground_truth]
    precision, recall = calculate_precision_recall(hits, predictions, ground_truth)
    return len(hits), len(predictions), len(ground_truth), precision, recall

def generate_coverage_plots(coverage_data: dict, filename: str):
    """Generate UpSet plot from coverage data.
    
    Args:
        coverage_data: Dictionary of coverage data
        filename: Output filename
    """
    results = from_contents(coverage_data)
    UpSet(results, subset_size="count", show_counts=True).plot()
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close()

# --------------------------
# Main Execution
# --------------------------

def main():
    """Main analysis pipeline."""
    # Initialize data structures
    instance_ids, _ = load_metadata()
    annotation_df = pd.read_excel(ANNOTATION_FILE)
    
    partial_coverage = {}
    full_coverage = {}

    # Process each experiment result
    for exp_file in os.listdir(EXP_DATA_DIR):
        exp_path = os.path.join(EXP_DATA_DIR, exp_file)
        model_name = MODEL_NAME_MAPPING.get(exp_file[:-5], exp_file[:-5])
        
        with open(exp_path) as f:
            exp_data = json.load(f)

        # Initialize metrics accumulators
        metrics = {'hits': 0, 'preds': 0, 'gt': 0, 'precisions': [], 'recalls': []}
        coverage_cases = {'partial': [], 'full': []}

        # Process each test case
        for case_id in instance_ids:
            predictions, ground_truth = generate_predictions(case_id, exp_data, annotation_df)
            hits, num_pred, num_gt, prec, rec = calculate_metrics(predictions, ground_truth)
            
            # Update metrics
            metrics['hits'] += hits
            metrics['preds'] += num_pred
            metrics['gt'] += num_gt
            metrics['precisions'].append(prec)
            metrics['recalls'].append(rec)
            
            # Track coverage
            if rec > 0:
                coverage_cases['partial'].append(case_id)
            if rec == 1:
                coverage_cases['full'].append(case_id)

        # Calculate final metrics
        micro_prec = metrics['hits'] / metrics['preds'] if metrics['preds'] else 0
        micro_rec = metrics['hits'] / metrics['gt'] if metrics['gt'] else 0
        f1 = (2 * micro_prec * micro_rec) / (micro_prec + micro_rec) if (micro_prec + micro_rec) else 0
        
        # Store results
        label = f"{model_name}(p-{micro_prec:.3f}, r-{micro_rec:.3f}, f-{f1:.3f})"
        partial_coverage[label] = coverage_cases['partial']
        full_coverage[label] = coverage_cases['full']

    # Save and visualize results
    with open("hit_all_symbols.json", "w") as f:
        json.dump(full_coverage, f, indent=4)
    with open("hit_at_least_one_symbol.json", "w") as f:
        json.dump(partial_coverage, f, indent=4)

    generate_coverage_plots(full_coverage, 'hit_all_symbols.png')
    generate_coverage_plots(partial_coverage, 'hit_at_least_one_symbol.png')

if __name__ == "__main__":
    main()