import sys
import json
import argparse
import requests
from datetime import datetime
import scorecard
import compatibility as cmp
import xml.etree.ElementTree as ET
from typing import Optional, List
from concurrent.futures import ThreadPoolExecutor

MAVEN_CENTRAL = "https://repo1.maven.org/maven2/"
LIBRARIES_URL = "https://libraries.io/api/Maven/"
API_KEY = "YOUR_API_KEY" # USER NEEDS TO PROVIDE THEIR OWN

# Control flow:
# 1 - Check input (groupID:artifactID)
# 2 - Check if dependency can be found on GitHub
#   - If so, download Scorecard tool
#   - If not, display warning message but continue
# 3 - Download latest version of japicmp
# 4 - Query all versions of dependency
# 5 - Determine release frequency
#   - Releases may be dated oddly
# 6 - Determine compatibility score by comparing all versions
# 7 - Determine scorecard score
# 8 - Combine results into new score(card)

# Modules:
# 1. japicmp module
# 2. Scorecard module
# 4. Main module

def get_library_metadata(group_id: str, artifact_id: str):
    metadata_url = f"{LIBRARIES_URL}{group_id}:{artifact_id}"
    
    try:
        response = requests.get(metadata_url, timeout=10, params={
            "api_key": API_KEY
        })
        
        if response.status_code == 200:
            return response.content
        
        if response.status_code == 404:
            # Project not found on libraries.io
            return None
        
    except (requests.RequestException, ET.ParseError) as e:
        print(f"An error occured when fetching libaries.io metadata: {e}")
        return None

def get_versions_and_freq(group_id, artifact_id):
    url = f"https://search.maven.org/solrsearch/select?q=g:%22{group_id}%22+AND+a:%22{artifact_id}%22&core=gav&rows=200&wt=json"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"[ERROR] Artifact not found.")
        sys.exit(1)
        
    data = response.json()
    versions = [
        {
            "version": doc["v"],
            "date": datetime.fromtimestamp(doc["timestamp"] / 1000)
        }
        for doc in data["response"]["docs"]
    ]
    versions.sort(key=lambda x: x['date'])
    frequencies = [
        (versions[i]['date'] - versions[i-1]['date']).days
        for i in range(1, len(versions))
    ]
    freq = sum(frequencies) / len(frequencies) if len(frequencies) > 0 else 0
    versions = [v['version'] for v in versions]

    return versions, freq
    
def get_properties(group_id: str, artifact_id: str):
    metadata = get_library_metadata(group_id, artifact_id)
    versions, freq = get_versions_and_freq(group_id, artifact_id)

    if metadata is None:
        print("[ERROR] Could not find artifact metadata on libraries.io.")
        return None, freq, versions
    else:
        metadata = json.loads(metadata)
        repository_url = metadata["repository_url"]

    if "github.com" in repository_url:
        return repository_url, freq, versions
    return None, freq, versions

def main():
    parser = create_parser()
    args = parser.parse_args()

    group_id = args.groupId
    artifact_id = args.artifactId
    
    # Query libraries.io and maven repository for GitHub link, frequency and versions
    repo_url, frequency, versions = get_properties(group_id, artifact_id)

    # Get scorecard and compatibility scores
    with ThreadPoolExecutor(max_workers=2) as executor:
        print("[INFO] Getting scorecard and compatibility scores...")
        futures = [
            executor.submit(scorecard.get_score, repo_url, args.full_scorecard),
            executor.submit(cmp.get_score, group_id, artifact_id, versions)
        ]

        results = [future.result() for future in futures]

    score, compatibility = results

    w1 = 0.35
    w2 = 0.2
    w3_1 = 0.25
    w3_2 = 0.20
    f = (1 - w1)

    if not args.full_scorecard and score is not None:
        total_score = w1 * score/10 + w2 * (1 - (frequency / 365)) + w3_1 * compatibility['patch_score'] + w3_2 * compatibility['minor_score']
    else:
        total_score = w2/f * (1 - (frequency / 365)) + w3_1/f * compatibility['patch_score'] + w3_2/f * compatibility['minor_score']

    print(f"Total combined score: {round(10 * total_score, 2)}\n")

    if not score is None: 
        print(f"Scorecard score: {score}")
    print("Compatibility scores:")
    print(f"\t{round(100 * compatibility["total_score"], 2)}% of all updates ({compatibility['total_amounts']}) are backward-compatible.")
    print(f"\t{round(100 * compatibility["minor_score"], 2)}% of minor updates ({compatibility['minor_amounts']}) are backward-compatible.")
    print(f"\t{round(100 *compatibility["patch_score"], 2)}% of patch updates ({compatibility["patch_amounts"]}) are backward-compatible.")
    print(f"\t{round(100 *compatibility["weird_score"], 2)}% of non-semver updates ({compatibility["weird_amounts"]}) are backward-compatible.")
    print(f"A new version is released every {round(frequency)} days on average.")

def create_parser():
    parser = argparse.ArgumentParser(description="Calculate trust score for a Maven dependency.")
    parser.add_argument("-g", "--groupId", required=True, help="Group ID of the Maven artifact")
    parser.add_argument("-a", "--artifactId", required=True, help="Artifact ID of the Maven artifact")
    parser.add_argument("--full_scorecard", action="store_true", help="Get full scorecard output.")
    # TODO: Add argument for getting full scorecard output  
    return parser

if __name__ == "__main__":
    main()