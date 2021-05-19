import requests
import re
from datetime import date
import argparse
from packaging.version import Version
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

parser = argparse.ArgumentParser(description="Create and Update FixVersions")
group = parser.add_mutually_exclusive_group()
group.add_argument("-c", "--create", action="store_true", help="create new fixVersion/s in Jira")
group.add_argument("-u", "--update", action="store_true", help="update fixVersion/s in Jira")
group.add_argument("-cs", "--create_space", action="store_true", help="create new space in file")
parser.add_argument("-us", type=str, help="login at ci_dos_xx")
parser.add_argument("-p", type=str, help="password at ci_dos_xx")
parser.add_argument("-sf", type=str, help="path to space file")
parser.add_argument("-b", type=str, help="bearer token")
parser.add_argument("-v", type=str, help="version")
parser.add_argument("-vp", type=str, help="version prefix")
parser.add_argument("-d", type=str, help="description")
parser.add_argument("-bid", type=str, help="build id")
parser.add_argument("-ju", type=str, help="Jira REST API URL")
parser.add_argument("-tu", type=str, help="TeamCity REST API URL")
parser.add_argument("-r", type=int, help="released version")
parser.add_argument("-m", type=int, help="move new version after previous")
args = parser.parse_args()


class TeamCityListSpaces:
    def __init__(self, bearer_token: str, rest_api_url: str, build_id: str) -> None:
        self.bearer_token = bearer_token
        self.rest_api_url = rest_api_url
        self.build_id = build_id

    def auth(self, url_path: str) -> str:
        head = {'Authorization': 'Bearer ' + self.bearer_token}
        with requests.Session() as session:
            response = session.get(url_path, headers=head, verify=False, timeout=600)
            response.encoding = 'utf-8'
            if response.status_code == 200:
                return response.text
            else:
                print(f"Some connection problems was occurred. Returned status code is: {response.status_code}")
                exit()

    def get_overview_id(self) -> list:
        url_path = f"{self.rest_api_url}?locator=build:(id:{self.build_id})"
        build_ids = self.auth(url_path)
        parse_input = re.findall(r'id="(\d+)"', build_ids)
        if parse_input:
            print(f"Id's found: {parse_input}")
            return parse_input
        else:
            print("No one id's found")
            return []

    def get_spaces_list(self) -> list:
        spaces_list = self.get_overview_id()
        spaces_list_len = len(spaces_list)
        parse_output = []
        if spaces_list_len > 0:
            for space in spaces_list:
                url_path = f"{self.rest_api_url}/id:{space}"
                get_spaces_list = self.auth(url_path)
                parse_input = re.findall(r'\[(\w+-\d+)]', get_spaces_list)
                if parse_input:
                    if len(parse_input) > 1:
                        for add in parse_input:
                            parse_output.append(add)
                    else:
                        list_to_str1 = ''.join(parse_input)
                        parse_output.append(list_to_str1)
            unique_list = list(dict.fromkeys(parse_output))
            unique_list.sort()
            print(f"Task/s found: {unique_list}")
            return unique_list


class ReadSpaceList:
    def __init__(self, file_path: str) -> None:
        self.path = file_path

    def get_list_spaces(self) -> list:
        with open(self.path, 'r') as spaces_file:
            data = spaces_file.read()
        spaces_list = [space for space in data.split(",")]
        return spaces_list

    def info(self):
        print(f"Spaces in file:\n{self.get_list_spaces()}")


class AddSpaceList(ReadSpaceList):
    def __init__(self, file_path, new_space: list) -> None:
        super().__init__(file_path)
        self.new_spaces = new_space
        self.spaces = self.get_list_spaces()
        self.space_new_list_d = []

    def add_space_into_file(self) -> None:
        if self.spaces[0] == '':
            space_new_list = []
        else:
            space_new_list = self.spaces
        if self.new_spaces:
            for new_space in self.new_spaces:
                parse_spaces = re.search(r'(\w+)', new_space)
                space_new_list.append(parse_spaces.group(0))
                self.space_new_list_d = list(dict.fromkeys(space_new_list))
                self.space_new_list_d.sort()
            convert_spaces = ','.join(self.space_new_list_d)

            with open(self.path, 'w') as space_file:
                space_file.write(convert_spaces)

            self.info()
        else:
            print("Nothing to add")

    def info(self) -> None:
        print(f"Trying add the new space\\s:\n{self.new_spaces}\nList of the spaces:\n{self.space_new_list_d} ")


class JiraAuth:
    def __init__(self, user: str, password: str) -> None:
        self.__user = user
        self.__password = password

    def auth(self) -> requests.sessions.Session:
        with requests.Session() as session:
            session.auth = (self.__user, self.__password)
            return session


class Jira(JiraAuth):
    def __init__(self, jira_url: str, *arguments, **kwargs) -> None:
        super().__init__(*arguments, **kwargs)
        self.jira_url = jira_url
        self.session = self.auth()

    def get(self, jira_url_prefix) -> requests.models.Response:
        full_url = self.jira_url + jira_url_prefix
        response = self.session.get(full_url, verify=False, timeout=600)
        return response

    def post(self, jira_url_prefix, json_data) -> requests.models.Response:
        full_url = self.jira_url + jira_url_prefix
        response = self.session.post(full_url, json=json_data, verify=False, timeout=600)
        return response

    def put(self, jira_url_prefix, json_data) -> requests.models.Response:
        full_url = self.jira_url + jira_url_prefix
        response = self.session.put(full_url, json=json_data, verify=False, timeout=600)
        return response


class Create:
    def __init__(self, project: str, description: str, released: bool, version: str,
                 version_prefix: str, jira: Jira, move: bool) -> None:
        self.project = project
        self.description = description
        self.release = released
        self.version = version
        self.version_prefix = version_prefix
        self.name = self.version_prefix + "_" + self.version
        self.jira = jira
        self.move = move

    def check_version(self) -> None:
        rest_api_prefix = f"/project/{self.project}/versions"
        jira_get = self.jira.get(rest_api_prefix)
        need_create = False
        id_previous_version = 0
        list_previous_version = self.version.split(".")
        list_current_version = int(list_previous_version[-1]) - 1
        list_previous_version[-1] = str(list_current_version)
        str_previous_version = '.'.join(list_previous_version)
        previous_version = self.version_prefix + "_" + str_previous_version
        if jira_get.status_code == 200:
            get_json = jira_get.json()
            get_json.reverse()
            for i in get_json:
                if previous_version in i['name']:
                    id_previous_version = i['id']
                if self.name in i['name']:
                    print(f"This version {self.name} exists in {self.project}")
                    need_create = False
                    break
                else:
                    need_create = True
            if need_create:
                new_ver_id = self.create_version()
                prev_ver_id = self.release_previous_task(id_previous_version)
                if self.move:
                    self.move_versions(new_ver_id, prev_ver_id, previous_version)
        else:
            print(f"Some problem occurred with space: {self.project}")

    def create_version(self) -> int:
        rest_api_prefix = f"/version"
        print(f"Creating version {self.name} in {self.project}")
        payload = {
            "description": self.description,
            "name": self.name,
            "archived": False,
            "released": self.release,
            "userStartDate": date.today().strftime("%Y-%m-%d"),
            "project": self.project
        }
        create = self.jira.post(rest_api_prefix, payload)

        if create.status_code == 201:
            new_version_id = create.json()['id']
            print(f"Version {self.name} with id {new_version_id} was created in {self.project}")
            return new_version_id
        else:
            print(f"Returned code is {create.status_code}")

    def release_previous_task(self, prev_ver_id) -> int:
        rest_api_prefix = f"/version/{prev_ver_id}"
        if prev_ver_id:
            payload = {
                "description": f"{self.description} Version released.",
                "released": True,
                "releaseDate": date.today().strftime("%Y-%m-%d")
            }
            update = self.jira.put(rest_api_prefix, payload)
            update_name = update.json()['name']
            if update.status_code == 200:
                print(f"Version {update_name} with id {prev_ver_id} was released in {self.project}")
                return prev_ver_id
            else:
                print(f"Returned code is {update.status_code}")

    def move_versions(self, new_ver, prev_ver, prev_ver_name) -> None:
        rest_api_prefix = f"/version/{new_ver}/move"
        if prev_ver:
            payload = {
                "after": f"{self.jira.jira_url}/version/{prev_ver}"
            }
            move = self.jira.post(rest_api_prefix, payload)
            if move.status_code == 200:
                print(f"Version {self.name} with id {new_ver}) moved after {prev_ver_name} with id: {prev_ver}")
            else:
                print(f"Returned code is {move.status_code}")


def parse_version(version: str, regexp: str) -> re.Match.group:
    parsed_version = re.search(regexp, version).group(0)
    return parsed_version


def checking_version(ins_ver: str, list_ver: str, all_ver: list, one_ver: str, ver: str) -> tuple:
    parse_insert_version = ins_ver
    parse_list_version = list_ver
    fv_list = all_ver
    list_version = one_ver
    version = ver
    change_fv = False
    if Version(parse_insert_version) > Version(parse_list_version):
        fv_list.pop(fv_list.index(list_version))
        change_fv = True
        print(f"| Version {list_version} changing to {version}")
    elif Version(parse_insert_version) < Version(parse_list_version):
        print(f"| Version {version} < {list_version} nothing to do")
        fv_list.pop(fv_list.index(version))
    elif Version(parse_insert_version) == Version(parse_list_version):
        change_fv = True
    else:
        print(f"| Some errors occurred for version setting")
    return change_fv, fv_list


class Issue:
    def __init__(self, issue_key: str, version_prefix: str, version: str, jira: Jira) -> None:
        self.issue_key = issue_key
        self.jira = jira
        self.version = version
        self.version_prefix = version_prefix
        self.name = self.version_prefix + "_" + self.version

    def get_issue(self) -> None:
        rest_api_prefix = f"/issue/{self.issue_key}"
        jira_get = self.jira.get(rest_api_prefix)
        fv_list = []
        if jira_get.status_code == 200:
            jira_get_json = jira_get.json()
            if 'fixVersions' in jira_get_json['fields']:
                jira_get_json_fv = jira_get_json['fields']['fixVersions']
                if jira_get_json_fv:
                    for fv in jira_get_json_fv:
                        fv_name = fv['name']
                        fv_list.append(fv_name)
                    print(f"| ------------------------------------------------------------\n"
                          f"| FixVersion/s {fv_list} found in task: {self.issue_key}")
            self.search_story(jira_get_json, fv_list)

    def search_story(self, jira_get_json, fv_list) -> None:
        jira_get_json_parent = ""
        if 'parent' in jira_get_json['fields']:
            jira_get_json_story = jira_get_json['fields']['parent']
            if jira_get_json_story:
                jira_get_json_parent = jira_get_json_story['key']
                print(f"| In task {self.issue_key} found parent story {jira_get_json_parent}")
        self.set_fix_version(jira_get_json_parent, fv_list)

    def set_fix_version(self, parent_task, fv_list) -> None:
        version = self.name
        issues = self.issue_key
        parent = parent_task
        issue_all = [issues]
        regexp = r'(?:\d{1,3}\.)*\d{1,3}'
        payload_body = []
        change_fv = False
        if parent:
            issue_all.append(parent)
        for issue in issue_all:
            print(f"| --- Checking fixVersion/s for {issue} ---")
            rest_api_prefix = f"/issue/{issue}"
            if fv_list:
                parse_insert_version = parse_version(version, regexp)
                split_insert_version = str(parse_insert_version).split('.')
                if version not in fv_list:
                    print(f"| Add {version} into {fv_list}")
                    fv_list.append(version)
                    for list_version in fv_list:
                        version_prefix = re.search(r'(\w+.*)_', list_version).group(1)
                        if self.version_prefix == version_prefix:
                            parse_list_version = parse_version(list_version, regexp)
                            split_list_version = str(parse_list_version).split('.')
                            if len(split_insert_version) == 2:
                                if split_insert_version[0] == split_list_version[0]:
                                    change_fv, fv_list = checking_version(parse_insert_version, parse_list_version,
                                                                          fv_list, list_version, version)
                            elif len(split_insert_version) == 3:
                                if split_insert_version[0] == split_list_version[0] \
                                        and split_insert_version[1] == split_list_version[1]:
                                    change_fv, fv_list = checking_version(parse_insert_version, parse_list_version,
                                                                          fv_list, list_version, version)
                else:
                    print(f"| fixVersion {version} exists in {fv_list}")
                if change_fv:
                    unique_list = list(dict.fromkeys(fv_list))
                    for i in unique_list:
                        payload_body.append({"name": i})
                    payload = {
                        "update": {
                            "fixVersions": [{"set": payload_body}]}
                    }
                    fv_put = self.jira.put(rest_api_prefix, payload)
                    if fv_put.status_code == 204:
                        print(f"| fixVersion/s {version} added successfully in task {fv_list}")
            else:
                print(f"| No fixVersion/s in task {issue}\nTrying to add fixVersion/s {version}")
                payload = {
                    "update": {
                        "fixVersions": [{"set": [{"name": version}]}]}
                }
                fv_put = self.jira.put(rest_api_prefix, payload)
                if fv_put.status_code == 204:
                    print(f"| fixVersion/s {version} added successfully in task {issue}")


def main():
    # -------------- Переменные полученные из аргументов -------------- #
    path = args.sf
    jira_url = args.ju
    jira_user = args.us
    jira_pass = args.p
    rest_api_url = args.tu
    bearer_token = args.b
    build_id = args.bid
    version_prefix = args.vp
    version = args.v
    description = args.d
    if args.r == 1:
        released = True
    elif args.r == 0:
        released = False
    if args.m == 1:
        move = True
    elif args.m == 0:
        move = False


    # -------------- Авторизация в Jira и методы get, post, put -------------- #
    jira = Jira(jira_url, jira_user, jira_pass)

    # -------------- Получеие списка задач и пространств из TeamCity -------------- #
    team = TeamCityListSpaces(bearer_token, rest_api_url, build_id)

    # -------------- Аргумент для пространств -------------- #
    if args.create_space:
        # -------------- Получить список задач из TeamCity и добавить пространства в файл  -------------- #
        add_new_space = AddSpaceList(path, team.get_spaces_list())
        add_new_space.add_space_into_file()

    # -------------- Проверка на существование и создание новой версии -------------- #
    if args.create:
        # -------------- Получить список пространств из файла -------------- #
        spaces = ReadSpaceList(path)
        projects = spaces.get_list_spaces()
        spaces.info()
        for project in projects:
            # -------------- Создание ФиксВерсий для каждого пространства полученного из файла -------------- #
            create = Create(project, description, released, version, version_prefix, jira, move)
            create.check_version()

    # -------------- Проставление ФиксВерсий в тасках Jira -------------- #
    if args.update:
        # -------------- Получить список тасок и установить ФиксВерсии -------------- #
        get_issues = team.get_spaces_list()
        if get_issues:
            for issue in get_issues:
                get_fix_version = Issue(issue, version_prefix, version, jira)
                get_fix_version.get_issue()


if __name__ == '__main__':
    main()
