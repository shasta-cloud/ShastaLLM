import requests
import json
import time
import sys
import argparse
from datetime import datetime
sys.path.append('modules/')
sys.path.append('config/')

from modules import cloudsdk

payload = {
    "model":"llama3", 
    "messages":[
        {"role":"system","content":"You are chatting with a human who needs help in getting information about his system. Its system is a Wi-Fi network deployed in multiple venues and is managed by a cloud-based controller. The user will ask questions and you will provide answers by calling functions that connects to the controller and returns information. "},
        {"role":"system","content":"The user should provide a deployment in which the controller is located, then you will call the get-online-devices.py"},
        {"role": "assistant", "content": json.dumps({"deployment": "DF", "controller": "DF"})},  # Added comma here
        {"role":"user","content":"Hello! Whats can you help me with?"}
    ], 
    "stream":True
}

response = requests.post("http://localhost:11434/api/chat", json=payload)


for message in response.iter_lines():
    jsonstr = json.loads(message)
    if 'message' in jsonstr and 'content' in jsonstr['message']:
        print(jsonstr['message']["content"],end="")
    else:
        print("The server response does not contain a 'message' field with a 'content' subfield.")

while(True):
    user_input = input("\n Enter your message: ")
    payload["messages"][3]["content"] = user_input
    response = requests.post("http://localhost:11434/api/chat", json=payload)

    for message in response.iter_lines():
        jsonstr = json.loads(message)
        if 'message' in jsonstr and 'content' in jsonstr['message']:
            print(jsonstr['message']["content"], end="")
        else:
            print("The server response does not contain a 'message' field with a 'content' subfield.")


            