# main.py
from fastapi import FastAPI, HTTPException, UploadFile, File
import os
import json
import aiohttp
import re
from datetime import datetime
from typing import Dict, Any, List
import sqlite3
from pathlib import Path
import subprocess
import glob
from dotenv import load_dotenv
import numpy as np
from PIL import Image
import io

# Load environment variables
load_dotenv()

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

class TaskHandler:
    def __init__(self, ai_proxy: AIProxy):
        self.ai_proxy = ai_proxy
        
    async def handle_sort_contacts(self, task_description: str) -> Dict[str, Any]:
        input_file = "/data/contacts.json"
        output_file = "/data/contacts-sorted.json"
        
        with open(input_file, 'r') as f:
            contacts = json.load(f)
            
        # Sort contacts by last_name, then first_name
        sorted_contacts = sorted(
            contacts,
            key=lambda x: (x['last_name'], x['first_name'])
        )
        
        with open(output_file, 'w') as f:
            json.dump(sorted_contacts, f, indent=2)
            
        return {"status": "success", "contacts_sorted": len(sorted_contacts)}

    async def handle_recent_logs(self, task_description: str) -> Dict[str, Any]:
        log_dir = "/data/logs/"
        output_file = "/data/logs-recent.txt"
        
        # Get all log files and sort by modification time
        log_files = glob.glob(f"{log_dir}*.log")
        recent_logs = sorted(
            log_files,
            key=lambda x: os.path.getmtime(x),
            reverse=True
        )[:10]
        
        # Extract first line from each log
        first_lines = []
        for log_file in recent_logs:
            with open(log_file, 'r') as f:
                first_lines.append(f.readline().strip())
                
        # Write to output file
        with open(output_file, 'w') as f:
            f.write('\n'.join(first_lines))
            
        return {"status": "success", "logs_processed": len(first_lines)}

    async def handle_extract_headers(self, task_description: str) -> Dict[str, Any]:
        docs_dir = "/data/docs/"
        output_file = "/data/docs/index.json"
        
        # Find all markdown files
        md_files = glob.glob(f"{docs_dir}**/*.md", recursive=True)
        headers = {}
        
        for md_file in md_files:
            with open(md_file, 'r') as f:
                content = f.read()
                # Find first H1 header
                match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
                if match:
                    # Remove /data/docs/ prefix from filename
                    relative_path = os.path.relpath(md_file, docs_dir)
                    headers[relative_path] = match.group(1)
                    
        with open(output_file, 'w') as f:
            json.dump(headers, f, indent=2)
            
        return {"status": "success", "files_processed": len(headers)}

    async def handle_extract_email(self, task_description: str) -> Dict[str, Any]:
        input_file = "/data/email.txt"
        output_file = "/data/email-sender.txt"
        
        with open(input_file, 'r') as f:
            email_content = f.read()
            
        prompt = f"""Extract just the sender's email address from this email:
        {email_content}
        Return only the email address, nothing else."""
        
        email = await self.ai_proxy.get_completion(prompt)
        
        with open(output_file, 'w') as f:
            f.write(email.strip())
            
        return {"status": "success", "email": email.strip()}

    async def handle_extract_card(self, task_description: str) -> Dict[str, Any]:
        input_file = "/data/credit-card.png"
        output_file = "/data/credit-card.txt"
        
        with open(input_file, 'rb') as f:
            image_data = f.read()
            
        # Convert image to base64 for AI Proxy
        image_base64 = base64.b64encode(image_data).decode()
        
        prompt = f"""Extract the credit card number from this image.
        Return only the numbers, no spaces or other characters."""
        
        # Note: Adjust this based on actual AI Proxy image handling capabilities
        card_number = await self.ai_proxy.get_completion(prompt)
        
        # Remove any non-digit characters
        card_number = re.sub(r'\D', '', card_number)
        
        with open(output_file, 'w') as f:
            f.write(card_number)
            
        return {"status": "success", "card_number": card_number}

    async def handle_ticket_sales(self, task_description: str) -> Dict[str, Any]:
        db_file = "/data/ticket-sales.db"
        output_file = "/data/ticket-sales-gold.txt"
        
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT SUM(units * price)
            FROM tickets
            WHERE type = 'Gold'
        """)
        
        total_sales = cursor.fetchone()[0]
        conn.close()
        
        with open(output_file, 'w') as f:
            f.write(str(total_sales))
            
        return {"status": "success", "total_sales": total_sales}

    # Phase B Business Tasks
    async def handle_api_fetch(self, task_description: str) -> Dict[str, Any]:
        # Extract API details using LLM
        prompt = f"""From this task: '{task_description}'
        Extract:
        1. API URL
        2. Output file path
        Return as JSON: {{"url": "...", "output": "..."}}"""
        
        params = json.loads(await self.ai_proxy.get_completion(prompt))
        
        # Ensure output path is in /data
        if not params['output'].startswith('/data/'):
            params['output'] = f"/data/{params['output']}"
            
        async with aiohttp.ClientSession() as session:
            async with session.get(params['url']) as response:
                data = await response.text()
                
        with open(params['output'], 'w') as f:
            f.write(data)
            
        return {"status": "success", "bytes_written": len(data)}

    async def handle_git_operations(self, task_description: str) -> Dict[str, Any]:
        # Only allow operations in /data directory
        work_dir = "/data/git_repos"
        os.makedirs(work_dir, exist_ok=True)
        
        # Extract git operations using LLM
        prompt = f"""From this task: '{task_description}'
        Extract:
        1. Repository URL
        2. Commit message
        Return as JSON: {{"repo": "...", "message": "..."}}"""
        
        params = json.loads(await self.ai_proxy.get_completion(prompt))
        
        # Clone repo
        repo_name = params['repo'].split('/')[-1].replace('.git', '')
        repo_path = os.path.join(work_dir, repo_name)
        
        subprocess.run(['git', 'clone', params['repo'], repo_path], check=True)
        
        # Make commit
        os.chdir(repo_path)
        subprocess.run(['git', 'add', '.'], check=True)
        subprocess.run(['git', 'commit', '-m', params['message']], check=True)
        
        return {"status": "success", "repo": repo_name}

app = FastAPI()
ai_proxy = AIProxy(os.environ["AIPROXY_TOKEN"])
task_handler = TaskHandler(ai_proxy)

@app.post("/run")
async def run_task(task: str):
    try:
        # Security check: ensure task only accesses /data directory
        if re.search(r'(?i)/(?!data/)[a-z]+/', task):
            raise HTTPException(
                status_code=400,
                detail="Access denied: Operations restricted to /data directory"
            )
            
        # Identify and execute task
        result = await task_handler.handle_task(task)
        return {"status": "success", "result": result}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/read")
async def read_file(path: str):
    try:
        # Security check: ensure path is within /data
        if not path.startswith("/data/"):
            raise HTTPException(
                status_code=400,
                detail="Access denied: Path must be within /data directory"
            )
            
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail=f"File not found: {path}")
            
        with open(path, 'r') as file:
            content = file.read()
            return content
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)