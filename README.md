# README

## Directory Structure

### `./experiments`
Contains patches submitted by six repair systems on the swe-bench official website and run logs.

### `./swe_projects`
Stores 12 swe-bench-verified code repositories. For demonstration, only the Astropy project is included. In actual use, you should clone the other 11 projects and put them here.

### `./reset_projects.sh`
Used to reset the initial state of the projects in `swe_projects`.

### `./repair`
Related to the bug fix experiments mentioned in the paper. Files included:
- `draw.py`: Run to generate `repair_statistics.json`, `repair_statistics.png`, and `overall_repair_info.json`.

### `./file_level_fl`
Related to file-level fault localization experiments mentioned in the paper. Files included:
- `golden_files.json`: Original file.
- `get_exp_predictions.py`: Run to obtain the sets of error files predicted by different repair methods for each case, output to the `exp_predictions` folder.
- `draw.py`: Run to get statistics for `hit_at_least_one` and `hit_all`, and generate respective plots.

### `./symbol_level_fl`
Related to symbol-level fault localization experiments mentioned in the paper. Files included:
- `get_exp_line_info.py`: Run to obtain the names of the error files predicted by each repair system.
- `get_buggy_files.py`: Search and generate the source code of these files.
- `code_symbol_parser.py`: Perform AST analysis to obtain the actual predicted code symbols.
- `draw.py`: Used for plotting.

### `./issue_quality_annotation`
Used to generate issue quality annotations with DeepSeek-r1 and includes five dimensions:
- `file_level_gt`
- `symbol_level_gt`
- `line_level_gt`
- `reproduce_gt`
- `solution_gt`

To operate within each folder:
1. Enter the corresponding folder for each dimension and run `llm_openrouter.py` to get ground truth predictions.
2. Run `result_parse.py` to obtain the final statistical results.
