## About
TeSTer is a conceptual command-line input tool used for analysing a dependency's security hygiene, release frequency, and semantic compatibility. TeSTer generates a Trust Score for a Maven dependency, aiding developers in the decision-making process when including a dependency into their project.

## Requirements
To use TeSTer, Docker must be installed and running, and Go must be installed locally.
In `scorecard.py`, replace the GITHUB_AUTH_TOKEN with your personal access token, that at least has the 'repo' permisssions.

## Usage
To use TeSTer, clone the repository and open a command prompt in the same location. Then, analyse a dependency with the following command:

``` python trustscore.py -a <artifact ID> -g <group ID> (--full_scorecard) ```
The full_scorecard flag can be used to display the full scorecard report instead of the aggregate score.
