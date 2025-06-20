import subprocess
import json
import sys

GITHUB_AUTH_TOKEN = "YOUR_TOKEN_HERE"

def get_score(repo_url: str, full_score: bool) -> str:
    if repo_url is None:
        print("[WARNING] No GitHub repository found for this artifact. Skipping scorecard score.")
        return None
    scorecard_output = run_scorecard(repo_url, full_score)

    # TODO: analyse results

    if full_score:
        return scorecard_output.decode("utf-8")
    scorecard_json = json.loads(scorecard_output)
    return scorecard_json["score"]

def run_scorecard(repo_url, full_score):
    # Requirements: go installed and docker running
    # TODO: Implement checks for go and docker

    # Check if scorecard is already pulled
    result = subprocess.run(["docker", "images"], capture_output=True).stdout
    if 'scorecard' in result.decode("utf-8"):
        print("[INFO] Scorecard image is already pulled. Running...")
    else:
        # Pull scorecard
        print("[INFO] Pulling scorecard image...")
        result = subprocess.run(["docker", "pull", "gcr.io/openssf/scorecard:stable"], capture_output=True)
        if result.stderr != b"":
            print("[ERROR] Could not pull scorecard image. Make sure docker is installed and running.")
            print(result.stderr)
            return None

        print("[INFO] Scorecard image pulled. Running scorecard...")

    # Run scorecard
    args = ["docker", "run",
                    "-e", f"GITHUB_AUTH_TOKEN={GITHUB_AUTH_TOKEN}",
                    "gcr.io/openssf/scorecard:stable",
                    f"--repo={repo_url}"]
    if not full_score:
        args.append("--format=json")
    result = subprocess.run(args, capture_output=True)
    
    if result.stdout == b"":
        print("[ERROR] An error occured while trying to run scorecard. Make sure go is installed and docker is running.")
        print(result.stderr)
        return None
    print("[INFO] Successfully ran scorecard.")

    return result.stdout