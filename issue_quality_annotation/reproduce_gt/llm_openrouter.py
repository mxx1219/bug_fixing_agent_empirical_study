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
    print(instance_id)
    messages = [
        {
            "role": "system",
            "content":
f"""
```
You are a data annotator. Specifically, you need to complete the following task:
While using an open-source project, a user encountered a problem and subsequently raised an issue. We will provide you with the complete description of the issue raised by the user. Your task is to carefully examine and analyze whether the issue description contains information that helps reproduce the problem, and in what form this information is provided. For the form of the information, you need to choose one of the following options:
(1) Option: Contains REs. Explanation: REs stands for Reproducible Examples. This option means that the issue description contains complete, directly runnable code for reproducing the problem without the need for additional manual setup.
(2) Option: Contains Partial REs. Explanation: This option means that the issue description contains partial code for reproducing the problem. This code often includes the core part needed to reproduce the issue but lacks some other necessary information compared to (1), requiring additional context to run. Examples of such necessary information might include import statements (if needed), declarations of related variables, essential runtime configuration (if needed), etc. In summary, if the reproducible code provided in the issue description does not appear to be directly runnable, you should choose this option.
(3) Option: Info in NL. Explanation: NL stands for Natural Language. This option means that the issue description does not provide the reproducible code in the form of code snippets, but rather explains in natural language how to step by step reproduce the problem.
(4) Option: Not Enough Info. Explanation: Choose this option if you believe the issue description does not contain any information that helps reproduce the problem. You do not need to make additional assumptions based on your knowledge; we only need you to objectively evaluate the literal content. No information means no information.

Please note that the above options from (1) to (4) represent a decreasing quality of the reproducible scripts. If multiple options are satisfied at once, you can only respond with the highest-level option (for example, if Contains REs, Contains Partial REs, and Info in NL are all satisfied, your annotation should be Contains REs).

Your final report must be written in the following format:
```
## Annotation Level: xxx (choose one of the four)
## Supporting Reason: xxx (keep it concise)
```
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

Please return the annotated report to me as required after careful reading and analysis.
"""
        }
    ]
    response, usage = get_llm_response("deepseek/deepseek-r1", messages)
    os.makedirs("./predict_dsr1/")
    with open(f"./predict_dsr1/{instance_id}.txt", "w") as file:
        file.write(response+"\n")


def worker(task_queue):
    while True:
        task = task_queue.get()
        if task is None:
            break
        item = task
        predict(item)


def main():
    num_processes = 1
    
    with open("../../swe_bench_verified.json", "r") as file:
        items = json.load(file)

    task_queue = multiprocessing.Queue()
    
    pool = []
    for _ in range(num_processes):
        p = multiprocessing.Process(target=worker, args=(task_queue,))
        p.start()
        pool.append(p)

    tasks = []
    for item in items:
        # if item["instance_id"] in ["sympy__sympy-17139"]:
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