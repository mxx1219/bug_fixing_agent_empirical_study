import os
import json

meta_data_path = "/home/mengxiangxin.1219/icse_26/file_level_localization_verified/swe_bench_verified.json"
standard_patch_diff_dir = "./standard_diff/"
delta_patch_diff_dir = "./delta_diff/"
os.makedirs(standard_patch_diff_dir, exist_ok=True)
os.makedirs(delta_patch_diff_dir, exist_ok=True)
with open(meta_data_path, "r") as file:
    content = json.load(file)
for factor in content:
    instance_id = factor["instance_id"]
    patch = factor["patch"]
    standard_patch_path = os.path.join(standard_patch_diff_dir, f"{instance_id}.patch")
    with open(standard_patch_path, "w") as file:
        file.write(patch)
    delta_patch_path = os.path.join(delta_patch_diff_dir, f"{instance_id}.patch")
    cmd = f"delta --line-numbers --hunk-header-style=omit --file-decoration-style=omit --keep-plus-minus-markers < {standard_patch_path} command | sed -e 's/\x1b\[[0-9;]*[a-zA-Z]//g' > {delta_patch_path}"
    status = os.system(cmd)
    assert status == 0