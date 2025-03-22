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
    edited_symbols = item["edited_symbols"]
    print(instance_id)
    if not edited_symbols:
        with open(f"./predict_dsr1/{instance_id}.txt", "w") as file:
            file.write("No gt code symboles.")
    else:
        messages = [
            {
                "role": "system",
                "content":
    f"""
You are a data annotator. Specifically, you need to perform the following task:
A user encountered a problem while using an open-source project and subsequently raised an issue. After seeing the issue, a developer provided a solution (the solution is given in the form of editing the code and submitting a patch). We will provide you with the full description of the issue raised by the user, as well as the names of the code symbols (including classes, functions, and methods) modified by the developer to address the issue. We use the format "file_path::symbol_name" to provide the information. You need to carefully review both and annotate whether each edited code symbol is mentioned in the issue description text and in what form it is mentioned. For the "form of mention," you need to choose one option from the following:

(1) Option: StackTrace. Explanation: The issue description text contains a related stack trace, and the name of the target code symbol appears directly in the stack trace.
(2) Option: Keyword. Explanation: The issue description text contains the name of the code symbol and its file path, but this information does not appear in the stack trace. Considering that symbols may have the same name in different files, both the symbol name and file path are indispensable; otherwise, you cannot choose this option.
(3) Option: Natural Language. Explanation: The issue description text mentions the name of the code symbol in natural language form, without requiring the file path information. Note that the code symbol name cannot be split into parts; for example, if a symbol is named `file_reader`, it doesn't count if only `file` and `reader` appear separately without the full `file_reader`.
(4) Option: No Information. Explanation: You cannot find any direct and accurate description related to the target code symbol in the issue text. Indirect descriptions also count as No Information; for example, if a function is named `file_reader`, and only separate mentions of `file` and `reader` appear but not the full `file_reader`, you should choose this option because this information is insufficient to directly identify the corresponding symbol. You don't need to make additional inferences based on your knowledge; we only need you to evaluate objectively based on the text. No information means no information.

Note that among the above options, from (1) to (4), the degree of relevance decreases gradually. If multiple options are satisfied simultaneously, you can only choose the highest-level option (e.g., if StackTrace, Keyword, and Natural Language are all satisfied, your annotation result should be StackTrace). Additionally, you need to provide annotation results for each target code symbol given!

Your final report must be written in the following format:
```
<Symbol_1>
## Target Code Symbol: xxx
## Annotation Level: xxx (choose one from four options)
## Supporting Reason: xxx (as concise as possible)
</Symbol_1>

<Symbol_2>
## Target Code Symbol: xxx
## Annotation Level: xxx (choose one from four options)
## Supporting Reason: xxx (as concise as possible)
</Symbol_2>
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

The edited code symbols are as follows:
```
{edited_symbols}
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
            # 接收到结束信号，退出循环
            break
        item = task
        predict(item)


def main():
    num_processes = 1
    
    with open("../../swe_bench_verified.json", "r") as file:
        items = json.load(file)
    with open("./gt_symbol_names.json", "r") as file:
        gt_searcher = json.load(file)

    task_queue = multiprocessing.Queue()
    
    pool = []
    for _ in range(num_processes):
        p = multiprocessing.Process(target=worker, args=(task_queue,))
        p.start()
        pool.append(p)

    tasks = []
    for item in items:
        item["edited_symbols"] = "\n".join(gt_searcher[item["instance_id"]])
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