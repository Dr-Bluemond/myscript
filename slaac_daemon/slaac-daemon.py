#!/usr/bin/env python3
"""Simple SLAAC daemon (pure stdlib).

- Runs `radvdump` and parses its output.
- Extracts: prefix, prefix length (mask), gateway (RA source address).
- Applies IPv6 address + default route via `ip`.

Requires on target host: radvdump, iproute2.
"""

import argparse
import ipaddress
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


_RE_RA_FROM = re.compile(r"^#\s*based\s+on\s+Router\s+Advertisement\s+from\s+([0-9a-fA-F:]+)\s*$")
_RE_PREFIX = re.compile(r"^\s*prefix\s+([0-9a-fA-F:]+)\/(\d+)\s*$")


def log(message: str) -> None:
    ts = datetime.now().strftime("%F %T")
    print(f"[{ts}] {message}", flush=True)


@dataclass(frozen=True)
class RaState:
    prefix: str
    prefix_len: int
    gateway: str


def calc_host_address(prefix: str, prefix_len: int) -> str:
    # Use stdlib ipaddress for correctness; parsing itself is done via re.
    net = ipaddress.IPv6Network(f"{prefix}/{prefix_len}", strict=False)
    host = net.network_address + 1
    return str(host)


def run_ip(args: list[str]) -> None:
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)


def apply_address(iface: str, prefix: str, prefix_len: int, gateway: str) -> None:
    addr = calc_host_address(prefix, prefix_len)

    log(f"applying: prefix={prefix}/{prefix_len} addr={addr}/{prefix_len} gw={gateway}")

    # Similar to the bash version: flush global, add address, set default route.
    run_ip(["ip", "-6", "addr", "flush", "dev", iface, "scope", "global"])
    run_ip(["ip", "-6", "addr", "add", f"{addr}/{prefix_len}", "dev", iface])
    run_ip(["ip", "-6", "route", "replace", "default", "via", gateway, "dev", iface])


def monitor_radvdump(iface: str) -> None:
    last_applied: Optional[RaState] = None
    gateway: Optional[str] = None

    while True:
        log(f"starting radvdump on {iface}...")
        try:
            proc = subprocess.Popen(
                ["radvdump"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError:
            log("error: radvdump not found in PATH")
            raise

        # After listener is up, send one RS to solicit an RA (ignore output).
        try:
            subprocess.run(
                ["rdisc6", "-1", "-q", iface],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=5,
                text=True,
            )
        except FileNotFoundError:
            log("warn: rdisc6 not found in PATH; waiting for unsolicited RA")
        except subprocess.TimeoutExpired:
            log("warn: rdisc6 timed out; waiting for unsolicited RA")

        try:
            assert proc.stdout is not None
            for raw_line in proc.stdout:
                line = raw_line.rstrip("\n")

                m = _RE_RA_FROM.match(line)
                if m:
                    gateway = m.group(1)
                    log(f"gateway received: {gateway}")
                    continue

                m = _RE_PREFIX.match(line)
                if not m:
                    continue

                prefix = m.group(1)
                prefix_len = int(m.group(2))
                log(f"prefix received: {prefix}/{prefix_len}")

                if not gateway:
                    log("warn: got prefix but no gateway yet; skipping apply")
                    continue

                new_state = RaState(prefix=prefix, prefix_len=prefix_len, gateway=gateway)
                if new_state == last_applied:
                    continue

                log(
                    f"change detected: "
                    f"{(last_applied.prefix + '/' + str(last_applied.prefix_len)) if last_applied else 'None'} -> {prefix}/{prefix_len}, "
                    f"gw={(last_applied.gateway if last_applied else 'None')} -> {gateway}"
                )

                try:
                    apply_address(iface, prefix, prefix_len, gateway)
                except subprocess.CalledProcessError as e:
                    stderr = (e.stderr or "").strip()
                    log(f"error: ip command failed: {e.cmd}; stderr={stderr}")
                    continue
                last_applied = new_state
        finally:
            try:
                proc.stdout and proc.stdout.close()
            except Exception:
                pass

            # Ensure process is gone.
            try:
                proc.terminate()
            except Exception:
                pass
            try:
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

        log("radvdump exited; restarting in 1s")
        time.sleep(1)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Simple SLAAC daemon (parse radvdump output).")
    parser.add_argument("iface", help="network interface, e.g. eth0")
    args = parser.parse_args(argv)

    iface = args.iface
    log(f"slaac-daemon starting on {iface}")
    monitor_radvdump(iface)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
