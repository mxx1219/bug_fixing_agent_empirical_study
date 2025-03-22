import os
from collections import Counter
import json

def get_highest_level(level_list):
    if "StackTrace" in level_list:
        return "StackTrace"
    elif "Keyword" in level_list:
        return "Keyword"
    elif "Natural Language" in level_list:
        return "Natural Language"
    else:
        return "No Information"

exp_dir = "./predict_claude35"
level_list = []
instance_level_list = []
instance_level_info = {}
for file_name in os.listdir(exp_dir):
    curr_level_list = []
    instance_id = file_name[:-4]
    with open(os.path.join(exp_dir, file_name), "r") as file:
        content = file.readlines()
    for line in content:
        if line.startswith("## Annotation Level:"):
            curr_level_list.append(line.replace("## Annotation Level:", "").strip())
    if not curr_level_list:
        print(file_name)
    level_list += curr_level_list
    higest_score = get_highest_level(curr_level_list)
    instance_level_list.append(higest_score)
    instance_level_info[instance_id] = higest_score

# instance level
element_counts = Counter(instance_level_list)
for element, count in element_counts.items():
    print(f'{element}: {count}')

enum_to_score = {
    'StackTrace': 3,
    'Keyword': 2,
    'Natural Language': 1,
    'No Information': 0
}
scores = 0
for element in instance_level_list:
    scores += enum_to_score[element]
print("avg_score: ", round(scores/len(instance_level_list),3))

mapped_dict = {k: enum_to_score[v] for k, v in instance_level_info.items()}
with open("scores.json", "w") as file:
    json.dump(mapped_dict, file, indent=4)