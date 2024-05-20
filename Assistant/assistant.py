from typing import Optional

from phi.assistant import Assistant
from phi.knowledge import AssistantKnowledge
from phi.llm.ollama import Ollama
from phi.embedder.ollama import OllamaEmbedder
from phi.vectordb.pgvector import PgVector2
from phi.storage.assistant.postgres import PgAssistantStorage
from phi.tools.file import FileTools
from phi.tools.csv_tools import CsvTools
from phi.tools.website import WebsiteTools
from phi.tools import Toolkit
import pandas as pd
from pandasai import SmartDataframe
from pandasai.llm.local_llm import LocalLLM
import subprocess
import os
import glob
import sys
from pathlib import Path

db_url = "postgresql+psycopg://ai:ai@localhost:5532/ai"
base_path = Path("/home/efi/ShastaChat")
os.path.dirname(base_path)
#Tools
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
            directory = os.path.join(base_path, 'results')
            subfolder = os.path.join(directory, deployment)
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
            deployment (str): The deployment in which the controller is located (possible inputs: DF (dogfood), PROD (Production), STG (staging), DEV (development)- should be mapped to DF, PROD, STG or DEV).
            new (bool): Whether to get the latest data or not. If not stated, it will be set to False.

        Returns:
            int: a number - all the devices of that deployment that are online
        """
        try:
            if new:
                # Get the latest data
                subprocess.call([sys.executable, "get-online-devices.py", "-d", deployment]) #, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
            # Get the list of files in the directory
            directory = os.path.join(base_path, 'results')
            subfolder = os.path.join(directory, deployment)
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
    def get_neighbors_df(self, deployment:str, new:bool) -> pd.DataFrame:
        """Obtains data from the Shasta web user interface for the given deployment.
        Args:
            deployment (str): The deployment in which the controller is located (possible inputs: DF (dogfood), PROD (Production), STG (staging), DEV (development)- should be mapped to DF, PROD, STG or DEV).
            new (bool): Whether to get the latest data or not. If not stated, it will be set to False.

        Returns:
            pd.DataFrame: a dataframe with all the neighbors of that deployment
        """
        try:
            if new:
                # Get the latest data
                subprocess.call([sys.executable, "get-online-devices.py", "-d", deployment]) #, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
            # Get the list of files in the directory
            directory = os.path.join(base_path, 'results')
            subfolder = os.path.join(directory, deployment)
            # Find the latest JSON file with "neighbors-data" in the file name
            subfile = os.path.join(subfolder, '*neighbors-data*.json')
            json_files = glob.glob(subfile)
            if not json_files:  # Check if json_files is empty
                return "No online devices found"
            latest_json_file = max(json_files, key=os.path.getctime)
            devices_df = pd.read_json(latest_json_file)
            return devices_df
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
            directory = os.path.join(base_path, 'results')
            subfolder = os.path.join(directory, deployment)
            # Find the latest JSON file with "neighbors-data" in the file name
            subfile = os.path.join(subfolder, '*neighbors-data*.json')
            json_files = glob.glob(subfile)
            if not json_files:  # Check if json_files is empty
                return "No online devices found. Or no cuncurrent data found in directory."
            latest_json_file = max(json_files, key=os.path.getctime)
            nr_df = pd.read_json(latest_json_file)
            smart_df = SmartDataframe(nr_df, config = {"llm": LocalLLM(api_base="http://localhost:11434/v1", model="llama2")})
            responce = smart_df.chat(input_question)
            print(responce)
            return responce
        except Exception as e:
            return {"error": str(e)}

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
        name="Shasta Helper",
        run_id=run_id,
        user_id=user_id,
        llm=Ollama(model=llm_model),
        tools = [AnalyzeDF().analyze_neighbors,GetNeighbors().get_number_of_neighbors, GetOnlineDevices().get_online_devices, GetNeighbors().get_neighbors_df], 
        show_tool_calls=True,
        storage=PgAssistantStorage(table_name="local_rag_assistant", db_url=db_url),
        knowledge_base=knowledge,
        prevent_hallucinations = True,
        description="You are an AI that help people with obtaining data from Shasta web user interface. You don't make up information that you don't have. You run the proper tool (from the ones you have in your list) and give informative polite responses,saying what you understand and doanalys. If needed, you can ask for more information to clarify the user's question. No markdown is needed, answer stright farward plain text",
        instructions=[
            "The user will want to have fully informative answer to a question it will ask, you will need to provide the answer to the question by calling the proper tool and executing it, if you don't have the answer you will need to ask for more information to clarify the user's question.",
            "When a user asks a question, you will be provided with information about the question.",
            "Carefully read this information and provide a clear and concise answer to the user.",
            "Do not use phrases like 'based on my knowledge' or 'depending on the information'.",
        ],
        # Uncomment this setting adds chat history to the messages
        add_chat_history_to_messages=True,
        # Uncomment this setting to customize the number of previous messages added from the chat history
        num_history_messages=300,
        # This setting adds references from the knowledge_base to the user prompt
        add_references_to_prompt=True,
        # This setting tells the LLM to format messages in markdown
        markdown=True,
        add_datetime_to_instructions=True,
        debug_mode=debug_mode
    )
