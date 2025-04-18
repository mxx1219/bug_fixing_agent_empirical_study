import os
from collections import Counter
import json

exp_dir = "./predict_dsr1"
level_list = []
instance_level_info = {}
for file_name in os.listdir(exp_dir):
    curr_level_list = []
    instance_id = file_name[:-4]
    # print(instance_id)
    with open(os.path.join(exp_dir, file_name), "r") as file:
        content = file.readlines()
    for line in content:
        if line.startswith("## Annotation Level:"):
            curr_level_list.append(line.replace("## Annotation Level:", "").strip())
    if not curr_level_list:
        print(file_name)
    # assert len(curr_level_list) == 1
    level_list.append(curr_level_list[-1])
    instance_level_info[instance_id] = curr_level_list[-1]

# 打印结果
element_counts = Counter(level_list)
for element, count in element_counts.items():
    print(f'{element}: {count}')

enum_to_score = {
    'Contains REs': 3,
    'Contains Partial REs': 2,
    'Info in NL': 1,
    'Not Enough Info': 0
}
scores = 0
for element in level_list:
    scores += enum_to_score[element]
print("avg_score: ", round(scores/len(level_list),3))

mapped_dict = {k: enum_to_score[v] for k, v in instance_level_info.items()}
with open("scores.json", "w") as file:
    json.dump(mapped_dict, file, indent=4)