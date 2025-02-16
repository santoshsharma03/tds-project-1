from fastapi import FastAPI, HTTPException
import os
import json
import aiohttp
import re
from datetime import datetime
from typing import Dict, Any
import sqlite3
import glob
from dotenv import load_dotenv
import base64
import subprocess
import difflib
from dateutil.parser import parse
from fastapi.responses import PlainTextResponse
import shutil
import requests
import pandas as pd
from PIL import Image
from markdown import markdown
import duckdb

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# ---------------- Security Checks (B1 & B2) ----------------
def check_safe_path(file_path):
    """ Ensure the path is within the /data directory """
    if not file_path.startswith("/data/"):
        raise HTTPException(status_code=403, detail="Access outside /data is forbidden.")
    return file_path

# Disable deletion operations
os.remove = lambda *args, **kwargs: (_ for _ in ()).throw(
    HTTPException(status_code=403, detail="Deletion operations are not allowed.")
)
shutil.rmtree = lambda *args, **kwargs: (_ for _ in ()).throw(
    HTTPException(status_code=403, detail="Deletion operations are not allowed.")
)

# ---------------- AI Proxy for LLM Interactions ----------------
class AIProxy:
    def __init__(self, token: str):
        self.token = token
        self.api_url = "https://api.aiproxy.cloud/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    async def get_completion(self, prompt: str) -> str:
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7
            }
            async with session.post(self.api_url, headers=self.headers, json=payload) as response:
                if response.status != 200:
                    raise HTTPException(status_code=500, detail="AI Proxy request failed")
                data = await response.json()
                return data['choices'][0]['message']['content']

# ---------------- Task Handler ----------------
class TaskHandler:
    def __init__(self, ai_proxy: AIProxy):
        self.ai_proxy = ai_proxy

    async def handle_task(self, task_description: str) -> Dict[str, Any]:
        lower_task = task_description.lower()
        # Phase A Tasks
        if "datagen" in lower_task or "generate data" in lower_task:
            return await self.handle_datagen()
        elif "format" in lower_task and "prettier" in lower_task:
            return await self.handle_format_file()
        elif "wednesday" in lower_task:
            return await self.handle_count_wednesdays()
        elif "contact" in lower_task and "sort" in lower_task:
            return await self.handle_sort_contacts()
        elif "log" in lower_task and "recent" in lower_task:
            return await self.handle_recent_logs()
        elif "markdown" in lower_task and "docs" in lower_task:
            return await self.handle_extract_headers()
        elif "email" in lower_task and "sender" in lower_task:
            return await self.handle_extract_email()
        elif ("credit" in lower_task and "card" in lower_task) or ("credit_card.png" in lower_task):
            return await self.handle_extract_card(task_description)
        elif "comment" in lower_task and "similar" in lower_task:
            return await self.handle_similar_comments()
        elif "ticket" in lower_task and "gold" in lower_task:
            return await self.handle_ticket_sales()
        
        # Phase B Tasks
        elif "fetch data" in lower_task or "api" in lower_task:
            return await self.handle_fetch_api(task_description)
        elif "clone" in lower_task or "git" in lower_task:
            return await self.handle_git_operations(task_description)
        elif "sql query" in lower_task or "run sql" in lower_task:
            return await self.handle_run_sql(task_description)
        elif "scrape" in lower_task or "extract website" in lower_task:
            return await self.handle_scrape_website(task_description)
        elif "resize image" in lower_task or "compress image" in lower_task:
            return await self.handle_resize_image(task_description)
        elif "transcribe audio" in lower_task:
            return await self.handle_transcribe_audio(task_description)
        elif "convert markdown" in lower_task or "md to html" in lower_task:
            return await self.handle_md_to_html(task_description)
        elif "filter csv" in lower_task:
            return await self.handle_filter_csv(task_description)
        else:
            raise ValueError(f"Unknown task: {task_description}")

    # ---------------- PHASE B HANDLERS ----------------

    # B3: Fetch Data from API
    async def handle_fetch_api(self, task_description: str) -> Dict[str, Any]:
        url = "https://api.example.com"
        output_file = check_safe_path("/data/output.json")
        response = requests.get(url)
        if response.status_code == 200:
            with open(output_file, 'w') as f:
                json.dump(response.json(), f, indent=2)
            return {"status": "success", "output": output_file}
        else:
            raise HTTPException(status_code=500, detail="Failed to fetch data")

    # B4: Clone a Git Repo and Commit
    async def handle_git_operations(self, task_description: str) -> Dict[str, Any]:
        repo_url = "https://github.com/user/repo.git"
        repo_dir = check_safe_path("/data/repo")
        subprocess.run(["git", "clone", repo_url, repo_dir], check=True)
        subprocess.run(["git", "commit", "-am", "Automated commit"], cwd=repo_dir, check=True)
        return {"status": "success", "repo": repo_dir}

    # B5: Run SQL Query on SQLite or DuckDB
    async def handle_run_sql(self, task_description: str) -> Dict[str, Any]:
        db_file = check_safe_path("/data/database.db")
        query = "SELECT * FROM table_name;"
        conn = duckdb.connect(db_file)
        result = conn.execute(query).fetchall()
        conn.close()
        return {"status": "success", "result": result}

# ---------------- GLOBAL INIT ----------------
ai_proxy = AIProxy(os.environ.get("AIPROXY_TOKEN", ""))
task_handler = TaskHandler(ai_proxy)

@app.post("/run")
async def run_task(task: str):
    try:
        result = await task_handler.handle_task(task)
        return {"status": "success", "result": result}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/read", response_class=PlainTextResponse)
async def read_file(path: str):
    if not path.startswith("/data/"):
        raise HTTPException(status_code=400, detail="Access denied: Path must be within /data directory")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    with open(path, 'r') as file:
        content = file.read().strip()
    return content

@app.get("/")
def read_root():
    return {"message": "Welcome to the LLM-based Automation Agent API"}