# Shasta helper based on phidata + tools + pandasai

This is a streamlit based Assistant which includes sevral function calling for tools (analyze_neighbors with pandasai - ususally doesn't work, get_neighbors_df, get_number_of_neighbors, get_online_devices).

This allows you to choose an LLM model, as well as an embedding model to use for the files you can upload.

There is a


> Note: Fork and clone this repository if needed

### 1. [Install](https://github.com/ollama/ollama?tab=readme-ov-file#macos) ollama and pull models

Pull the LLM you'd like to use:

```shell
ollama pull phi3

ollama pull llama3
```

Pull the Embeddings model:

```shell
ollama pull nomic-embed-text
```

### 2. Create a virtual environment (optional)

```shell
python3 -m venv ~/.venvs/aienv
source ~/.venvs/aienv/bin/activate
```

### 3. Install libraries

```shell
pip install -r Assistant/requirements.txt
```

### 4. Run PgVector

> Install [docker desktop](https://docs.docker.com/desktop/install/mac-install/) first.


- run using the docker run command

```shell
docker run -d \
  -e POSTGRES_DB=ai \
  -e POSTGRES_USER=ai \
  -e POSTGRES_PASSWORD=ai \
  -e PGDATA=/var/lib/postgresql/data/pgdata \
  -v pgvolume:/var/lib/postgresql/data \
  -p 5532:5432 \
  --name pgvector \
  phidata/pgvector:16
```

### 5. Run RAG App

```shell
streamlit run app.py
```

- Open [localhost:8501](http://localhost:8501) to view your local RAG app.

- Add websites or PDFs and ask question.
- Example PDF: https://phi-public.s3.amazonaws.com/recipes/ThaiRecipes.pdf
- Example Websites:
  - https://techcrunch.com/2024/04/18/meta-releases-llama-3-claims-its-among-the-best-open-models-available/?guccounter=1
  - https://www.theverge.com/2024/4/23/24137534/microsoft-phi-3-launch-small-ai-language-model

