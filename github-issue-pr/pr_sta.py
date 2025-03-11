import os
import requests
from datetime import datetime, timedelta, UTC

BASE_URL = "https://api.github.com"

def get_open_issues_count(owner, repo, token, until_time):
    """ 
    在某一个时间点(until_time)是open的issues数量
    要求当前时间点必须大于上述时间点
    以及在一个时间跨度内创建且在上述时间点是open的issues数量

    """
    # GitHub API 配置
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # 初始化计数器
    page = 1
    per_page = 100  # 每页最大数量

    open_issues_1 = []
    while True:
        # 构建请求参数
        params = {
            "state": "open",
            "per_page": per_page,
            "page": page
        }
        
        # 发送请求
        response = requests.get(
            f"{BASE_URL}/repos/{owner}/{repo}/issues",
            headers=headers,
            params=params
        )
        # 错误处理
        if response.status_code != 200:
            print(f"请求失败，状态码：{response.status_code}")
            print(f"错误信息：{response.json().get('message', '未知错误')}")
            return None
        
        # 解析数据
        issues = response.json()
        if not issues:
            break  # 无更多数据

        # 过滤掉 Pull Request（PR 会有 pull_request 字段）
        issues = [issue for issue in issues if "pull_request" in issue]
        open_issues_1 = [issue for issue in issues if issue['created_at'] < until_time]
        # 检查分页
        if "next" not in response.links:
            break
        page += 1

    open_issues_2 = []
    while True:
        # 构建请求参数
        params = {
            "state": "closed",
            "since": until_time,
            "per_page": per_page,
            "page": page
        }
        
        # 发送请求
        response = requests.get(
            f"{BASE_URL}/repos/{owner}/{repo}/issues",
            headers=headers,
            params=params
        )
        # 错误处理
        if response.status_code != 200:
            print(f"请求失败，状态码：{response.status_code}")
            print(f"错误信息：{response.json().get('message', '未知错误')}")
            return None
        
        # 解析数据
        issues = response.json()
        if not issues:
            break  # 无更多数据

        # 过滤掉 Pull Request（PR 会有 pull_request 字段）
        issues = [issue for issue in issues if "pull_request" in issue]
        open_issues_2 = [issue for issue in issues if issue['created_at'] < until_time and issue['closed_at']>= until_time]
        # 检查分页
        if "next" not in response.links:
            break
        page += 1

    open_issues = open_issues_1 + open_issues_2
    return len(open_issues)

# 获取 Issue 时间线事件
def get_timeline_events(owner, repo, token, issue_number):
    events = []
    page = 1
    per_page = 100  # 每页最多 100 条记录

    # GitHub API 配置
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    while True:
        # 添加分页参数
        params = {
            "page": page,
            "per_page": per_page
        }
        # 发送请求
        response = requests.get(
            f"{BASE_URL}/repos/{owner}/{repo}/issues/{issue_number}/timeline",
            #f"{BASE_URL}/repos/{owner}/{repo}/pulls/{issue_number}/timeline",
            headers=headers,
            params=params
        )

        if response.status_code == 200:
            data = response.json()
            if not data:
                break  # 如果没有数据，退出循环
            events.extend(data)
            ## 检查分页
            #if "next" not in response.links:
            #    break
            page += 1
        else:
            print(f"{BASE_URL}/repos/{owner}/{repo}/pulls/{issue_number}/timeline 请求失败，状态码: {response.status_code}")
            break
    return events

def find_key_endswith(keys, sss):
    for key in keys:
        if key.endswith(sss):
            return key
    return False


def get_last_update_event(owner, repo, token, issue_number, issue_created_time, since_time, until_time):
    last_update_event = None
    # 通过时间线获取events
    events = get_timeline_events(owner, repo, token, issue_number)
    # pr中的events的时间字段不标准，统一成标准的created_at时间a
    for i in range(len(events)):
        event = events[i]
        if 'created_at' not in event:
            if event['event'] == 'committed':
                events[i]['created_at'] = event['committer']['date']
            # 如果存在一个以 _at 结尾的字段
            else:
                key = find_key_endswith(event.keys(), '_at')  
                events[i]['created_at'] = event[key]
        #print(events[i]['event'])
        #print(events[i]['created_at'])
    # 去除掉第一个创建或者和创建相关的labeled event, 有些项目创建时必须指定label
    # 一般来说创建issue是不在timeline的
    #if issue_number == 806:
    #    for event in events:
    #        print(event['event'])
    #        print(event['created_at'])

    for i in range(len(events)):
        if events[i]['created_at'] != issue_created_time:
            break
    events = events[i:]

    # 时间线的元素个数有限制 时间从远及近 好像是30个
    # 逆序遍历
    events.reverse()
    for event in events:
        # 去除掉close event
        if event["event"] == "closed":
            continue
        else:
            if event['created_at'] >= until_time:
                continue
            elif event['created_at'] < since_time:
                print('last non-closed updated event of issue(number: %d) in timeline is : %s and its created time is %s' %(issue_number, event['event'], event['created_at']))
                break
            else:
                return event
    return last_update_event


def get_recent_issues_count(owner, repo, token, since_time, until_time):
    # GitHub API 配置
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    
    # 初始化计数器
    page = 1
    per_page = 100  # 每页最大数量

    created_issues = []
    closed_issues = []
    created_closed_issues = []
    updated_issues = []
    
    while True:
        # 构建请求参数
        params = {
            "state": "all",
            #最近一周有更新
            "since": since_time,
            "per_page": per_page,
            "page": page
        }
        
        # 发送请求
        response = requests.get(
            f"{BASE_URL}/repos/{owner}/{repo}/issues",
            headers=headers,
            params=params
        )
        # 错误处理
        if response.status_code != 200:
            print(f"请求失败，状态码：{response.status_code}")
            print(f"错误信息：{response.json().get('message', '未知错误')}")
            return None
        
        # 解析数据
        issues = response.json()
        if not issues:
            break  # 无更多数据

        # 过滤掉 Pull Request（PR 会有 pull_request 字段）
        issues = [issue for issue in issues if "pull_request" in issue]
        #total_issues += issues
        # 统计最近一周updated的issues数量 update不包含单纯的create event和close event
        for issue in issues:
            issue_number = issue['number']
            last_update_event = get_last_update_event(owner, repo, token, issue_number,\
                    issue['created_at'], since_time, until_time)
            if last_update_event:
                updated_issues.append(issue)
            else:
                continue
        issue_number = [issue['number'] for issue in issues]
        last_update_issue_number = [issue['number'] for issue in updated_issues]
        print('issue_number: %s'%str(issue_number))
        print('last_update_issue_number: %s'%str(last_update_issue_number))

        # 统计最近一周新建的issues
        created_issues += [issue for issue in issues if issue['created_at'] >= since_time and issue['created_at'] < until_time]
        # 统计最近一周closed的issues
        closed_issues += [issue for issue in issues if issue['state'] == 'closed' and issue['closed_at'] >= since_time and issue['closed_at'] < until_time]
        # 统计本周新建且本周closed的issues
        created_closed_issues += [issue for issue in issues \
                if issue['created_at'] >= since_time and issue['created_at'] < until_time \
                and issue['state'] == 'closed' \
                and issue['closed_at'] >= since_time and issue['closed_at'] < until_time]
        # 检查分页
        if "next" not in response.links:
            break
            
        page += 1
    
    return len(created_issues), len(closed_issues), len(created_issues)-len(created_closed_issues), len(updated_issues)


# 使用示例
if __name__ == "__main__":
    # 替换以下信息  必须的参数
    OWNER = "tronprotocol"         # 仓库所有者
    ACCESS_TOKEN = os.getenv("GITHUB_ACCESS_TOKEN")  # 从环境变量中获取 GitHub ACCESS Token
    REPOs = ["java-tron", "tips", "trident", "tron-docker", "wallet-cli", 'documentation-en', 'documentation-zh']            # 仓库名称
    #REPOs = ["java-tron"]            # 仓库名称
    #utc时间
    until_date = datetime.now().strftime('%Y-%m-%d')
    since_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    until_time = '%sT03:00:00Z'%until_date
    since_time = '%sT03:00:00Z'%since_date

    for REPO in REPOs:
        open_count = get_open_issues_count(OWNER, REPO, ACCESS_TOKEN, until_time)
        print(f"仓库 {OWNER}/{REPO} 当前open的Issue 数量：{open_count} 个")
        created_count, closed_count, created_open_count, updated_count = get_recent_issues_count(OWNER, REPO, ACCESS_TOKEN, since_time, until_time)
        print(f"仓库 {OWNER}/{REPO} 最近一周新建的Issue 数量：{created_count} 个")
        print(f"仓库 {OWNER}/{REPO} 最近一周关闭的Issue 数量：{closed_count} 个")
        print(f"仓库 {OWNER}/{REPO} 最近一周新建且open的Issue 数量：{created_open_count} 个")
        print(f"仓库 {OWNER}/{REPO} 最近一周更新的Issue 数量：{updated_count} 个")
        print('\n')
        print('************************************************')
