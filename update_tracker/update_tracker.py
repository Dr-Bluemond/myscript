import socket
import time
import qbittorrentapi

import aiohttp
import requests
from urllib.parse import urlparse
import asyncio
import random
import struct

proxy_url = "http://127.0.0.1:7890"
# trackers_url = "https://raw.githubusercontent.com/ngosang/trackerslist/master/trackers_best.txt"
trackers_url = "https://github.com/ngosang/trackerslist/raw/refs/heads/master/trackers_all.txt"
qbit_host = 'http://192.168.1.100:8080'
timeout = 3

# List of tracker URLs
def get_trackers_list():
    # GitHub上trackers列表的raw链接

    # 设置代理
    proxies = {
        "http": proxy_url,
        "https": proxy_url
    }

    try:
        # 发起GET请求获取trackers列表
        response = requests.get(trackers_url, proxies=proxies, timeout=10)
        response.raise_for_status()  # 检查请求是否成功

        # 分割获取的文本并返回tracker列表
        trackers = response.text.splitlines()
        return [tracker for tracker in trackers if tracker]  # 去除空行
    except requests.exceptions.RequestException as e:
        print(f"Error fetching trackers: {e}")
        return []


class MyProtocol(asyncio.DatagramProtocol):
    def __init__(self):
        super().__init__()
        self.datagram_future = asyncio.Future()

    def datagram_received(self, data, addr):
        self.datagram_future.set_result(data)

    def error_received(self, exc):
        self.datagram_future.set_exception(exc)


async def test_udp_tracker(hostname, port):
    try:
        # Resolve the hostname to an IP address
        host = socket.gethostbyname(hostname)
    except socket.gaierror:
        print(f"Unable to resolve hostname: {hostname}")
        return False
    # UDP Tracker protocol connection request
    transaction_id = random.randint(0, 0xFFFFFFFF)
    connection_id = 0x41727101980  # default connection id for UDP trackers
    packet = struct.pack(">QLL", connection_id, 0, transaction_id)  # format the connection request

    # Create a UDP transport
    loop = asyncio.get_event_loop()
    try:
        # Create a Datagram Protocol for UDP
        transport, protocol = await loop.create_datagram_endpoint(
            MyProtocol, local_addr=('0.0.0.0', 0)
        )

        # Send the packet
        transport.sendto(packet, (host, port))
        start_time = time.time()
    except Exception as e:
        print(f"{host}:{port} send failed: {e}")
        return False
    # Receive the response
    try:
        response = await asyncio.wait_for(protocol.datagram_future, timeout=timeout)
        if len(response) >= 16:
            action, res_transaction_id = struct.unpack(">LL", response[:8])
            if action == 0 and res_transaction_id == transaction_id:
                total_time = (time.time() - start_time) * 1000
                print(f"udp://{hostname}:{port} responded in {total_time} ms")
                return total_time
    except asyncio.TimeoutError:
        print(f"udp://{hostname}:{port} timed out in {timeout}s!")
        return False
    except Exception as e:
        print(f"udp://{hostname}:{port} receive failed!")
        return False

    return False

# Usage example
# asyncio.run(test_udp_tracker('tracker.example.com', 1234))

async def test_http_tracker(url):
    try:
        async with aiohttp.ClientSession() as session:
            start_time = time.time()
            async with session.get(url, timeout=timeout) as response:
                total_time = (time.time() - start_time) * 1000
                if response.status == 200:
                    print(f"{url} responded in {total_time} ms")
                    return total_time
                return False
    except TimeoutError:
        print(f"{url} timed out in {timeout}s!")
    except Exception as e:
        print(f"{url} failed: {repr(e)}")
        return False


async def check_tracker(tracker):
    parsed_url = urlparse(tracker)
    if parsed_url.scheme == 'udp':
        host = parsed_url.hostname
        port = parsed_url.port or 80
        t = await test_udp_tracker(host, port)
        return (tracker, t) if t else None
    elif parsed_url.scheme in ['http', 'https']:
        t = await test_http_tracker(tracker)
        return (tracker, t) if t else None
    else:
        print(f"Unsupported tracker type: {tracker}")
        return None


def check_trackers(trackers):
    # Create an event loop and run the check_tracker tasks
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    tasks = [check_tracker(tracker) for tracker in trackers]
    results = loop.run_until_complete(asyncio.gather(*tasks))

    # Filter out None values (trackers that failed)
    ok = [result for result in results if result is not None]
    print(f"Amount of ok trackers: {len(ok)}")

    best = sorted(ok, key=lambda x: x[1])[:20]
    print("Fastest trackers:")
    for tracker, t in best:
        print(f"{tracker}: {t}ms")
    best = [x[0] for x in best]
    return best


# 判断一个 tracker 是否可能是私有 tracker
def is_private_tracker(tracker_url):
    # 可以根据具体情况调整私有 tracker 的特征，比如域名或者协议
    private_keywords = ['passkey', 'auth', 'private', 'secure']
    return any(keyword in tracker_url for keyword in private_keywords)


def update_tracker(trackers):
    # 连接本地运行的 qbittorrent-nox
    client = qbittorrentapi.Client(host=qbit_host)

    # 检查是否连接成功
    try:
        client.auth_log_in()
        print("Connected to qBittorrent!")
    except qbittorrentapi.LoginFailed as e:
        print(f"Failed to connect: {e}")
        exit(1)

    # 获取所有种子信息
    torrents = client.torrents_info()

    # 打印每个种子的 tracker 信息并推断是否为私有种子
    for torrent in torrents:

        # 获取种子的 tracker 信息
        current_trackers = client.torrents_trackers(torrent.hash)

        private_flag = False
        if current_trackers:
            for tracker in current_trackers:
                tracker_url = tracker['url']
                # 如果发现任何私有 tracker，认为这个种子可能是私有的
                if is_private_tracker(tracker_url):
                    private_flag = True

        # 根据 tracker 信息推断是否为私有种子

        # 如果不是私有种子，执行 trackers 更新
        if not private_flag:
            print(f"Torrent Name: {torrent.name}")
            # 删除不在 ok_trackers 列表中的旧 trackers
            for tracker in current_trackers:
                tracker_url = tracker['url']
                if tracker_url not in trackers:
                    try:
                        client.torrents_remove_trackers(torrent_hash=torrent.hash, urls=tracker_url)
                        print(f"Removed old tracker: {tracker_url} from torrent: {torrent.name}")
                    except Exception as e:
                        print(f"Failed to remove tracker {tracker_url} from {torrent.name}: {e}")

            # 添加 ok_trackers 中不存在的 trackers
            for tracker in trackers:
                if tracker not in [t['url'] for t in current_trackers]:
                    try:
                        client.torrents_add_trackers(torrent_hash=torrent.hash, urls=tracker)
                        print(f"Added tracker: {tracker} to torrent: {torrent.name}")
                    except Exception as e:
                        print(f"Failed to add tracker {tracker} to {torrent.name}: {e}")

    # 创建一个包含 trackers 的字符串，以逗号分隔
    trackers_str = ',\n'.join(trackers)

    # 设置 preferences
    try:
        client.app_set_preferences(prefs={"add_trackers": trackers_str})
        print(f"Set 'add_trackers' preference to: {trackers_str}")
    except Exception as e:
        print(f"Failed to set 'add_trackers' preference: {e}")


if __name__ == '__main__':
    trackers = get_trackers_list()
    ok_trackers = check_trackers(trackers)
    update_tracker(ok_trackers)
