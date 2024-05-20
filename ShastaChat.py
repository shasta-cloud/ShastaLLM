from phi.assistant import Assistant
from phi.tools.duckduckgo import DuckDuckGo
from phi.llm.ollama import Ollama
from phi.tools import Toolkit
from phi.document import Document
from phi.utils.log import logger
from phi.storage.assistant.postgres import PgAssistantStorage
from phi.embedder.ollama import OllamaEmbedder
from phi.vectordb.pgvector import PgVector2
from phi.knowledge import AssistantKnowledge

import subprocess

#from langchain_community.llms import Ollama
from pandasai import SmartDataframe
from pandasai.llm.local_llm import LocalLLM
from typing import Any, List, Optional
from textwrap import dedent
import streamlit as st
import requests
import json
import time

import sys
import os
import glob
import pandas as pd
ollama_llm = LocalLLM(api_base="http://localhost:11434/v1", model="llama3")
db_url = "postgresql+psycopg://ai:ai@localhost:5532/ai"

class GetOnlineDevices(Toolkit):
    def __init__(self):
        super().__init__()
    def get_online_devices(self, deployment:str, new:bool) -> str:
        """Obtains data from the Shasta web user interface for the given deployment.
        Args:
            deployment (str): The deployment in which the controller is located (possible inputs: DF, dogfood, Production, PROD, STG, staging, development, DEV - should be mapped to DF, PROD, STG or DEV).
            new (bool): Whether to get the latest data or not. If not stated, it will be set to False.

        Returns:
            int: a number - all the devices of that deployment that are online
        """
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
 

class GetNeighbors(Toolkit):
    def __init__(self):
        super().__init__()
    def get_number_of_neighbors(self, deployment:str, new:bool) -> str:
        """Obtains data from the Shasta web user interface for the given deployment.
        Args:
            deployment (str): The deployment in which the controller is located (possible inputs: DF, dogfood, Production, PROD, STG, staging, development, DEV - should be mapped to DF, PROD, STG or DEV).
            new (bool): Whether to get the latest data or not. If not stated, it will be set to False.

        Returns:
            int: a number - all the devices of that deployment that are online
        """
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
        

class AnalyzeDF(Toolkit):
    def __init__(self):
        super().__init__()
    def analyze_neighbors(self, deployment:str, new:bool, input_question:str) -> str:
        """analyze neighbors data from the Shasta web user interface for the given deployment. uses smart data frame to analyze data.
        the question to ask the smart data frame should be provided, and the result will be returned as simple string.
        Args:
            deployment (str): The deployment in which the controller is located (possible inputs: DF, dogfood, Production, PROD, STG, staging, development, DEV - should be mapped to DF, PROD, STG or DEV).
            new (bool): Whether to get the latest data or not. If not stated, it will be set to False.
            input_question (str): The question to ask the smart data frame, it should not include the deployment name, only the request for analysis of the data.

        Returns:
            answer (str): anaylsis of the data according to the question provided by the user, in a simple string format
            smart_df (SmartDataframe): the smart data frame object that was used to analyze the data
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
            return responce, smart_df
        except Exception as e:
            return {"error": str(e)}

# Define a function to search for text in a Python object
def search(obj, text):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if text in key or search(value, text):
                return True
    elif isinstance(obj, list):
        for item in obj:
            if search(item, text):
                return True
    elif isinstance(obj, str):
        if text in obj:
            return True
    return False        


db_url = "postgresql+psycopg://ai:ai@localhost:5532/ai"


def get_rag_assistant(
    llm_model: str = "llama3",
    embeddings_model: str = "nomic-embed-text",
    user_id: Optional[str] = None,
    run_id: Optional[str] = None,
    debug_mode: bool = True,
) -> Assistant:
    """Get a Local RAG Assistant."""

    # Define the embedder based on the embeddings model
    embedder = OllamaEmbedder(model=embeddings_model, dimensions=4096)
    embeddings_model_clean = embeddings_model.replace("-", "_")
    if embeddings_model == "nomic-embed-text":
        embedder = OllamaEmbedder(model=embeddings_model, dimensions=768)
    elif embeddings_model == "phi3":
        embedder = OllamaEmbedder(model=embeddings_model, dimensions=3072)
    # Define the knowledge base
    knowledge = AssistantKnowledge(
        vector_db=PgVector2(
            db_url=db_url,
            collection=f"local_rag_documents_{embeddings_model_clean}",
            embedder=embedder,
        ),
        # 3 references are added to the prompt
        num_documents=3,
    )

    return Assistant(
        name="local_rag_assistant",
        run_id=run_id,
        user_id=user_id,
        llm=Ollama(model=llm_model),
        storage=PgAssistantStorage(table_name="local_rag_assistant", db_url=db_url),
        knowledge_base=knowledge,
        description="You are an AI called 'RAGit' and your task is to answer questions using the provided information",
        instructions=[
            "When a user asks a question, you will be provided with information about the question.",
            "Carefully read this information and provide a clear and concise answer to the user.",
            "Do not use phrases like 'based on my knowledge' or 'depending on the information'.",
        ],
        # Uncomment this setting adds chat history to the messages
        # add_chat_history_to_messages=True,
        # Uncomment this setting to customize the number of previous messages added from the chat history
        # num_history_messages=3,
        # This setting adds references from the knowledge_base to the user prompt
        add_references_to_prompt=True,
        # This setting tells the LLM to format messages in markdown
        markdown=True,
        add_datetime_to_instructions=True,
        debug_mode=debug_mode,
    )


assistant = Assistant(
    llm = Ollama(model="llama3"),
    tools = [ GetOnlineDevices().get_online_devices, GetNeighbors().get_number_of_neighbors, AnalyzeDF().analyze_neighbors],
    use_tools = True,
    description="You are an AI that help people with obtaining data from Shasta web user interface. You don't make up information that you don't have. You run the proper tool and give informative polite responses,saying what you understand and doanalys. If needed, you can ask for more information to clarify the user's question. No markdown is needed, answer stright farward plain text",
    instructions = ["The user will want to have fully informative answer to a question it will ask, you will need to provide the answer to the question by calling the proper tool and executing it, if you don't have the answer you will need to ask for more information to clarify the user's question."],
    prevent_hallucinations = True,
    run_name = "Shasta Helper",
    debug=True,
    show_tool_calls=True
    )

st.set_page_config(
    page_title="Local RAG",
    page_icon=":orange_heart:",
)

st.title("Shasta Helper")
prompt = st.text_area("Ask me somthing - ")
upload = st.file_uploader("Upload a file")

#AnalyzeDF().analyze_neighbors("DF", False, "say hello")

if st.button("Generate Response") and upload is not None:
    df = pd.read_json(upload)
    smart_df = SmartDataframe(df, config = {"llm": ollama_llm})
    st.write(df)
else:
    response = assistant.chat(prompt)
    st.write(response)



    
#while(True):
#   AnalyzeDF().analyze_neighbors("DF", False, input("Ask me somthing - "))
   #assistant.print_response(input("Ask me somthing - "), markdown=False, stream=False)

# AnalyzeDF().analyze_neighbors