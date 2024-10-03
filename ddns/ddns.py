#!/usr/bin/env python3

import datetime
import re
import subprocess

import requests


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


def main():
    ipv6 = get_ipv6()
    ipv4 = get_ipv4()

    proxies = {
        "http": "http://127.0.0.1:1080",
        "https": "http://127.0.0.1:1080"
    }
    current_time = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
    # 检查IPv6地址是否为空
    if ipv6:
        url = "https://api.cloudflare.com/client/v4/zones/ba_____________________b2/dns_records/f5_____________________e"
        headers = {
            "Authorization": "Bearer pt__________________________wB-2PI",
            "Content-Type": "application/json"
        }
        data = {
            "content": ipv6,
            "name": "________________.com",
            "proxied": False,
            "type": "AAAA",
            "comment": f"自动更新于: {current_time}",
            "id": "f55_____________________4fe",
            "ttl": 1
        }
        try:
            # 发送PATCH请求更新DNS记录
            response = requests.patch(url, json=data, headers=headers, proxies=proxies)
            if response.status_code == 200:
                print("IPv6地址上传成功")
            else:
                print(f"上传失败: {response.status_code}, {response.text}")
        except Exception as e:
            print(f"请求出错: {e}")

    if ipv4:
        url = "https://api.cloudflare.com/client/v4/zones/bac_____________________deb2/dns_records/2c_____________________88"
        headers = {
            "Authorization": "Bearer pt_____________________-2PI",
            "Content-Type": "application/json"
        }
        data = {
            "content": ipv4,
            "name": "_____________________.com",
            "proxied": False,
            "type": "A",
            "comment": f"自动更新于: {current_time}",
            "id": "2c_____________________88",
            "ttl": 1
        }
        try:
            # 发送PATCH请求更新DNS记录
            response = requests.patch(url, json=data, headers=headers, proxies=proxies)
            if response.status_code == 200:
                print("IPv4地址上传成功")
            else:
                print(f"上传失败: {response.status_code}, {response.text}")
        except Exception as e:
            print(f"请求出错: {e}")


if __name__ == "__main__":
    main()
