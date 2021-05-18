import requests
from datetime import date
import argparse

# отключение warnings при игнорировании ssl сертификата
requests.packages.urllib3.disable_warnings()

# переменные принимаемые из коммандной строки
parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group()
group.add_argument("-n", "--new", action="store_true")
group.add_argument("-up", "--update", action="store_true")
parser.add_argument("-v", type=str, help="version")
parser.add_argument("-i", type=str, help="issues list")
parser.add_argument("-u", type=str, help="ci user")
parser.add_argument("-p", type=str, help="ci password")
args = parser.parse_args()

ci_user = args.u
ci_password = args.p

issues = args.i.split(",")

jira_api = 'https://task.corp.dev.vtb/rest/api/2'
api_version = jira_api + '/version'

with open('jira_spaces.config') as f:
    data = f.read()

spaces_list = [space.split("'")[1] for space in data.split(")")[0].split("(")[-1].split(",")]


def jira_version(version):
    return ('tbmb_' + version)


class Jira:
    def get(self):
        s = requests.Session()
        s.auth = (ci_user, ci_password)
        s.headers.update({'Content-Type': 'application/json'})
        r = s.get(self, verify=False)
        return r

    def post(self, data_json):
        s = requests.Session()
        s.auth = (ci_user, ci_password)
        s.headers = {'Content-Type': 'application/json'}
        r = s.post(self, json=data_json, verify=False)
        return r

    def put(self, data_json):
        s = requests.Session()
        s.auth = (ci_user, ci_password)
        s.headers = {'Content-Type': 'application/json'}
        r = s.put(self, json=data_json, verify=False)
        return r

    def delete(self):
        s = requests.Session()
        s.auth = (ci_user, ci_password)
        s.headers = {'Content-Type': 'application/json'}
        r = s.delete(self, verify=False)
        return r


class Find:
    # определение адреса API конкретной задачи
    #  вызо issue_api(issue)
    def issue_api(self):
        return jira_api + '/issue/' + self

    # определение адреса API пространства Jira
    # вызов Find.space(space)
    def space(self):
        project = jira_api + '/project'
        project_content = Jira.get(project).json()
        for i in project_content:
            if i.get('key') == self:
                return project + '/' + i.get('id') + '/versions'
            else:
                pass

    # определение адреса API версии, берёт за основу результат метода space
    # вызов Find.version(version, space)
    def version(self, space):
        version_name = jira_version(self)
        space_link = Find.space(space)
        space_content = Jira.get(space_link).json()
        for i in space_content:
            if i.get('name') == version_name:
                return api_version + '/' + i.get('id')
            else:
                pass

    # определение имени родительской задачи\стори
    def parent(self):
        issue_json = Jira.get(Find.issue_api(self)).json()
        for i in issue_json:
            if i == 'fields':
                for x in issue_json.get(i):
                    if x == 'parent':
                        a = issue_json.get(i).get(x)
                        # return a.get('self')
                        return a.get('key')
                    else:
                        pass

    # проверяет есть ли у задачи уже имеющиеся fixVersion, возвращает список имеющихся
    # вызов having_fv(issue)
    def having_fv(self):
        issue_json = Jira.get(Find.issue_api(self)).json()
        having = []
        for x in issue_json:
            if x == 'fields':
                for y in issue_json.get(x):
                    if y == 'fixVersions':
                        for z in issue_json.get(x).get(y):
                            having.append(z.get('name'))
        if not having:
            return None
        else:
            return having

    # находит в списке версию с минорным значением ниже, чем у новой версии и убирает из списка для
    # вызов lower(having_fv(issue), jira_version(version))
    def lower(self, new_version):
        for i in self:
            # имя проекта
            if i.split('_')[0] == new_version.split('_')[0]:
                # мажорные
                if i.split('_')[1] == new_version.split('_')[1]:
                    # минорные
                    if i.split('_')[2] == new_version.split('_')[2]:
                        # хотфикс
                        if i.split('_')[3] == new_version.split('_')[3]:
                            self.remove(i)
                        elif i.split('_')[3] < new_version.split('_')[3]:
                            print('Версия ' + i + ' меньше новой ' + new_version + ' заменяем.')
                            self.remove(i)
                        else:
                            print('такого быть не должно, ' + i + ' больше, чем ' + new_version)
                            pass
                    elif i.split('_')[2] < new_version.split('_')[2]:
                        print('Версия ' + i + ' меньше новой ' + new_version + ' заменяем.')
                        self.remove(i)
                    else:
                        print('такого быть не должно, ' + i + ' больше, чем ' + new_version)
                        pass
                else:
                    pass
            else:
                pass
        return self


# создание новой версии в спейсе
# вызов Create.version(version, space)
class Create:
    def version(self, space):
        payload = {
            "description": "Version created from CI automatically",
            "name": jira_version(self),
            "archived": False,
            "released": False,
            "project": space
        }
        version_link = Find.version(self, space)
        print('Проверяем, существует ли версия ' + jira_version(self) + ' в спейсе ' + space + ':')
        if version_link == None:
            print('Версия отсуствует, создаём.\nJson на загрузку:\n' + str(payload))
            Jira.post(api_version, payload)
            print('Версия ' + jira_version(self) + ' успешно создана в проекте ' + space + '.')
        else:
            print('Версия ' + jira_version(self) + ' уже существует в проекте ' + space + '.')

    # генерирует Json на прикрепление новой fixVersion к таске
    # вызов update_task_payload(issue, version)
    def update_task_payload(self, version):
        new_version = jira_version(version)
        result = Find.having_fv(self)
        if result is None:
            payload = {"update": {"fixVersions": [{"set": [{"name": new_version}]}]}}
            return payload
        else:
            payload_body = []
            without_lower = Find.lower(result, new_version)
            for i in range(len(without_lower)):
                payload_body.append({"name": without_lower[i] })
            payload_body.append({"name": new_version })
            payload = {"update": {"fixVersions": [{"set": payload_body}]}}
            return payload


class Update:
    # добавление версии к таске в Jira
    # вызов Update.task(version, issue)
    def task(self, version):
        payload = Create.update_task_payload(self, version)
        print('Добавляем fixVersion')
        if Jira.put(Find.issue_api(self), payload).status_code == 204:
            print('В поле fixVersion задачи ' + self + ' добавлено значение ' + jira_version(version))
        else:
            the_exception = "Field 'fixVersions' cannot be set. It is not on the appropriate screen, or unknown."
            if Jira.put(Find.issue_api(self), payload).json().get('errors').get('fixVersions') == the_exception:
                print('\033[91mЗадача скорее всего в статусе "закрыта"\033[0m')
            else:
                print('Ошибка:')
                print(Jira.put(Find.issue_api(self), payload).json().get('errors').get('fixVersions'))


    # обновление полей released и releaseDate в уже имеющейся в проекте версии
    # вызов Update.version(version, issue)
    def version(self, space):
        payload = {
            "description": "Version created from CI automatically",
            "name": jira_version(self),
            "archived": False,
            "released": True,
            "releaseDate": date.today().strftime("%Y-%m-%d"),
            "project": space
        }
        version_link = Find.version(self, space)
        print('Находим версию ' + jira_version(self) + ' в спейсе ' + space + ':')
        if version_link == None:
            print('Версия ' + jira_version(self) + 'отсуствует, нечего обновлять.')
        else:
            print('Версия найдена, обновляем.\nJson на загрузку:\n' + str(payload))
            Jira.put(version_link, payload)
            print('Статус версии ' + jira_version(self) + ' в проекте ' + space + ' успешно изменен на released.')


def new_fixVersion(version, issue):
    space = issue.split('-')[0]
    if Find.space(space) == None:
        print('спейс ' + space + ' не существует или принадлежит JiraIT.')
        pass
    else:
        Update.task(issue, version)
        print('Проверяем наличие родительской таски у ' + issue + ':')
        if Find.parent(issue) == None:
            print('Родительская таска отсутствует')
        else:
            print('Номер родительской заявки: ' + Find.parent(issue))
            Update.task(Find.parent(issue), version)


def update_Version(version, issue):
    space = issue.split('-')[0]
    if Find.version(version, space) == None:
        print('версия ' + jira_version(version) + ' ещё не создана или что-то пошло не так.')
        pass
    else:
        for i in spaces_list:
            Update.version(version, i)


if args.update:
    for i in issues:
        print('Цикл для задачи ' + i + ':')
        update_Version(args.v, i)
elif args.new:
    print("создаём версию " + args.v + " во всех спейсах:")
    for i in spaces_list:
        Create.version(args.v, i)
    print("проставляем версию в таски по списку из коммита:")
    for i in issues:
        print('Цикл для задачи ' + i + ':')
        new_fixVersion(args.v, i)
else:
    print("Параметры ввода -v Версия -i Задачи Jira -u Пользователь Jira -p Пароль пользователя\nПроверка: version: {}\nissues: {}\nuser: {}\n--n для создания новой версии и закрепления её за задачей Jira\n--up для обновления статуса имеющейся".format(args.v, args.i, args.u))