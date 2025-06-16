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
API_KEY = "16bf19d6c1a317ef101cb8691d5fcec5" # USER NEEDS TO PROVIDE THEIR OWN

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
        print("whoops")
        return None
    
def get_maven_metadata(group_id: str, artifact_id: str) -> Optional[ET.Element]:
    # Convert group_id to path format
    group_path = group_id.replace('.', '/')
    metadata_url = f"{MAVEN_CENTRAL}{group_path}/{artifact_id}/maven-metadata.xml"
    
    try:
        response = requests.get(metadata_url, timeout=10)
        
        if response.status_code == 200:
            return ET.fromstring(response.content)
        
    except (requests.RequestException, ET.ParseError) as e:
        return None
    
def get_all_versions(group_id: str, artifact_id: str) -> List[str]:
    metadata = get_maven_metadata(group_id, artifact_id)
    
    if metadata is None:
        return []
    
    versions = []
    
    # Extract version information from the metadata XML
    versioning = metadata.find("versioning")
    if versioning is not None:
        versions_element = versioning.find("versions")
        if versions_element is not None:
            for version_element in versions_element.findall("version"):
                if not '-' in version_element.text:
                    versions.append(version_element.text)
    return versions

    
def get_release_frequency(metadata):
    first_release = datetime.strptime(metadata["versions"][0]["published_at"].split('T')[0], r"%Y-%m-%d")
    amount_of_releases = len(metadata["versions"])
    latest_release = datetime.strptime(metadata["versions"][amount_of_releases - 1]["published_at"].split('T')[0], r"%Y-%m-%d")

    if amount_of_releases < 2:
        # Can't compute frequency
        return 0
    
    time_span = (latest_release - first_release).days

    frequency = time_span / (amount_of_releases - 1)
    return frequency
    
def get_properties(group_id: str, artifact_id: str):
    metadata = get_library_metadata(group_id, artifact_id)
    versions = get_all_versions(group_id, artifact_id)

    if metadata is None:
        print("[ERROR] Could not find artifact metadata on libraries.io.")
        return None, -1, versions
    else:
        metadata = json.loads(metadata)
        release_frequency = get_release_frequency(metadata)
        repository_url = metadata["repository_url"]

    
    if "github.com" in repository_url:
        return repository_url, release_frequency, versions
    return None, release_frequency, versions

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

    if not score is None: 
        print(f"Scorecard score: {score}")
    print("Compatibility scores:")
    print(f"\t{round(100 * compatibility["total_score"], 2)}% of all updates ({compatibility['total_amounts'] - 1}) are backward-compatible.")
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