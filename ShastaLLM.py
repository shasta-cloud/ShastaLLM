import langchain
from langchain_community.chat_models import ChatOllama
from langchain.llms import Ollama
from langchain.prompts import ChatPromptTemplate
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_experimental.llms.ollama_functions import OllamaFunctions
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ChatMessage
from langchain.agents import AgentType, initialize_agent, load_tools
from langchain.tools.base import StructuredTool
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
from langchain.agents import AgentExecutor, create_structured_chat_agent, Tool
from langchain.tools import BaseTool
from langchain.pydantic_v1 import BaseModel, Field
from langchain.callbacks.manager import (AsyncCallbackManagerForToolRun, CallbackManagerForToolRun)
from langchain.memory import ConversationBufferWindowMemory
from langchain_experimental.llms.ollama_functions import OllamaFunctions
from langchain.callbacks.manager import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain import hub
from typing import Optional, Type
from langchain.document_loaders import UnstructuredFileLoader
from langchain.chains.summarize import load_summarize_chain
from langchain_community.document_loaders import WebBaseLoader

import os

from pandasai import SmartDataframe
from pandasai.llm.local_llm import LocalLLM

import streamlit as st
from langchain.callbacks import StreamlitCallbackHandler
import requests
import json
import time

import sys
import glob
import pandas as pd


#loader = UnstructuredFileLoader()
#docs = loader.load()

class GetOnlineDevices(BaseTool):
    name = "get_online_devices"
    description =  """Obtains data from the Shasta web user interface for the given deployment.
    Args:
        deployment (str): The deployment in which the controller is located (possible inputs: DF, dogfood, Production, PROD, STG, staging, development, DEV - should be mapped to DF, PROD, STG or DEV).
        new (bool): Whether to get the latest data or not. If not stated, it will be set to False.
    
    Returns:
        int: a number - all the devices of that deployment that are online
    """
    deployment: Optional[str] = Field(None, description=" The deployment in which the controller is located (possible inputs: DF, dogfood, Production, PROD, STG, staging, development, DEV - should be mapped to DF, PROD, STG or DEV).")
    new: Optional[bool] = Field(None, description="Whether to get the latest data or not. If not stated, it will be set to False.")

    def _run(self, deployment:str, new:bool, run_manager: Optional[CallbackManagerForToolRun]) -> str: 
        try:
            if new:
                # Get the latest data
                subprocess.call([sys.executable, "get-online-devices.py", "-d", deployment]) #, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
            # Get the list of files in the directory
            subfolder = os.path.join('results', deployment)
            # Find the latest JSON file with "neighbors-data" in the file name
            subfile = os.path.join(subfolder, '*online-devices*.json')
            json_files = glob.glob(subfile)
            if not json_files:  # Check if json_files is empty
                return "No online devices found"
            latest_json_file = max(json_files, key=os.path.getctime)
            devices_df = pd.read_json(latest_json_file)
            
            return str(len(devices_df))
        except Exception as e:
            return {"error": str(e)}
    def _arun(self, deployment:str, new:bool) -> str:
        try:
            if new:
                # Get the latest data
                subprocess.call([sys.executable, "get-online-devices.py", "-d", deployment]) #, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
            # Get the list of files in the directory
            subfolder = os.path.join('results', deployment)
            # Find the latest JSON file with "neighbors-data" in the file name
            subfile = os.path.join(subfolder, '*online-devices*.json')
            json_files = glob.glob(subfile)
            if not json_files:  # Check if json_files is empty
                return "No online devices found"
            latest_json_file = max(json_files, key=os.path.getctime)
            devices_df = pd.read_json(latest_json_file)
            
            return str(len(devices_df))
        except Exception as e:
            return {"error": str(e)}

class GetNeighbors(BaseTool):
    name = "get_number_of_neighbors"
    description =  """Obtains data from the Shasta web user interface for the given deployment.
    Args:
        deployment (str): The deployment in which the controller is located (possible inputs: DF, dogfood, Production, PROD, STG, staging, development, DEV - should be mapped to DF, PROD, STG or DEV).
        new (bool): Whether to get the latest data or not. If not stated, it will be set to False.
    
    Returns:
        int: a number - all the devices of that deployment that are online
    """
    def _run(self, deployment:str, new:bool) -> str:
        try:
            if new:
                # Get the latest data
                subprocess.call([sys.executable, "get-online-devices.py", "-d", deployment]) #, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
            # Get the list of files in the directory
            subfolder = os.path.join('results', deployment)
            # Find the latest JSON file with "neighbors-data" in the file name
            subfile = os.path.join(subfolder, '*neighbors-data*.json')
            json_files = glob.glob(subfile)
            if not json_files:  # Check if json_files is empty
                return "No online devices found"
            latest_json_file = max(json_files, key=os.path.getctime)
            devices_df = pd.read_json(latest_json_file)
            print(devices_df)
            return str(len(devices_df))
        except Exception as e:
            return {"error": str(e)}

class AnalyzeDF(BaseTool):

    name = "analyze_df"
    description = "Analyze neighbors data from the Shasta web user interface for the given deployment. Uses smart data frame to analyze data."

    def _run(self, deployment:str, new:bool, input_question:str) -> str:
        """analyze neighbors data from the Shasta web user interface for the given deployment. uses smart data frame to analyze data.
        the question to ask the smart data frame should be provided, and the result will be returned as simple string.
        Args:
            deployment (str): The deployment in which the controller is located (possible inputs: DF, dogfood, Production, PROD, STG, staging, development, DEV - should be mapped to DF, PROD, STG or DEV).
            new (bool): Whether to get the latest data or not. If not stated, it will be set to False.
            input_question (str): The question to ask the smart data frame, it should not include the deployment name, only the request for analysis of the data.

        Returns:
            answer (str): anaylsis of the data according to the question provided by the user, in a simple string format
        """
        try:
            print("Analyzing data")
            if new:
                # Get the latest data
                subprocess.call([sys.executable, "get-online-devices.py", "-d", deployment]) #, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
            # Get the list of files in the directory
            subfolder = os.path.join('results', deployment)
            # Find the latest JSON file with "neighbors-data" in the file name
            subfile = os.path.join(subfolder, '*neighbors-data*.json')
            json_files = glob.glob(subfile)
            if not json_files:  # Check if json_files is empty
                return "No online devices found"
            latest_json_file = max(json_files, key=os.path.getctime)
            nr_df = pd.read_json(latest_json_file)
            smart_df = SmartDataframe(nr_df, config = {"llm": ollama_llm})
            responce = smart_df.chat(input_question + " respond in simple verbal text")
            print(responce)
            return responce
        except Exception as e:
            return {"error": str(e)}
class Analyze(BaseTool):
    name = "Analyze"
    description = "read an DF from json file and use pandasai to analyze it"

    def _run(self, query:str) -> str:
        try:
            # Get the list of files in the directory
            subfolder = os.path.join('results', deployment)
            # Find the latest JSON file with "neighbors-data" in the file name
            subfile = os.path.join(subfolder, '*neighbors-data*.json')
            json_files = glob.glob(subfile)
            if not json_files:  # Check if json_files is empty
                return "No online devices found"
            latest_json_file = max(json_files, key=os.path.getctime)
            nr_df = pd.read_json(latest_json_file)
            return query
        except Exception as e:
            return {"error": str(e)}
      
class CustomTool():
    def __init__(self):
        self.name = "CustomTool"
        self.description = "Custom tool to run a python script"
        self.run = self._run
        self.is_single_input = True 

    def _run(self, script:str, args:dict) -> str:
        try:
            subprocess.call([sys.executable, script, args]) #, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
            return "Script executed successfully"
        except Exception as e:
            return {"error": str(e)}
# Assuming analyze_neighbors, get_number_of_neighbors, and get_online_devices are your functions
#AnalyzeDF = StructuredTool.from_function(analyze_neighbors)
#GetNeighbors = StructuredTool.from_function(get_number_of_neighbors)
#GetOnlineDevices = StructuredTool.from_function(get_online_devices)

#tools = [GetOnlineDevices, GetNeighbors]
"""
functions = [
            {"name": "get_online_devices", "tool": GetOnlineDevices,
            "requires": ["deployment", "new"],
            "args": {"deployment": "DF", "new": False},
            "returns": "int: a number - all the devices of that deployment that are online"},
            {"name": "get_number_of_neighbors", "tool": GetNeighbors,
             "requires": ["deployment", "new"],
            "args": {"deployment": "DF", "new": False},
            "returns": "int: a number - all the devices of that deployment that are online"},
            {"name": "analyze_neighbors", "tool": AnalyzeDF,
            "requires": ["deployment", "new", "input_question"],
            "args": {"deployment": "DF", "new": False, "input_question": "What is the subject of the text?"}
            }
            ]
"""
#template = """
#agent_scratchpad: {agent_scratchpad}
#tool_names: {tool_names}
#tools: {tools}

#subject: What is the subject of the text?
#action: What is the action in the text?

#Format the text output as JSON with the following format:
#sentiment
#subject
#action

#text: {input_text}
#"""
llm = Ollama(model="llama3",
                 keep_alive=-1,
                 temperature=0,
                 callback_manager=CallbackManager([StreamingStdOutCallbackHandler()])
                 )

model = OllamaFunctions(model="llama3", format="json")
initial_chat_history = ['Hello', 'Hi', 'How are you?']
memory = ConversationBufferWindowMemory(
    memory_key='chat_history',
    k=3,
    return_messages=True,
    initial_memory={'chat_history': initial_chat_history}
)
tools = [CustomTool()]
agent = initialize_agent(
    tools, llm, memory, AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=True, handle_parsing_errors=True
)


if prompt := st.chat_input():
    st.chat_message("user").write(prompt)
    with st.chat_message("assistant"):
        st_callback = StreamlitCallbackHandler(st.container())
        response = agent.run(prompt, callbacks=[st_callback])
        st.write(response)