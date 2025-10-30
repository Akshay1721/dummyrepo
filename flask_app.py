from flask import Flask, request, jsonify
import os
import requests
from dotenv import load_dotenv
from pathlib import Path

# load .env if present in the repo root (handles being run from other CWDs)
project_root = Path(__file__).resolve().parent
dotenv_path = project_root / ".env"
# attempt to load standard .env first
load_dotenv()  # load default .env if present in process CWD
if dotenv_path.exists():
	load_dotenv(dotenv_path=dotenv_path)

app = Flask(__name__)

GITHUB_API = "https://api.github.com"

@app.route("/create_pr", methods=["POST"])
def create_pr():
	try:
		data = request.get_json(force=True)
		# reject any attempt to provide a token in the payload
		if isinstance(data, dict) and ("token" in data or "GITHUB_TOKEN" in data):
			return jsonify(error="Do not send GitHub tokens in request payloads. Set GITHUB_TOKEN as an environment variable."), 400
		repo = data.get("repo")
		head = data.get("head")
		base = data.get("base", "main")
		title = data.get("title")
		body = data.get("body", "")
		# read token from environment (or .env loaded above); never from client payload
		token = os.environ.get("GITHUB_TOKEN")

		# fallback: try to parse .env in repo root if token still missing
		if not token and dotenv_path.exists():
			try:
				with dotenv_path.open("r", encoding="utf-8") as fh:
					for raw in fh:
						line = raw.strip()
						if not line or line.startswith("#"):
							continue
						# handle lines like: KEY=VALUE or KEY = VALUE
						if "=" in line:
							k, v = line.split("=", 1)
							if k.strip() == "GITHUB_TOKEN":
								token = v.strip().strip('\'"')
								break
			except Exception:
				# don't crash on file read errors; will return clear error below
				pass

		if not token:
			return jsonify(error="GITHUB_TOKEN not set in environment. Set GITHUB_TOKEN env var or add it to a .env in the repo root."), 500

		if not repo or not head or not title:
			return jsonify(error="Missing required fields: repo, head, title"), 400

		if "/" not in repo:
			return jsonify(error="repo must be in the form 'owner/repo'"), 400

		owner, repo_name = repo.split("/", 1)
		url = f"{GITHUB_API}/repos/{owner}/{repo_name}/pulls"
		payload = {"title": title, "head": head, "base": base, "body": body}
		headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}

		resp = requests.post(url, json=payload, headers=headers, timeout=10)
		if resp.status_code in (200, 201):
			j = resp.json()
			# include owner/repo and number for frontend convenience
			return jsonify(
				status="created",
				owner=owner,
				repo=repo_name,
				number=j.get("number"),
				state=j.get("state"),
				url=j.get("html_url"),
				raw=j
			)
		else:
			try:
				err = resp.json()
			except Exception:
				err = resp.text
			return jsonify(error="GitHub API error", details=err), resp.status_code
	except Exception as e:
		return jsonify(error=str(e)), 500

@app.route("/pr_status", methods=["GET"])
def pr_status():
	"""
	Query a PR by repo (owner/repo) and number. Example:
	GET /pr_status?repo=owner/repo&number=123
	"""
	try:
		repo = request.args.get("repo")
		number = request.args.get("number")
		if not repo or not number:
			return jsonify(error="Missing query parameters 'repo' and 'number'"), 400
		if "/" not in repo:
			return jsonify(error="repo must be in the form 'owner/repo'"), 400

		token = os.environ.get("GITHUB_TOKEN")
		# fallback same as above: try .env if missing
		if not token and dotenv_path.exists():
			try:
				with dotenv_path.open("r", encoding="utf-8") as fh:
					for raw in fh:
						line = raw.strip()
						if not line or line.startswith("#"):
							continue
						if "=" in line:
							k, v = line.split("=", 1)
							if k.strip() == "GITHUB_TOKEN":
								token = v.strip().strip('\'"')
								break
			except Exception:
				pass

		if not token:
			return jsonify(error="GITHUB_TOKEN not set in environment. Set GITHUB_TOKEN env var or add it to a .env in the repo root."), 500

		owner, repo_name = repo.split("/", 1)
		url = f"{GITHUB_API}/repos/{owner}/{repo_name}/pulls/{number}"
		headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}

		resp = requests.get(url, headers=headers, timeout=10)
		if resp.status_code == 200:
			j = resp.json()
			return jsonify(
				status="ok",
				owner=owner,
				repo=repo_name,
				number=j.get("number"),
				state=j.get("state"),
				url=j.get("html_url"),
				raw=j
			)
		else:
			try:
				err = resp.json()
			except Exception:
				err = resp.text
			return jsonify(error="GitHub API error", details=err), resp.status_code
	except Exception as e:
		return jsonify(error=str(e)), 500

@app.route("/list_prs", methods=["GET"])
def list_prs():
	try:
		repo = request.args.get("repo")
		state = request.args.get("state", "all")  # open, closed, all
		if not repo:
			return jsonify(error="Missing query parameter 'repo'"), 400
		if "/" not in repo:
			return jsonify(error="repo must be in the form 'owner/repo'"), 400

		# token retrieval (reuse existing logic)
		token = os.environ.get("GITHUB_TOKEN")
		if not token and dotenv_path.exists():
			try:
				with dotenv_path.open("r", encoding="utf-8") as fh:
					for raw in fh:
						line = raw.strip()
						if not line or line.startswith("#"):
							continue
						if "=" in line:
							k, v = line.split("=", 1)
							if k.strip() == "GITHUB_TOKEN":
								token = v.strip().strip('\'"')
								break
			except Exception:
				pass

		if not token:
			return jsonify(error="GITHUB_TOKEN not set in environment. Set GITHUB_TOKEN env var or add it to a .env in the repo root."), 500

		owner, repo_name = repo.split("/", 1)
		url = f"{GITHUB_API}/repos/{owner}/{repo_name}/pulls"
		headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
		params = {"state": state, "per_page": 100}
		resp = requests.get(url, headers=headers, params=params, timeout=10)
		if resp.status_code == 200:
			j = resp.json()
			# summarize PRs for frontend
			prs = []
			for p in j:
				prs.append({
					"number": p.get("number"),
					"title": p.get("title"),
					"state": p.get("state"),
					"url": p.get("html_url"),
					"head": p.get("head", {}).get("ref"),
					"base": p.get("base", {}).get("ref"),
					"user": p.get("user", {}).get("login")
				})
			return jsonify(status="ok", owner=owner, repo=repo_name, prs=prs)
		else:
			try:
				err = resp.json()
			except Exception:
				err = resp.text
			return jsonify(error="GitHub API error", details=err), resp.status_code
	except Exception as e:
		return jsonify(error=str(e)), 500

if __name__ == "__main__":
	# For local development only. Use a proper WSGI server for production.
	app.run(host="0.0.0.0", port=5000, debug=True)