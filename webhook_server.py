from flask import Flask, request
import requests
import json
from datetime import datetime
from dotenv import load_dotenv
import os
from openai import OpenAI

# Load .env file
load_dotenv()

app = Flask(__name__)

# Initialize OpenAI client
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Configuration from environment variables
DISCORD_WEBHOOK_URLS = {
    'github_feeds': os.getenv('FEEDS_WEBHOOK'),
    'changelog': os.getenv('CHANGELOG_WEBHOOK'),
    'issues': os.getenv('ISSUES_WEBHOOK')
}

def generate_changelog(commit_data):
    """Generate changelog using OpenAI"""
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """คุณคือผู้เขียน changelog ที่มีความเชี่ยวชาญ 
                    กรุณาสรุปการเปลี่ยนแปลงของ commit เป็นภาษาไทยที่เข้าใจง่าย 
                    ใช้ emoji ที่เหมาะสม และจัดรูปแบบให้สวยงาม"""
                },
                {
                    "role": "user",
                    "content": f"สร้าง changelog จาก commit นี้: {commit_data}"
                }
            ],
            max_tokens=150
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"OpenAI Error: {e}")
        return None

def send_to_discord_webhook(message, webhook_type='github_feeds'):
    """Send message to Discord webhook"""
    try:
        webhook_url = DISCORD_WEBHOOK_URLS.get(webhook_type)
        if webhook_url:
            payload = {
                "content": message,
                "username": "GitHub Bot",
                "avatar_url": "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png"
            }
            response = requests.post(webhook_url, json=payload)
            response.raise_for_status()
            print(f"Message sent to Discord ({webhook_type})")
        else:
            print(f"No webhook URL configured for {webhook_type}")
    except Exception as e:
        print(f"Error sending to Discord: {e}")

def format_commit_message(data):
    """Format commit message"""
    try:
        commits = data.get('commits', [])
        repository = data.get('repository', {}).get('name', 'unknown')
        ref = data.get('ref', '').split('/')[-1]
        
        messages = []
        for commit in commits:
            message = (
                f"{commit.get('id', '')[:7]}\n"
                f"[{repository}:{ref}] 1 new commit\n"
                f"{commit.get('message', '')} - {commit.get('author', {}).get('name', 'Unknown')}"
            )
            messages.append({
                'formatted': message,
                'raw': {
                    'id': commit.get('id', '')[:7],
                    'repo': repository,
                    'branch': ref,
                    'message': commit.get('message', ''),
                    'author': commit.get('author', {}).get('name', 'Unknown'),
                    'timestamp': commit.get('timestamp', datetime.utcnow().isoformat())
                }
            })
        
        return messages
    except Exception as e:
        print(f"Error formatting commit message: {e}")
        return []

def format_issue_message(data, event_type):
    """Format issue message"""
    try:
        repository = data.get('repository', {}).get('full_name', 'unknown')
        sender = data.get('sender', {}).get('login', 'unknown')
        issue = data.get('issue', {})
        
        if event_type == 'issues':
            action = data.get('action', 'unknown')
            message = (
                f"{sender}\n"
                f"[{repository}] Issue {action}: #{issue.get('number', '?')} "
                f"{issue.get('title', '')}\n"
                f"{issue.get('body', '')}"
            )
        elif event_type == 'issue_comment':
            comment = data.get('comment', {})
            message = (
                f"{sender}\n"
                f"[{repository}] New comment on issue #{issue.get('number', '?')}: "
                f"{issue.get('title', '')}\n"
                f"{comment.get('body', '')}"
            )
        else:
            message = f"Unsupported event type: {event_type}"
        
        return message
    except Exception as e:
        print(f"Error formatting issue message: {e}")
        return "Error formatting message"

@app.route("/")
def home():
    return "GitHub Webhook Server is Running!"

@app.route("/webhook", methods=["POST"])
def github_webhook():
    try:
        event_type = request.headers.get('X-GitHub-Event')
        data = request.json
        
        print(f"Received {event_type} webhook at {datetime.utcnow()}")
        
        if event_type == "push":
            messages = format_commit_message(data)
            for message in messages:
                # สร้างและส่ง changelog
                changelog = generate_changelog(json.dumps(message['raw'], ensure_ascii=False))
                if changelog:
                    send_to_discord_webhook(changelog, 'changelog')
                
        elif event_type in ["issues", "issue_comment"]:
            message = format_issue_message(data, event_type)
        
        return {"status": "success", "event": event_type}, 200
        
    except Exception as e:
        print(f"Error processing webhook: {e}")
        return {"status": "error", "message": str(e)}, 500

@app.route("/test", methods=["GET"])
def test():
    return {
        "status": "running",
        "time": datetime.utcnow().isoformat(),
        "configured_webhooks": list(DISCORD_WEBHOOK_URLS.keys())
    }

if __name__ == "__main__":
    # Run the Flask app
    port = int(os.getenv('PORT', 5000))
    app.run(host="0.0.0.0", port=port)