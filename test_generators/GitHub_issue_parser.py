import requests
import re
from logging import getLogger

logger = getLogger()

# ############################## CONFIG:
owner = 'NCATSTranslator'  # Replace with the repository owner's name or organization name
repo = 'Feedback'   # Replace with the repository name
TEST_ASSET_HEADERS = [
    'Relationship',
    'Settings',
    'InputName',
    'InputID',
    'OutputName',
    'OutputID',
    'Expected Result',
    'Author',
    'issue label'
]


# ############################## UTILS:

def parse_lines(text_lines, field_names):
    data_entry = {}
    for line in text_lines:
        line = line.strip()
        if not line:
            continue
        for field in field_names:
            if line.startswith(field):
                data_entry[field] = re.split(field+":", line, 1)[1].lstrip()
    return data_entry


def parse_asset(body_text):
    testing_framework = body_text.split("## Testing framework:", 1)
    if len(testing_framework) > 1:
        templated_text_lines = testing_framework[1].splitlines()
        asset_data = parse_lines(templated_text_lines, TEST_ASSET_HEADERS)
    else:
        asset_data = {}
    return asset_data


# SCRIPT: For the moment, does not take into account multiple templates in 1 issue,
# in case of multiplicity, the syntax needs to be worked out first
if __name__ == '__main__':
    url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    data = []
    response = requests.get(url)

    if response.status_code != 200:
        print(f"Failed to fetch data from GitHub API. Status code: {response.status_code}")
        print(response.text)
        templated_issues = []
    else:
        issue_list = response.json()
        issue = issue_list[0]
        templated_issues = []
        for issue in issue_list:
            body = issue['body']
            test_asset = parse_asset(body)
            if len(test_asset):
                # pk = parse_lines(body.splitlines(),['PK'])
                UI_url = parse_lines(body.splitlines(), ['URL'])
                if UI_url:
                    # Found the URL and parsed it
                    # ars_response = requests.get("http://ars.ci.transltr.io/ars/api/messages/" + pk['PK']).json()
                    # ars_response['fields']['data']['message']['query_graph']['nodes']['ids']
                    test_asset['InputID'] = UI_url['URL'].split(r"results?l=")[1].split("&")[1][2:]
                    test_asset['InputName'] = UI_url['URL'].split(r"results?l=")[1].split("&")[0].replace("%20", " ")
                else:
                    logger.warning(f"Warning: query URL not provided in issue #{str(issue['number'])}")
                test_asset['labels'] = [label['name'] for label in issue['labels']]
                # test_asset['Relationship'] need to use ars message for that, currently does not work
                # test_asset['Settings'] do we really need this?
                test_asset['GitHubIssue'] = issue['url']
                templated_issues.append(test_asset)
        
    print(templated_issues)




