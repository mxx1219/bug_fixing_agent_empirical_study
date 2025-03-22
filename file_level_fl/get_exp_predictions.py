import json
import os
import re

# Pattern to detect test-related paths
pattern = re.compile(
    r'(^|[/\\])(test|tests|testing)([/\\]|$)|(^|[/\\])test_',
    flags=re.IGNORECASE
)

def is_test_path(path):
    """Check if a path is related to tests."""
    return pattern.search(path) is not None

def process_block(block, modified_files):
    """
    Process a single block of diff information.

    Parameters:
    block (list of str): Lines representing a block of diff information.
    modified_files (list of str): List to store paths of modified files.
    """
    # Parse the diff --git line
    git_line = block[0].strip()
    parts = git_line.split()
    if len(parts) < 3:
        return
    
    # Extract source path and target path
    a_path_full = parts[2]
    b_path_full = parts[3]
    
    # Remove a/ and b/ prefixes
    a_path = a_path_full[2:] if a_path_full.startswith('a/') else a_path_full
    b_path = b_path_full[2:] if b_path_full.startswith('b/') else b_path_full
    
    # Exclude renamed or moved files
    if a_path != b_path:
        return
    
    # Find --- and +++ lines
    old_file, new_file = None, None
    for line in block:
        if line.startswith('--- '):
            old_file = line[4:].strip()
        elif line.startswith('+++ '):
            new_file = line[4:].strip()
    
    # Exclude added files (source path is /dev/null)
    if old_file == '/dev/null':
        return
    
    # Extract the relative path of the target file
    file_path = b_path
    
    # Check if the file extension is .py
    if not file_path.endswith('.py'):
        return
    
    # Exclude files related to tests
    if is_test_path(file_path):
        return
    
    modified_files.append(file_path)

def extract_modified_py_files(diff_string):
    """
    Extract modified Python file paths from a diff string.

    Parameters:
    diff_string (str): String containing the diff information.

    Returns:
    list of str: List of modified Python file paths.
    """
    modified_files = []
    if diff_string is None or not diff_string.strip():
        return modified_files
    
    current_block = []
    for line in diff_string.split("\n"):
        if line.startswith('diff --git'):
            if current_block:
                # Process the current block
                process_block(current_block, modified_files)
            current_block = [line]
        else:
            current_block.append(line)
    
    # Process the last block
    if current_block:
        process_block(current_block, modified_files)
    
    return modified_files

def process_experiment(exp_id, data_dir, output_dir):
    """
    Process a single experiment to extract modified file information.

    Parameters:
    exp_id (str): The experiment ID.
    data_dir (str): The directory containing experiment data.
    output_dir (str): The directory to save the output JSON file.
    """
    loc_file_info = {}
    result_path = os.path.join(data_dir, exp_id, "all_preds.jsonl")
    with open(result_path, "r") as file:
        content = file.readlines()
    for line in content:
        record = json.loads(line.strip())
        instance_id = record["instance_id"]
        modified_file_paths = extract_modified_py_files(record["model_patch"])
        loc_file_info[instance_id] = modified_file_paths
    
    output_path = os.path.join(output_dir, f"{exp_id}.json")
    with open(output_path, "w") as file:
        json.dump(loc_file_info, file, indent=4)

def main():
    data_dir = "../experiments/"
    output_dir = "./exp_predictions/"
    os.makedirs(output_dir, exist_ok=True)
    
    for exp_id in os.listdir(data_dir):
        # print(exp_id)
        process_experiment(exp_id, data_dir, output_dir)

if __name__ == "__main__":
    main()