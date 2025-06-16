from typing import List
import subprocess
from urllib.request import urlretrieve
from pathlib import Path
import urllib.error
import tempfile

MAVEN_CENTRAL = "https://repo1.maven.org/maven2"
japicmp_path = "japicmp-0.23.1-jar-with-dependencies.jar"

def split_majors(versions):
    # Splits versions in smaller sets within the same major group
    split_versions = []
    majors_seen = set()
    for version in versions:
        major = version.split('.')[0]
        if major in majors_seen:
            continue
        majors_seen.add(major)
        split_versions.append([version for version in versions if version.startswith(major)])
    return split_versions

def maven_to_path(group_id, artifact_id, version):
    path = f"{group_id.replace('.', '/')}/{artifact_id}/{version}/{artifact_id}-{version}.jar"
    return f"{MAVEN_CENTRAL}/{path}"

def download_jar(group_id, artifact_id, version, dest_dir):
    if 'bom' in artifact_id or 'parent' in artifact_id:
        return None
    
    jar_url = maven_to_path(group_id, artifact_id, version)
    jar_path = Path(dest_dir) / f"{artifact_id}-{version}.jar"
    try:
        urlretrieve(jar_url, jar_path)
    except urllib.error.HTTPError as e:
        print(f'[ERROR] Could not retrieve jar for {group_id}:{artifact_id}.')
        return None
    return str(jar_path)

def execute_jcmp(old_jar, new_jar) -> bool:
    result = subprocess.run([
        "java", "-jar", japicmp_path,
        "--old", old_jar,
        "--new", new_jar,
        "--only-incompatible",
        "--ignore-missing-classes"
    ], 
    capture_output=True,
    text=True)\

    if "!" in result.stdout or result.returncode != 0:
        return 0
    return 1

def compare_versions(group_id, artifact_id, old_version, new_version):
    with tempfile.TemporaryDirectory() as temp_dir:
        old_jar = download_jar(group_id, artifact_id, old_version, temp_dir)
        new_jar = download_jar(group_id, artifact_id, new_version, temp_dir)

        if old_jar is None or new_jar is None:
            # Likely a module referring to its parent artifact, backward compatibility is assumed
            return 1

        is_compatible = execute_jcmp(old_jar, new_jar)
        return is_compatible
    
def check_update_type(old_version, new_version):
    old = old_version.split(".")
    new = new_version.split('.')

    if len(old) != len(new) or len(old) != 3 or len(new) != 3:
        return "weird"
    
    if old[1] != new[1]:
        return "minor"
    
    if old[2] != new[2]:
        return "patch"

def compare_all(group_id, artifact_id, versions):
    total_score = 0
    minor_amounts = 0
    minor_score = 0
    patch_amounts = 0
    patch_score = 0
    weird_update = 0
    weird_score = 0

    result = {}
    for i in range(len(versions) - 1):
        cmp = compare_versions(group_id, artifact_id, versions[i], versions[i+1])
        total_score += 1 if cmp == 1 else 0
        update_type = check_update_type(versions[i], versions[i+1])
        if update_type == "minor":
            minor_score += 1 if cmp == 1 else 0
            minor_amounts += 1
        elif update_type == "patch":
            patch_score += 1 if cmp == 1 else 0
            patch_amounts += 1
        else:
            weird_update += 1
            weird_score += 1 if cmp == 1 else 0

    result["total_score"] = total_score / len(versions)
    result["minor_score"] = minor_score
    result["minor_amounts"] = minor_amounts
    result["patch_score"] = patch_score
    result["patch_amounts"] = patch_amounts
    result["weird_score"] = weird_score
    result["weird_amounts"] = weird_update

    return result


def get_score(group_id: str, artifact_id: str, versions: List[str]) -> dict:
    # Strategy:
    # - Divide versions into major groups
    # - For each major group:
    #   - Compare each version with the consecutive version
    #   - Keep track of whether it was a minor or major upgrade
    #   - Return total score, minor score, and patch score for that group 
    # TODO: exclude pre-release versions (e.g. 0.1.2)

    # Download jcmp
    if not Path(japicmp_path).exists():
        urlretrieve("https://repo1.maven.org/maven2/com/github/siom79/japicmp/japicmp/0.23.1/japicmp-0.23.1-jar-with-dependencies.jar", japicmp_path)
    
    major_groups = split_majors(versions)

    group_results = []

    # Compare all groups
    for group in major_groups:
        group_results.append(compare_all(group_id, artifact_id, group))

    # Aggregate results
    result = {}
    result["group_id"] = group_id
    result["artifact_id"] = artifact_id
    result["total_amounts"] = len(versions)
    result["total_score"] = sum([group["total_score"] for group in group_results]) / len(group_results) if len(group_results) > 0 else 0
    result["minor_amounts"] = sum([group["minor_amounts"] for group in group_results])
    result["minor_score"] = sum([group["minor_score"] for group in group_results]) / result["minor_amounts"] if result["minor_amounts"] > 0 else 0
    result["patch_amounts"] = sum([group["patch_amounts"] for group in group_results])
    result["patch_score"] = sum([group["patch_score"] for group in group_results]) / result["patch_amounts"] if result["patch_amounts"] > 0 else 0
    result["weird_amounts"] = sum([group["weird_amounts"] for group in group_results])
    result["weird_score"] = sum([group["weird_score"] for group in group_results]) / result["weird_amounts"] if result["weird_amounts"] > 0 else 0
    

    print(f"[INFO] Successfully received compatibility scores.")
    return result