import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
import json
import multiprocessing

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

def send_request(model, messages, temperature = 0.0, n = 1):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}"
    }
    data = {
        "model": model,
        "messages": messages,
        "top_p": 1,
        "n": n,
        "temperature": temperature,
        "max_tokens": 1024*8,
    }
    data["messages"] = messages
    length = sum(len(str(obj)) for obj in messages)

    session = requests.Session()

    retry_limit = 3
    current_retry = 0
    while True:
        retry = Retry(
            total=15, 
            backoff_factor=2,  
            status_forcelist=tuple(range(401, 6000)),  
            allowed_methods=["POST"] 
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        chat_url = "https://openrouter.ai/api/v1/chat/completions"

        response = session.post(chat_url, json=data, headers=headers, timeout=(120, 300))

        parse_error = False
        resp_json = {}
        try:
            resp_json = response.json()
            _ = resp_json["choices"][0]
        except:
            parse_error = True

        if parse_error or response.status_code != 200 or "error" in resp_json["choices"][0]:
            print("response.status_code: ", response.status_code)
            # print(response.text)
            if length > 200000:
                raise Exception(f"Token limit protect! Message length: {length}")
            time.sleep(30) # Prevent tpm from being maxed out
            current_retry += 1
            if current_retry >= retry_limit:
                break
            else:
                continue
            
        return resp_json

    raise Exception(f"Failed to get response from LLM, Message length: {length}")


def get_llm_response(model: str, messages, temperature = 0.0, n = 1):
    decoded_answer = []
    assistant_response = send_request(model, messages, temperature, n)
    
    for choice in assistant_response["choices"]:
        decoded_answer.append(choice["message"]["content"])
    # print(assistant_response["usage"])
    return decoded_answer[0], assistant_response["usage"]


def predict(item):
    instance_id = item["instance_id"]
    problem_statment = item["problem_statement"]
    edited_files = item["edited_files"]
    print(instance_id)
    messages = [
        {
            "role": "system",
            "content":
f"""
You are a data annotator. Specifically, you need to complete the following tasks:

A user encountered a problem while using an open-source project and subsequently raised an issue. After seeing the issue, the developer provided a solution (the solution was provided by editing the code and submitting a patch). We will provide you with the full description of the issue raised by the user, as well as the names of the code files modified by the developer to resolve the issue. You need to carefully examine both, and annotate whether each modified file appears in the issue description text, and in what form it appears. For the "form" aspect, you need to choose one option from the following:

(1) Option: StackTrace. Explanation: The issue description text contains a StackTrace related to the problem, and the modified file's name appears directly in the StackTrace.
(2) Option: Keyword. Explanation: The issue description text contains the file's name and its path prefix directly. The path prefix is required to appear because together they uniquely specify the file entity. For example, if the target file is path/to/file_reader.py, it suffices if path/to/file_reader.py or path/to/file_reader appears without the suffix. Additionally, if the file path and file name appear separately in different locations of the issue description, this is allowed as long as both appear.
(3) Option: Natural Language. Explanation: The issue description text provides the file name in natural language format. If only the file name is mentioned and the file name's path prefix information does not appear anywhere in the issue description, this option should be chosen. However, note that the file's name cannot be split up. For instance, with file_reader.py, if file_reader.py or file_reader appears without the suffix, it is allowed. But if file and reader appear separately in different locations without forming the complete file_reader, this option cannot be chosen.
(4) Option: No Information. Explanation: The modified file's name does not appear in the current issue description. In cases where keywords like file and reader appear separately and not as file_reader, or worse, neither keyword appears, this option should be chosen. You do not need to make additional inferences based on your knowledge; we only require objective evaluation based on the literal content. If there is no information, then there is no information.

Note that the connection tightness in the above options decreases progressively from (1) to (4). If multiple options are satisfied simultaneously, you can only select the highest level option (e.g., if StackTrace, Keyword, and Natural Language are all satisfied, your annotation result should be StackTrace). Additionally, please note that for each target file given to you, you need to provide an annotation result!

Your final report must follow the format below:
```
<File_1>
## Target File: path/to/a.py
## Annotation Level: xxx (choose one of four)
## Supporting Reason: xxx (as concise as possible)
</File_1>

<File_2>
## Target File: path/to/b.py
## Annotation Level: xxx (choose one of four)
## Supporting Reason: xxx (as concise as possible)
</File_2>
...
```
"""
        },     
        {
            "role": "user",
            "content":                 
f"""
The issue description is as follows:
```
{problem_statment}
```

The edited files are as follows:
```
{edited_files}
```
Please return the annotated report to me as required after careful reading and analysis.
"""
        }
    ]
    response, usage = get_llm_response("deepseek/deepseek-r1", messages)
    os.makedirs("./predict_dsr1/")
    with open(f"./predict_dsr1/{instance_id}.txt", "w") as file:
        file.write(response)


def worker(task_queue):
    while True:
        task = task_queue.get()
        if task is None:
            break
        item = task
        predict(item)


def main():
    num_processes = 1 # Adjustable
    
    with open("../../swe_bench_verified.json", "r") as file:
        items = json.load(file)
    with open("../../file_level_fl/golden_files.json", "r") as file:
        gt_searcher = json.load(file)

    task_queue = multiprocessing.Queue()
    
    pool = []
    for _ in range(num_processes):
        p = multiprocessing.Process(target=worker, args=(task_queue,))
        p.start()
        pool.append(p)

    tasks = []
    for item in items:
        item["edited_files"] = "\n".join(gt_searcher[item["instance_id"]])
        tasks.append(item)
    print(len(tasks))

    for task in tasks:
        task_queue.put(task)
    
    for _ in range(num_processes):
        task_queue.put(None)

    for p in pool:
        p.join()


if __name__ == "__main__":
    main()