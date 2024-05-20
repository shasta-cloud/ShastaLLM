import langchain
from langchain_community.chat_models import ChatOllama
from langchain_community.llms import Ollama
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
from langchain.chains.summarize import load_summarize_chain
from langchain_community.document_loaders import WebBaseLoader, JSONLoader, UnstructuredFileLoader, DataFrameLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import chroma
from langchain_chroma import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_community.embeddings.ollama import OllamaEmbeddings
from langchain_community.vectorstores.utils import filter_complex_metadata
import gradio as gr
import os
import bs4

from pandasai import SmartDataframe
from pandasai.llm.local_llm import LocalLLM

import streamlit as st
from langchain.callbacks import StreamlitCallbackHandler
import requests
import json
from pathlib import Path
from pprint import pprint
import time

import sys
import glob
import pandas as pd
#deployments = ["DF", "PROD", "STG", "DEV"]
files = []

    #devices_df = pd.read_json(latest_json_file)
def load_and_retrieve_docs(deployment):
  
    # Get the list of files in the directory
    subfolder = os.path.join('results', deployment)
    # Find the latest JSON file with "online-devices" in the file name
    subfile = os.path.join(subfolder, '*online-devices*.json')
    json_files = glob.glob(subfile)

    latest_json_file = max(json_files, key=os.path.getctime)
    files.append(latest_json_file)
    subfile = os.path.join(subfolder, '*neighbors-data*.json')
    json_files = glob.glob(subfile)


    latest_json_file = max(json_files, key=os.path.getctime)
    files.append(latest_json_file)
    subfile = os.path.join(subfolder, '*survey-data*.json')
    json_files = glob.glob(subfile)

    latest_json_file = max(json_files, key=os.path.getctime)
    files.append(latest_json_file)


    for file_path in files:
        docs = json.loads(Path(file_path).read_text())
        df = pd.DataFrame(docs)
        # Load the files
        loader = DataFrameLoader(df, page_content_column="mac")
        docs = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=2500)
    splits = text_splitter.split_documents(docs)

    # Create Ollama embeddings and vector store
    embeddings = OllamaEmbeddings(model = "llama3")
    vectorstore = Chroma.from_documents(splits, embeddings)

    # Create a retrivere
    return vectorstore.as_retriever()


def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

# Define the Ollama LLM function
def ollama_llm (question, context):
    formated_prompt = f"Question: {question}\n\nContext: {context}"
    llm = ChatOllama(model = 'llama3', format = "json" , temperature=0,  messages = [{'role': 'user', 'content': formated_prompt}])
    response = llm.invoke(formated_prompt)
    return response

# Define the RAG chain
def rag_chain(question,deployment):
 retriever = load_and_retrieve_docs(deployment)
 retrived_docs = retriever.invoke(question, n_results=1)
 print(retrived_docs)
 formatted_context = format_docs(retrived_docs)
 responce = ollama_llm(question, formatted_context)
 return responce

iface = gr.Interface(
    fn=rag_chain,
    inputs=["text", "text"],
    outputs="text",
    title="RAG Chat",
    description="Chat with the RAG model to get answers to your questions"
)
# Use the RAG chain
result = rag_chain("say hello, tell me what you can do in DF deployment", "DF")
pprint(result)
iface.launch()