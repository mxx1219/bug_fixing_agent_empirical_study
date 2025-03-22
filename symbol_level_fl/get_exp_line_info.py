import os
import json
import re


def get_hunks(deleted_lines, added_lines):
    """
    Group consecutive deleted line numbers into hunks, while removing overlapping added lines.
    
    Args:
        deleted_lines: List[int] - Sorted list of deleted line numbers
        added_lines: List[int] - List of added line numbers (will be modified during processing)
    
    Returns:
        List[List[int]] - List of hunks where each hunk contains consecutive line numbers
    """
    hunks = []
    current_hunk = []
    for factor in deleted_lines:
        if current_hunk and factor != max(current_hunk) + 1:
            hunks.append(current_hunk[:])
            current_hunk = []
        
        # Remove adjacent added lines that might overlap
        if factor-1 in added_lines:
            added_lines.remove(factor-1)
        if factor in added_lines:
            added_lines.remove(factor)
        
        current_hunk.append(factor)
    
    if current_hunk:
        hunks.append(current_hunk[:])
    return hunks


def calculate_whitespace(line):
    """
    Calculate whitespace length at line beginning (tabs as 4 spaces).
    
    Args:
        line: str - Input code line
    
    Returns:
        int - Equivalent whitespace length in spaces
    """
    whitespace_count = 0
    for char in line:
        if char == ' ':
            whitespace_count += 1
        elif char == '\t':
            whitespace_count += 4  # Tab expansion
        else:
            break  # Stop at first non-whitespace character

    return whitespace_count


def split_list_by_increasing_values(input_list):
    """
    Split list into subgroups where each subgroup maintains increasing values.
    
    Args:
        input_list: List[int] - Input list of integers
    
    Returns:
        List[List[int]] - List of split subgroups
    """
    result = []
    if not input_list:
        return result
    
    curr = []
    for factor in input_list:
        if not curr:
            curr.append(factor)
        else:
            if factor < min(curr):
                result.append(curr[:])
                curr = [factor]
            else:
                curr.append(factor)
    
    if curr:
        result.append(curr[:])
    return result


# Constants configuration
DIFF_PATTERN = re.compile(r'^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@')
META_DATA_PATH = os.path.join("..", "swe_bench_verified.json")
PROJECTS_DIR = os.path.join("..", "swe_projects")
EXPERIMENTS_DIR = os.path.join("..", "experiments")
OUTPUT_DIR = os.path.join(".", "exp_buggy_line_info")  # Output directory for results


def load_experiment_data():
    """Load all experiment predictions from JSONL files"""
    exp_info = {}
    for exp_id in os.listdir(EXPERIMENTS_DIR):
        exp_preds_path = os.path.join(EXPERIMENTS_DIR, exp_id, "all_preds.jsonl")
        
        with open(exp_preds_path, "r") as file:
            exp_content = file.readlines()
        
        curr_exp_info = {}
        for line in exp_content:
            exp_record = json.loads(line.strip())
            curr_exp_info[exp_record["instance_id"]] = exp_record["model_patch"]
        
        exp_info[exp_id] = curr_exp_info
    return exp_info


def main():
    with open(META_DATA_PATH, "r") as file:
        meta_data = json.load(file)
    
    exp_info = load_experiment_data()
    
    def parse_diff_patch(patch):
        """Extract line modification info from diff patch"""
        current_file_path = None
        line_index = 0
        deleted_lines = {}
        added_lines = {}
        add_line_content = {}
        
        for line in patch.split("\n"):
            # Detect file path declaration
            if line.startswith("---"):
                current_file_path = line.strip().split(" ")[1][2:]  # Extract filename
                deleted_lines[current_file_path] = []
                added_lines[current_file_path] = []
                add_line_content[current_file_path] = {}
            
            # Skip metadata lines
            elif line.startswith(("+++", "diff ", "index ", "deleted file mode",
                                "new file mode", "\ No newline", "Binary files")):
                continue
            
            # Process diff content
            else:
                match = DIFF_PATTERN.match(line)
                if match:
                    line_index = int(match.group(1)) - 1  # Convert to 0-based index
                else:
                    # Track deleted lines
                    if line.startswith("-"):
                        line_index += 1
                        deleted_lines[current_file_path].append(line_index)
                    # Track added lines and their content
                    elif line.startswith("+"):
                        added_lines[current_file_path].append(line_index)
                        add_line_content[current_file_path].setdefault(line_index, []).append(line[1:])
                    # Handle context lines
                    else:
                        line_index += 1
        return deleted_lines, added_lines, add_line_content

    all_hit_line_info = {}
    for record in meta_data:
        instance_id = record["instance_id"]
        project_name = "-".join(instance_id.split("-")[:-1])
        base_commit = record["base_commit"]
        pro_root_dir = os.path.join(PROJECTS_DIR, project_name)
        
        # Checkout target commit
        cmd = f"cd {pro_root_dir} && git checkout {base_commit} > /dev/null 2>&1"
        status = os.system(cmd)
        assert status == 0, f"Git checkout failed: {cmd}"
        
        # Process each experiment's patches
        for exp_id in exp_info:
            all_hit_line_info.setdefault(exp_id, {})
            if instance_id not in exp_info[exp_id]:
                continue
            
            patch = exp_info[exp_id][instance_id]
            if not (patch and patch.strip()):
                continue
            
            # Parse diff information
            deleted_lines, added_lines, add_line_content = parse_diff_patch(patch)
            
            all_hit_line_info[exp_id][instance_id] = {}
            
            # Analyze each modified file
            for file_path in deleted_lines:
                try:
                    with open(os.path.join(pro_root_dir, file_path), "r") as f:
                        file_lines = f.readlines()
                except Exception:
                    continue
                
                # Process line numbers
                deleted_lines[file_path] = sorted(set(deleted_lines[file_path]))
                added_lines[file_path] = sorted(set(added_lines[file_path]))
                hunks = get_hunks(deleted_lines[file_path], added_lines[file_path])
                
                # Detect anchor points for added code
                real_anchors = []
                for anchor in add_line_content.get(file_path, {}):
                    if anchor not in added_lines[file_path]:
                        continue
                    
                    # Analyze indentation patterns
                    blanks = [
                        calculate_whitespace(ln)
                        for ln in add_line_content[file_path][anchor]
                        if ln.strip()
                    ]
                    
                    # Determine code block boundaries
                    for block in split_list_by_increasing_values(blanks):
                        min_indent = min(block) if block else 0
                        # Find matching indentation in existing code
                        for i, file_line in enumerate(reversed(file_lines[:anchor])):
                            if not file_line.strip():
                                continue
                            curr_indent = calculate_whitespace(file_line)
                            if (min_indent == 0 and curr_indent == 0) or \
                               (min_indent > 0 and curr_indent < min_indent):
                                real_anchors.append(anchor - i)
                                break
                
                # Combine hunks and anchors
                real_anchors += [num for hunk in hunks for num in hunk]
                real_anchors = sorted(set(real_anchors))
                
                # Store results for Python files only
                if file_path.endswith(".py"):
                    all_hit_line_info[exp_id][instance_id][file_path] = real_anchors

    # Save analysis results
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for exp_id in all_hit_line_info:
        output_path = os.path.join(OUTPUT_DIR, f"{exp_id}.json")
        with open(output_path, "w") as f:
            json.dump(all_hit_line_info[exp_id], f, indent=4)


if __name__ == "__main__":
    main()