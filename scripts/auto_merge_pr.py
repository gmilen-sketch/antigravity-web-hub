#!/usr/bin/env python3
"""
Automated GitHub Pull Request creation and merge script for cloud-gtm repositories.
Bypasses manual web UI clicking when GITHUB_TOKEN or GH_TOKEN is provided.
"""

import os
import sys
import json
import urllib.request
import urllib.error
import subprocess

REPO = "cloud-gtm/antigravity-web-hub"
API_URL = f"https://api.github.com/repos/{REPO}"

def get_current_branch():
    return subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()

def auto_merge():
    branch = get_current_branch()
    if branch in ("main", "master"):
        print(f"Already on '{branch}' branch.")
        return

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    
    if not token:
        print(f"\n→ Branch '{branch}' is pushed to origin.")
        print(f"→ To auto-merge via CLI, export GITHUB_TOKEN=<your_token>.")
        print(f"→ 1-Click Merge URL: https://github.com/{REPO}/compare/main...{branch}?expand=1\n")
        return

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }

    # 1. Create PR
    pr_payload = {
        "title": f"Merge {branch} into main",
        "head": branch,
        "base": "main",
        "body": "Automated pull request to merge feature updates into main."
    }
    
    pr_number = None
    try:
        req = urllib.request.Request(f"{API_URL}/pulls", data=json.dumps(pr_payload).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            pr_number = data.get("number")
            print(f"✓ Created Pull Request #{pr_number}: {data.get('html_url')}")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        if "A pull request already exists" in err_body:
            # Fetch existing PR
            req = urllib.request.Request(f"{API_URL}/pulls?head=cloud-gtm:{branch}&state=open", headers=headers)
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
                if data:
                    pr_number = data[0]["number"]
                    print(f"✓ Found existing open Pull Request #{pr_number}")
        else:
            print(f"Error creating PR: {err_body}")
            return

    if not pr_number:
        print("Could not determine PR number.")
        return

    # 2. Merge PR
    try:
        merge_payload = {
            "commit_title": f"Merge pull request #{pr_number} from cloud-gtm/{branch}",
            "merge_method": "merge"
        }
        req = urllib.request.Request(f"{API_URL}/pulls/{pr_number}/merge", data=json.dumps(merge_payload).encode(), headers=headers, method="PUT")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            if data.get("merged"):
                print(f"🚀 Successfully auto-merged PR #{pr_number} into main!")
            else:
                print(f"Merge status: {data.get('message')}")
    except urllib.error.HTTPError as e:
        print(f"Error merging PR #{pr_number}: {e.read().decode()}")

if __name__ == "__main__":
    auto_merge()
