#!/usr/bin/env python3

import subprocess
import requests
import datetime
import sys
import re

ZONE_ID = "<hidden>"
TOKEN = "<hidden>"

# 获取IPv6地址
def get_ipv6():
    try:
        result = subprocess.run(['/usr/sbin/ifconfig', 'eth0'], stdout=subprocess.PIPE, text=True)
        lines = result.stdout.splitlines()
        for line in lines:
            if 'inet6' in line and 'fe80' not in line:
                ipv6 = line.split()[1]
                print(f"成功获取IPv6地址: {ipv6}")
                return ipv6
    except Exception as e:
        print(f"获取IPv6地址时出错: {e}")
        return None
    return None


# 获取IPv4地址
def get_ipv4():
    try:
        response = requests.get("http://myip.ipip.net")
        if response.status_code == 200:
            # 使用正则表达式提取IPv4地址
            match = re.search(r"当前 IP：(\d+\.\d+\.\d+\.\d+)", response.text)
            if match:
                ipv4 = match.group(1)
                print(f"成功获取IPv4地址: {ipv4}")
                return ipv4
            else:
                print("未找到IPv4地址")
        else:
            print(f"请求失败，状态码: {response.status_code}")
    except Exception as e:
        print(f"请求出错: {e}")
    return None

# 查询现有的DNS记录并返回记录字典
def get_existing_dns_records():
    url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records"
    headers = {
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json"
            }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            records = response.json().get('result', [])
            # 使用 (name, type) 作为联合主键
            record_map = {(record['name'], record['type']): record for record in records}
            print("成功获取现有DNS记录")
            return record_map
        else:
            print(f"无法获取DNS记录列表，状态码: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"获取DNS记录时出错: {e}")
    return {}


# 更新DNS记录
def update_dns_record(record_id, name, record_type, content):
    url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records/{record_id}"
    headers = {
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json"
            }
    data = {
            "content": content,
            "name": name,
            "proxied": False,
            "type": record_type,
            "ttl": 1
            }

    try:
        response = requests.put(url, json=data, headers=headers)
        if response.status_code == 200:
            print(f"{record_type} 记录 {name} 更新成功")
        else:
            print(f"更新失败: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"请求出错: {e}")

# 创建新的DNS记录
def create_dns_record(name, record_type, content):
    url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records"
    headers = {
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json"
            }
    data = {
            "type": record_type,
            "name": name,
            "content": content,
            "ttl": 1,
            "proxied": False
            }

    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            print(f"成功创建新的 {record_type} 记录: {name}")
        else:
            print(f"创建DNS记录失败，状态码: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"创建DNS记录时出错: {e}")


# 封装检查和更新DNS记录的逻辑
def check_and_update_dns_record(record_name, record_type, content, existing_records):
    # 使用 (record_name, record_type) 作为联合主键
    key = (record_name, record_type)
    if key in existing_records:
        record = existing_records[key]
        if record['content'] != content:  # 只在内容改变时更新
            print(f"{record_type}记录内容变化，旧值: {record['content']}，新值: {content}")
            update_dns_record(record['id'], record_name, record_type, content)
        else:
            print(f"{record_type}记录内容未变化，无需更新")
    else:
        print(f"{record_type}记录 {record_name} 不存在，创建新记录")
        create_dns_record(record_name, record_type, content)


# 将DNS记录漂亮打印
def print_dns_records(record_map):
    print(f"{'名称':<30} {'类型':<10} {'内容':<40}")
    print("-" * 80)
    for (name, record_type), record in record_map.items():
        print(f"{name:<30} {record_type:<10} {record['content']:<40}")


def main():
    import datetime; print(datetime.datetime.now())
    ipv6 = get_ipv6()
    ipv4 = get_ipv4()

    # 查询现有DNS记录
    existing_records = get_existing_dns_records()

    print_dns_records(existing_records)

    # 更新或创建IPv6记录
    if ipv6:
        check_and_update_dns_record("<hidden>", "AAAA", ipv6, existing_records)

    # 更新或创建IPv4记录
    if ipv4:
        check_and_update_dns_record("<hidden>", "A", ipv4, existing_records)

if __name__ == "__main__":
    main()
