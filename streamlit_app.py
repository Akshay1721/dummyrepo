import streamlit as st
import requests

st.set_page_config(page_title="Git PR Creator", layout="centered")

# Security note: never paste personal access tokens into forms or chat.
st.warning("Do NOT paste GitHub personal access tokens into this app or chat. Set GITHUB_TOKEN as an environment variable for the backend (e.g. in a local .env file). Revoke any token you already pasted publicly and create a new one.")

BACKEND_URL = "http://localhost:5000"

# Initialize session state containers
if "prs" not in st.session_state:
	st.session_state["prs"] = []  # list of dicts: owner, repo, number, title, state, url, raw
# add view state initialization
if "view" not in st.session_state:
	st.session_state["view"] = "form"
if "current_repo" not in st.session_state:
	st.session_state["current_repo"] = None

def add_pr_to_session(pr_info):
	# Normalize and append
	entry = {
		"owner": pr_info.get("owner"),
		"repo": pr_info.get("repo"),
		"number": pr_info.get("number"),
		"title": pr_info.get("raw", {}).get("title") if pr_info.get("raw") else pr_info.get("title"),
		"state": pr_info.get("state"),
		"url": pr_info.get("url"),
		"raw": pr_info.get("raw", {})
	}
	st.session_state["prs"].append(entry)

def refresh_all_statuses():
	updated = []
	for pr in list(st.session_state["prs"]):
		repo_full = f"{pr['owner']}/{pr['repo']}"
		try:
			resp = requests.get(f"{BACKEND_URL}/pr_status", params={"repo": repo_full, "number": pr["number"]}, timeout=10)
			if resp.status_code == 200:
				j = resp.json()
				pr["state"] = j.get("state")
				pr["url"] = j.get("url")
				pr["raw"] = j.get("raw", {})
			else:
				# keep existing state and attach error detail
				try:
					err = resp.json()
				except Exception:
					err = resp.text
				pr["error"] = err
		except Exception as e:
			pr["error"] = str(e)
		updated.append(pr)
	st.session_state["prs"] = updated

def show_pr_table():
	if not st.session_state["prs"]:
		st.info("No PRs created in this session yet.")
		return
	st.subheader("Created PRs")
	# Display a simple table
	rows = []
	for p in st.session_state["prs"]:
		rows.append({
			"repository": f"{p['owner']}/{p['repo']}",
			"number": p["number"],
			"title": p.get("title") or p.get("raw", {}).get("title"),
			"state": p.get("state"),
			"url": p.get("url")
		})
	st.table(rows)
	cols = st.columns([1,1,1])
	if cols[0].button("Refresh statuses"):
		refresh_all_statuses()
		return  # let Streamlit re-run naturally
	if cols[1].button("Clear PRs"):
		st.session_state["prs"] = []
		return  # let Streamlit re-run naturally

def show_repo_prs():
	st.title("Repository Pull Requests")
	repo = st.session_state.get("current_repo")
	if not repo:
		st.error("No repository selected.")
		if st.button("Back"):
			st.session_state["view"] = "form"
			return
		return

	st.write(f"Showing PRs for: {repo}")
	cols = st.columns([1,1,1])
	if cols[0].button("Refresh PR list"):
		st.session_state.pop("repo_prs_cache", None)  # force refresh
	if cols[1].button("Back to form"):
		st.session_state["view"] = "form"
		return

	# cached fetch to avoid repeated calls per render
	if "repo_prs_cache" not in st.session_state:
		try:
			resp = requests.get(f"{BACKEND_URL}/list_prs", params={"repo": repo, "state": "all"}, timeout=10)
			if resp.status_code == 200:
				j = resp.json()
				st.session_state["repo_prs_cache"] = j.get("prs", [])
			else:
				try:
					err = resp.json()
				except Exception:
					err = resp.text
				st.error(f"Failed to fetch PRs ({resp.status_code}): {err}")
				st.session_state["repo_prs_cache"] = []
		except Exception as e:
			st.error(f"Failed to call backend: {e}")
			st.session_state["repo_prs_cache"] = []

	prs = st.session_state.get("repo_prs_cache", [])
	if not prs:
		st.info("No pull requests found for this repository.")
		return

	# display PRs as a table
	rows = []
	for p in prs:
		rows.append({
			"number": p.get("number"),
			"title": p.get("title"),
			"state": p.get("state"),
			"head": p.get("head"),
			"base": p.get("base"),
			"url": p.get("url")
		})
	st.table(rows)

def show_form():
	st.title("Create GitHub Pull Request")
	st.write("Provide repository (owner/repo), feature branch (head), base branch, PR title and description.")
	show_pr_table()

	# --- Test data prefill support ---
	# initialize test input storage if missing
	if "input_repo" not in st.session_state:
		st.session_state["input_repo"] = ""
		st.session_state["input_head"] = ""
		st.session_state["input_base"] = "main"
		st.session_state["input_title"] = ""
		st.session_state["input_body"] = ""

	# button to fill sample/test values
	if st.button("Fill test data"):
		st.session_state["input_repo"] = "octocat/Hello-World"
		st.session_state["input_head"] = "feature-branch"
		st.session_state["input_base"] = "main"
		st.session_state["input_title"] = "Add example feature"
		st.session_state["input_body"] = "This PR adds an example feature for testing."
		return  # let Streamlit re-run naturally
	# --- end test data support ---

	with st.form("pr_form"):
		# use session_state-stored defaults so "Fill test data" works
		repo = st.text_input("Repository (owner/repo)", value=st.session_state.get("input_repo", ""))
		head = st.text_input("Feature branch (head)", value=st.session_state.get("input_head", ""))
		base = st.text_input("Base/main branch", value=st.session_state.get("input_base", "main"))
		title = st.text_input("PR Title", value=st.session_state.get("input_title", ""))
		body = st.text_area("PR Description", value=st.session_state.get("input_body", ""))
		use_flask = st.checkbox("Use Flask API (http://localhost:5000)", value=True)
		submit = st.form_submit_button("Create PR")
		if submit:
			payload = {
				"repo": repo.strip(),
				"head": head.strip(),
				"base": base.strip(),
				"title": title.strip(),
				"body": body.strip()
			}
			# clear the stored input defaults so the form resets after submit
			st.session_state["input_repo"] = ""
			st.session_state["input_head"] = ""
			st.session_state["input_base"] = "main"
			st.session_state["input_title"] = ""
			st.session_state["input_body"] = ""
			if use_flask:
				try:
					resp = requests.post(f"{BACKEND_URL}/create_pr", json=payload, timeout=10)
					if resp.status_code in (200, 201):
						j = resp.json()
						# ensure owner/repo are present for refresh
						pr_entry = {
							"owner": j.get("owner"),
							"repo": j.get("repo"),
							"number": j.get("number"),
							"title": j.get("raw", {}).get("title") if j.get("raw") else payload["title"],
							"state": j.get("state"),
							"url": j.get("url"),
							"raw": j.get("raw", {})
						}
						add_pr_to_session(pr_entry)
						st.success("Pull request created and added to session table.")
						# navigate to repo PRs view
						st.session_state["current_repo"] = payload["repo"]
						st.session_state["view"] = "repo_prs"
						return
					else:
						# Better error display for GitHub validation errors (e.g., base branch invalid)
						try:
							err = resp.json()
							# If GitHub provides 'details' with validation info, show it clearly
							details = err.get("details") or err.get("message") or err
						except Exception:
							details = resp.text
						st.error(f"Failed to create PR ({resp.status_code}): {details}")
				except Exception as e:
					st.error(f"Failed to call backend: {e}")
			else:
				# Local simulation: don't call backend; just add simulated entry
				sim_entry = {
					"owner": payload["repo"].split("/",1)[0] if "/" in payload["repo"] else payload["repo"],
					"repo": payload["repo"].split("/",1)[1] if "/" in payload["repo"] else "",
					"number": -1,
					"title": payload["title"],
					"state": "simulated",
					"url": "",
					"raw": payload
				}
				add_pr_to_session(sim_entry)
				st.success("Simulated PR added to session table.")
			return  # let Streamlit re-run naturally after submit

# Main view — always show form (session state updates will refresh the page)
if st.session_state["view"] == "form":
	show_form()
elif st.session_state["view"] == "repo_prs":
	show_repo_prs()
else:
	st.session_state["view"] = "form"
	show_form()