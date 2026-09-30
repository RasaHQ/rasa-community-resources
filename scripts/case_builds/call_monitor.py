#!/usr/bin/env python3
"""Watch the agent process during a case-build run: where it connects, and what it costs locally.

    python3 scripts/case_builds/call_monitor.py --out <file.json> &
    python3 scripts/case_builds/run_build.py examples/<build> ...

macOS, standard library only, no root. It waits for the agent process the
harness starts (a command line containing `usage_launcher.py`), then until
that process exits:

- every `--interval` seconds (default 0.2) lists the internet sockets of the
  agent and all its descendants with `lsof -nP -i`, and keeps every distinct
  (process, local address, remote address) with first and last sighting;
- every second samples CPU and resident memory of each of those processes
  (`ps`) and the GPU's "Device Utilization %" (`ioreg`, the figure Activity
  Monitor shows).

At the end it resolves each remote address (reverse DNS, and a forward
lookup of the hosts in `--expect` for comparison) and writes one JSON file.

What it cannot see: a connection that opens and closes between two samples,
and DNS lookups, which macOS makes in mDNSResponder, not in the agent. The
report says so. It records addresses, never payloads.
"""

from __future__ import annotations

import argparse
import json
import re
import signal
import socket
import statistics
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

LOOPBACK = re.compile(r"^(127\.|\[::1\]|localhost|\*)")


def run(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout
    except (subprocess.TimeoutExpired, OSError):
        return ""


def find_roots(match: str) -> list[int]:
    return [int(p) for p in run(["pgrep", "-f", match]).split()]


def descendants(roots: list[int]) -> list[int]:
    seen, todo = set(roots), list(roots)
    while todo:
        for child in run(["pgrep", "-P", str(todo.pop())]).split():
            if int(child) not in seen:
                seen.add(int(child))
                todo.append(int(child))
    return sorted(seen)


def alive(pids: list[int]) -> bool:
    return bool(pids) and bool(run(["ps", "-o", "pid=", "-p", ",".join(map(str, pids))]).strip())


def sockets(pids: list[int]) -> list[dict]:
    out = run(["lsof", "-nP", "-i", "-a", "-p", ",".join(map(str, pids))])
    rows = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 9:
            continue
        name = " ".join(parts[8:])
        state = re.search(r"\((\w+)\)$", name)
        address = re.sub(r"\s*\(\w+\)$", "", name)
        local, _, remote = address.partition("->")
        rows.append({"command": parts[0], "pid": int(parts[1]), "proto": parts[7], "local": local,
                     "remote": remote or None, "state": state.group(1) if state else None})
    return rows


def cpu(pids: list[int]) -> list[dict]:
    out = run(["ps", "-o", "pid=,%cpu=,rss=,comm=", "-p", ",".join(map(str, pids))])
    rows = []
    for line in out.splitlines():
        parts = line.split(None, 3)
        if len(parts) == 4:
            rows.append({"pid": int(parts[0]), "cpu_pct": float(parts[1]), "rss_mb": round(int(parts[2]) / 1024, 1),
                         "command": Path(parts[3]).name})
    return rows


def gpu_utilisation() -> float | None:
    match = re.search(r'"Device Utilization %"=(\d+)', run(["ioreg", "-r", "-d", "1", "-w", "0", "-c", "IOAccelerator"]))
    return float(match.group(1)) if match else None


def host_of(address: str) -> str:
    return address.rsplit(":", 1)[0].strip("[]")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--match", default="usage_launcher.py")
    parser.add_argument("--interval", type=float, default=0.2)
    parser.add_argument("--wait", type=float, default=900, help="seconds to wait for the agent to start")
    parser.add_argument("--expect", nargs="*", default=["api.openai.com", "api.anthropic.com",
                        "api.deepgram.com", "huggingface.co", "api.segment.io", "rasa.com"])
    args = parser.parse_args()

    stop = False

    def _stop(*_):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    deadline = time.monotonic() + args.wait
    roots: list[int] = []
    while not stop and time.monotonic() < deadline and not roots:
        roots = find_roots(args.match)
        time.sleep(0.2)
    if not roots:
        print("call_monitor: agent process never appeared")
        return 1
    started = datetime.now(timezone.utc)
    flows: dict[tuple, dict] = {}
    cpu_samples: list[dict] = []
    gpu_samples: list[float] = []
    samples = 0
    next_cpu = 0.0
    pids = descendants(roots)
    while not stop and alive(roots):
        pids = descendants(roots)
        now = time.time()
        for row in sockets(pids):
            key = (row["command"], row["proto"], row["local"], row["remote"])
            flow = flows.setdefault(key, {**row, "first_seen": now, "last_seen": now, "sightings": 0, "states": []})
            flow["last_seen"] = now
            flow["sightings"] += 1
            if row["state"] and row["state"] not in flow["states"]:
                flow["states"].append(row["state"])
        samples += 1
        if time.monotonic() >= next_cpu:
            next_cpu = time.monotonic() + 1.0
            cpu_samples.append({"t": now, "processes": cpu(pids)})
            g = gpu_utilisation()
            if g is not None:
                gpu_samples.append(g)
        time.sleep(args.interval)

    remote_hosts = sorted({host_of(f["remote"]) for f in flows.values() if f["remote"]})
    external = [h for h in remote_hosts if not LOOPBACK.match(h)]
    reverse = {}
    for host in external:
        try:
            reverse[host] = socket.gethostbyaddr(host)[0]
        except OSError:
            reverse[host] = None
    forward = {}
    for name in args.expect:
        try:
            forward[name] = sorted({i[4][0] for i in socket.getaddrinfo(name, 443)})
        except OSError:
            forward[name] = []
    by_command: dict[str, dict] = {}
    for sample in cpu_samples:
        for proc in sample["processes"]:
            entry = by_command.setdefault(proc["command"], {"cpu_pct": [], "rss_mb": []})
            entry["cpu_pct"].append(proc["cpu_pct"])
            entry["rss_mb"].append(proc["rss_mb"])
    report = {
        "started_at": started.isoformat(timespec="seconds"),
        "ended_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "interval_s": args.interval,
        "socket_samples": samples,
        "processes_watched": sorted({f["command"] for f in flows.values()} | set(by_command)),
        "external_remote_hosts": [
            {"address": h, "reverse_dns": reverse[h],
             "matches_expected": [n for n, ips in forward.items() if h in ips],
             "commands": sorted({f["command"] for f in flows.values() if f["remote"] and host_of(f["remote"]) == h}),
             "ports": sorted({f["remote"].rsplit(":", 1)[1] for f in flows.values()
                              if f["remote"] and host_of(f["remote"]) == h})}
            for h in external
        ],
        "loopback_remote_ports": sorted({f["remote"].rsplit(":", 1)[1] for f in flows.values()
                                         if f["remote"] and LOOPBACK.match(host_of(f["remote"]))}),
        "listening": sorted({f"{f['command']} {f['local']}" for f in flows.values() if "LISTEN" in f["states"]}),
        "forward_lookups": forward,
        "flows": sorted(flows.values(), key=lambda f: f["first_seen"]),
        "cpu_by_command": {
            k: {"samples": len(v["cpu_pct"]), "cpu_pct_mean": round(statistics.mean(v["cpu_pct"]), 1),
                "cpu_pct_max": max(v["cpu_pct"]), "rss_mb_max": max(v["rss_mb"])}
            for k, v in sorted(by_command.items())
        },
        "gpu_device_utilisation_pct": {
            "samples": len(gpu_samples),
            "mean": round(statistics.mean(gpu_samples), 1) if gpu_samples else None,
            "max": max(gpu_samples) if gpu_samples else None,
            "p95": sorted(gpu_samples)[int(0.95 * len(gpu_samples)) - 1] if gpu_samples else None,
            "note": "whole-GPU figure from ioreg, all processes on the Mac, sampled once a second",
        },
        "limits": ("lsof sampling every interval_s: a connection opened and closed between two samples is not "
                   "seen; DNS lookups happen in mDNSResponder, not in the agent, and are not listed"),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n")
    print(f"call_monitor: {samples} samples, external hosts {external}, wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
