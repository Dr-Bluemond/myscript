#!/usr/bin/env python3

import subprocess
import requests
import datetime
import re
import os

TOKEN = "hidden"
ZONE_ID = "hidden"

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
def get_existing_dns_records(zone_id):
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
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
    return None


# 更新DNS记录
def update_dns_record(zone_id, record_id, name, record_type, content):
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record_id}"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "content": content,
        "name": name,
        "proxied": False,
        "type": record_type,
        "ttl": 60
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
def create_dns_record(zone_id, name, record_type, content):
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "type": record_type,
        "name": name,
        "content": content,
        "ttl": 60,
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


# 记录DNS变化到日志文件
def log_dns_change(record_name, record_type, old_value, new_value):
    log_file = "/var/log/ddns.log"
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"{timestamp} - 域名: {record_name}, 类型: {record_type}, 原值: {old_value}, 新值: {new_value}\n"

    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
        print(f"已记录DNS变化到日志文件: {log_file}")
    except Exception as e:
        print(f"写入日志文件时出错: {e}")


# 封装检查和更新DNS记录的逻辑
def check_and_update_dns_record(zone_id, record_name, record_type, content, existing_records):
    # 使用 (record_name, record_type) 作为联合主键
    key = (record_name, record_type)
    if key in existing_records:
        record = existing_records[key]
        if record['content'] != content:  # 只在内容改变时更新
            old_value = record['content']
            print(f"{record_type}记录内容变化，旧值: {old_value}，新值: {content}")
            # 记录DNS变化到日志文件
            log_dns_change(record_name, record_type, old_value, content)
            update_dns_record(zone_id, record['id'], record_name, record_type, content)
            return True
        else:
            print(f"{record_type}记录内容未变化，无需更新")
            return False
    else:
        print(f"{record_type}记录 {record_name} 不存在，创建新记录")
        # 创建新记录时也记录到日志，原值为空
        log_dns_change(record_name, record_type, "无", content)
        create_dns_record(zone_id, record_name, record_type, content)
        return True


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
    existing_records = get_existing_dns_records(ZONE_ID)
    if existing_records is None:
        print("无法获取现有DNS记录，程序终止")
        return
    print_dns_records(existing_records)

    updated = False
    # 更新或创建IPv6记录
    if ipv6:
        updated |= check_and_update_dns_record(ZONE_ID, "hidden.com", "AAAA", ipv6, existing_records)
        check_and_update_dns_record(ZONE_ID, "hidden.com", "AAAA", ipv6, existing_records)

    # 更新或创建IPv4记录
    if ipv4:
        updated |= check_and_update_dns_record(ZONE_ID, "hidden.com", "A", ipv4, existing_records)
        check_and_update_dns_record(ZONE_ID, "hidden.com", "A", ipv4, existing_records)

    if updated:
        os.system("systemctl restart qbittorrent-nox@qbtuser.service")
        os.system("systemctl restart qbittorrent-nox@qptuser.service")

if __name__ == "__main__":
    main()