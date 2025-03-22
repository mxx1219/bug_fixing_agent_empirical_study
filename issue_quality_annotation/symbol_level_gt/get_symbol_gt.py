import os
import json
import pandas as pd
import re

def parse_line_ranges(line_range_str):
    range_list = line_range_str.split(',')
    line_numbers = []

    for part in range_list:
        if '-' in part:
            start, end = map(int, part.split('-'))
            line_numbers.extend(range(start, end + 1))
        else:
            line_numbers.append(int(part))

    return line_numbers

with open("../../swe_bench_verified.json", "r") as file:
    items = json.load(file)
project_dir = "./swe_bench_verified/"
symbol_gt_path = "../../symbol_level_fl/verified-code-entity-annotation.xlsx"
df = pd.read_excel(symbol_gt_path)
pattern = r'(?P<filename>[^:]+):(?P<code_type>[^()]+)\((?P<line_numbers>[0-9,-]+)\)'
pattern_function = r'def\s+(?P<function_name>[a-zA-Z_][a-zA-Z0-9_]*)\s*\('
pattern_class = r'class\s+(?P<class_name>[a-zA-Z_][a-zA-Z0-9_]*)\s*(\(|:)'
empty_symbol_instances = []
symbol_name_info = {}
for item in items:
    instance_id = item["instance_id"]
    project = "-".join(instance_id.split("-")[:-1])
    result = df.loc[df['Case-IDs'] == instance_id, 'Buggy Entities']
    ground_truth_list = result.tolist()[0].split("\n")
    # print(ground_truth_list)
    symbol_names = []
    for factor in ground_truth_list:
        if factor == "-":
            continue
        # print(factor)
        match = re.match(pattern, factor)
        assert match
        filename = match.group("filename")    # 'sympy__simplify__sqrtdenest'
        code_type = match.group("code_type") # 'functions'
        line_numbers = match.group("line_numbers") # 140
        flat_line_numbers = parse_line_ranges(line_numbers)
        if code_type not in ["methods", "classes", "functions"]:
            continue
        buggy_file_path = os.path.join(project_dir, instance_id, "buggy_files", filename+".py")
        with open(buggy_file_path, "r") as buggy_file:
            buggy_file_lines = buggy_file.readlines()
        entity_name = None
        for line_number in flat_line_numbers:
            curr_line = buggy_file_lines[line_number-1].strip()
            class_match = re.match(pattern_class, curr_line)
            if class_match:
                entity_name = filename + "::" + class_match.group('class_name')
            else:
                function_match = re.match(pattern_function, curr_line)
                if function_match:
                    entity_name = filename + "::" + function_match.group('function_name')
            if entity_name:
                break
        assert entity_name is not None
        # print(entity_name)
        symbol_names.append(entity_name)
    print(symbol_names)
    if not symbol_names:
        empty_symbol_instances.append(instance_id)
    symbol_name_info[instance_id] = symbol_names
print(empty_symbol_instances)
with open("gt_symbol_names.json", "w") as file:
    json.dump(symbol_name_info, file, indent=4)