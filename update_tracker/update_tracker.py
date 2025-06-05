import socket
import time
import qbittorrentapi
import aiohttp
import requests
from urllib.parse import urlparse
import asyncio
import random
import struct

TRACKERSLIST_BEST = "https://raw.githubusercontent.com/ngosang/trackerslist/master/trackers_best.txt"
TRACKERSLIST_ALL = "https://raw.githubusercontent.com/ngosang/trackerslist/master/trackers_all.txt"

class TrackerChecker:
    def __init__(self,
                 proxy_url="http://127.0.0.1:8000",
                 trackers_url=TRACKERSLIST_ALL,
                 timeout=2,
                 best_tracker_count=30):
        self.proxy_url = proxy_url
        self.trackers_url = trackers_url
        self.timeout = timeout
        self.best_tracker_count = best_tracker_count
        self.trackers = []

    class MyProtocol(asyncio.DatagramProtocol):
        def __init__(self):
            super().__init__()
            self.datagram_future = asyncio.Future()
            self._transport = None  # 添加传输对象引用

        def connection_made(self, transport):
            self._transport = transport

        def datagram_received(self, data, addr):
            # 仅当Future未完成时设置结果
            if not self.datagram_future.done():
                self.datagram_future.set_result(data)
                # 收到响应后立即关闭传输
                self._transport.close()

        def error_received(self, exc):
            if not self.datagram_future.done():
                self.datagram_future.set_exception(exc)

        def connection_lost(self, exc):
            # 连接关闭时处理未完成的Future
            if not self.datagram_future.done():
                self.datagram_future.set_exception(
                    ConnectionError("Connection lost")
                )

    def fetch_trackers(self):
        proxies = {
            "http": self.proxy_url,
            "https": self.proxy_url
        } if self.proxy_url else None

        try:
            response = requests.get(self.trackers_url, proxies=proxies, timeout=10)
            response.raise_for_status()
            self.trackers = [t.strip() for t in response.text.splitlines() if t.strip()]
            print(f"Fetched {len(self.trackers)} trackers from {self.trackers_url}")
        except Exception as e:
            print(f"Error fetching trackers: {e}")
            self.trackers = []

    async def _test_udp_tracker(self, hostname, port):
        try:
            host = socket.gethostbyname(hostname)
        except socket.gaierror:
            return False

        transaction_id = random.randint(0, 0xFFFFFFFF)
        connection_id = 0x41727101980
        packet = struct.pack(">QLL", connection_id, 0, transaction_id)

        loop = asyncio.get_event_loop()
        try:
            transport, protocol = await loop.create_datagram_endpoint(
                self.MyProtocol, local_addr=('0.0.0.0', 0)
            )
            transport.sendto(packet, (host, port))
            start_time = time.time()
        except Exception as e:
            return False

        try:
            response = await asyncio.wait_for(protocol.datagram_future, timeout=self.timeout)
            if len(response) >= 16:
                action, res_transaction_id = struct.unpack(">LL", response[:8])
                if action == 0 and res_transaction_id == transaction_id:
                    return (time.time() - start_time) * 1000
        except (asyncio.TimeoutError, Exception):
            return False
        finally:
            transport.close()

        return False

    async def _test_http_tracker(self, url):
        try:
            async with aiohttp.ClientSession() as session:
                start_time = time.time()
                async with session.get(url, timeout=self.timeout) as response:
                    if response.status == 200:
                        return (time.time() - start_time) * 1000
        except Exception:
            return False

    async def _check_tracker(self, tracker):
        parsed = urlparse(tracker)
        if parsed.scheme not in ("udp", "http", "https"):
            return None

        success_count = 0
        total_latency = 0.0

        for _ in range(10):
            latency = None
            try:
                if parsed.scheme == "udp":
                    host = parsed.hostname
                    port = parsed.port or 80
                    latency = await self._test_udp_tracker(host, port)
                else:
                    latency = await self._test_http_tracker(tracker)

                if latency is not False and latency is not None:
                    success_count += 1
                    total_latency += latency
            except Exception as e:
                pass

            await asyncio.sleep(1)

        if success_count == 0:
            print(f"{tracker} failed all 10 attempts")
            return None

        avg_latency = total_latency / success_count
        print(f"{tracker} succeeded {success_count}/10 times, avg latency {avg_latency:.2f}ms")
        return (tracker, success_count, avg_latency)

    def check_trackers(self):
        if not self.trackers:
            return []

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        tasks = [self._check_tracker(t) for t in self.trackers]
        results = loop.run_until_complete(asyncio.gather(*tasks))

        valid = [r for r in results if r]
        sorted_trackers = sorted(valid, key=lambda x: (-x[1], x[2]))
        best_trackers = [t[0] for t in sorted_trackers[:self.best_tracker_count]]

        print(f"\nBest {len(best_trackers)} trackers:")
        for t in sorted_trackers[:self.best_tracker_count]:
            print(f"{t[0]} - {t[1]} successes, avg {t[2]:.2f}ms")

        return best_trackers

def update_tracker(trackers):
    client = qbittorrentapi.Client(host='http://127.0.0.1:8080')
    try:
        client.auth_log_in()
        print("\nConnected to qBittorrent:")
    except Exception as e:
        print(f"qBit connection failed: {e}")
        return

    try:
        client.app_set_preferences({"add_trackers": "\n".join(trackers)})
        print("Updated default trackers list")

        for torrent in client.torrents_info():
            current = [t["url"] for t in client.torrents_trackers(torrent.hash)]
            to_remove = [t for t in current if t not in trackers]
            for t in to_remove:
                client.torrents_remove_trackers(torrent.hash, t)
            to_add = [t for t in trackers if t not in current]
            for t in to_add:
                client.torrents_add_trackers(torrent.hash, t)

        print(f"Updated {len(client.torrents_info())} torrents")
    except Exception as e:
        print(f"Update failed: {e}")

if __name__ == "__main__":
    checker = TrackerChecker(trackers_url=TRACKERSLIST_ALL)
    checker.fetch_trackers()
    best_trackers = checker.check_trackers()
    update_tracker(best_trackers)
