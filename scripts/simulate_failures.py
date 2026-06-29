#!/usr/bin/env python3
"""
Observability & Incident Simulation Framework
simulate_failures.py — Triggers controlled system failure scenarios to validate
monitoring pipelines (CloudWatch, Prometheus, Grafana alerting).

Usage:
    python simulate_failures.py --scenario cpu       # CPU exhaustion
    python simulate_failures.py --scenario latency   # Network latency injection
    python simulate_failures.py --scenario memory    # Memory pressure
    python simulate_failures.py --scenario disk      # Disk I/O saturation
    python simulate_failures.py --scenario all       # Run all scenarios sequentially
"""

import argparse
import logging
import multiprocessing
import os
import random
import subprocess
import sys
import time
import threading
from datetime import datetime

import boto3
import psutil

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/tmp/simulation.log"),
    ],
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
AWS_REGION        = os.getenv("AWS_REGION", "ap-south-1")
CLOUDWATCH_NS     = os.getenv("CW_NAMESPACE", "ObservabilityFramework")
EC2_INSTANCE_ID   = os.getenv("INSTANCE_ID", "i-0000000000000000")  # override via env
SCENARIO_DURATION = int(os.getenv("SCENARIO_DURATION_SECS", "60"))   # default 60 s


# ── CloudWatch helper ─────────────────────────────────────────────────────────
class MetricEmitter:
    """Pushes custom metrics to CloudWatch so alerts fire during simulation."""

    def __init__(self):
        self.cw = boto3.client("cloudwatch", region_name=AWS_REGION)

    def put(self, metric_name: str, value: float, unit: str = "None", dims: dict = None):
        dimensions = [
            {"Name": "InstanceId", "Value": EC2_INSTANCE_ID},
            {"Name": "Environment", "Value": "simulation"},
        ]
        if dims:
            for k, v in dims.items():
                dimensions.append({"Name": k, "Value": str(v)})

        try:
            self.cw.put_metric_data(
                Namespace=CLOUDWATCH_NS,
                MetricData=[
                    {
                        "MetricName": metric_name,
                        "Dimensions": dimensions,
                        "Value": value,
                        "Unit": unit,
                        "Timestamp": datetime.utcnow(),
                    }
                ],
            )
            log.debug("CW metric %s = %.2f %s", metric_name, value, unit)
        except Exception as exc:
            log.warning("CloudWatch put_metric_data failed: %s", exc)


emitter = MetricEmitter()


# ── Scenario: CPU Exhaustion ──────────────────────────────────────────────────
def _cpu_burner(stop_event: threading.Event):
    """Spin on a single core until stop_event is set."""
    while not stop_event.is_set():
        _ = [x**2 for x in range(10_000)]


def simulate_cpu_exhaustion(duration: int = SCENARIO_DURATION):
    """
    Spins up (n_cores - 1) threads to push CPU utilisation above 90 %.
    Emits custom CloudWatch metric: CpuUtilizationSimulated (Percent).
    """
    n_cores = multiprocessing.cpu_count()
    workers = max(n_cores - 1, 1)
    log.info("▶ CPU Exhaustion — spinning %d threads for %ds", workers, duration)

    stop = threading.Event()
    threads = [threading.Thread(target=_cpu_burner, args=(stop,), daemon=True)
               for _ in range(workers)]
    for t in threads:
        t.start()

    deadline = time.time() + duration
    while time.time() < deadline:
        cpu_pct = psutil.cpu_percent(interval=1)
        emitter.put("CpuUtilizationSimulated", cpu_pct, "Percent")
        log.info("  CPU: %.1f%%", cpu_pct)

    stop.set()
    for t in threads:
        t.join(timeout=2)
    log.info("✔ CPU Exhaustion scenario complete")


# ── Scenario: Memory Pressure ─────────────────────────────────────────────────
def simulate_memory_pressure(duration: int = SCENARIO_DURATION, target_mb: int = 512):
    """
    Allocates `target_mb` MB of RAM in blocks, holds it for `duration` seconds.
    Emits: MemoryUsedPercent (Percent).
    """
    log.info("▶ Memory Pressure — allocating %d MB for %ds", target_mb, duration)
    chunks = []
    block_mb = 64
    try:
        while sum(len(c) for c in chunks) < target_mb * 1024 * 1024:
            chunks.append(bytearray(block_mb * 1024 * 1024))
            mem = psutil.virtual_memory()
            pct = mem.percent
            emitter.put("MemoryUsedPercent", pct, "Percent")
            log.info("  RAM: %.1f%% used", pct)
            time.sleep(0.5)

        log.info("  Holding allocation for %ds …", duration)
        deadline = time.time() + duration
        while time.time() < deadline:
            mem = psutil.virtual_memory()
            emitter.put("MemoryUsedPercent", mem.percent, "Percent")
            time.sleep(2)
    finally:
        del chunks
        log.info("✔ Memory Pressure scenario complete")


# ── Scenario: Network Latency Injection ──────────────────────────────────────
def simulate_latency(duration: int = SCENARIO_DURATION, delay_ms: int = 500):
    """
    Uses `tc` (traffic control) to add egress latency on lo.
    Requires: iproute2 and sudo/root.
    Emits: LatencyInjectedMs (Milliseconds) + simulated P99 response time.
    """
    iface = "lo"  # loopback — safe for lab environments
    log.info("▶ Latency Injection — adding %dms delay on %s for %ds",
             delay_ms, iface, duration)

    def _tc(args: list):
        cmd = ["sudo", "tc"] + args
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            log.warning("tc error: %s", result.stderr.strip())
        return result.returncode == 0

    # Add root qdisc + netem delay
    _tc(["qdisc", "add", "dev", iface, "root", "netem",
         "delay", f"{delay_ms}ms", "10ms", "distribution", "normal"])

    try:
        deadline = time.time() + duration
        while time.time() < deadline:
            jitter = random.randint(-50, 50)
            observed = delay_ms + jitter
            emitter.put("LatencyInjectedMs", observed, "Milliseconds")
            emitter.put("P99ResponseTimeMs", observed * 1.8, "Milliseconds")
            log.info("  Latency: ~%dms", observed)
            time.sleep(2)
    finally:
        _tc(["qdisc", "del", "dev", iface, "root"])
        log.info("✔ Latency Injection scenario complete")


# ── Scenario: Disk I/O Saturation ────────────────────────────────────────────
def simulate_disk_io(duration: int = SCENARIO_DURATION):
    """
    Writes/reads a large temp file repeatedly to saturate disk I/O.
    Emits: DiskWriteMBps (Count), DiskReadMBps (Count).
    """
    tmp_path = "/tmp/_sim_disk_payload"
    chunk = b"X" * (4 * 1024 * 1024)  # 4 MB block
    log.info("▶ Disk I/O Saturation — hammering %s for %ds", tmp_path, duration)

    deadline = time.time() + duration
    while time.time() < deadline:
        t0 = time.time()
        with open(tmp_path, "wb") as f:
            for _ in range(8):          # 32 MB write burst
                f.write(chunk)
        write_secs = time.time() - t0

        t0 = time.time()
        with open(tmp_path, "rb") as f:
            while f.read(4 * 1024 * 1024):
                pass
        read_secs = time.time() - t0

        write_mbps = 32 / write_secs if write_secs > 0 else 0
        read_mbps  = 32 / read_secs  if read_secs  > 0 else 0
        emitter.put("DiskWriteMBps", write_mbps, "Count")
        emitter.put("DiskReadMBps",  read_mbps,  "Count")
        log.info("  Write: %.1f MB/s  Read: %.1f MB/s", write_mbps, read_mbps)

    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    log.info("✔ Disk I/O Saturation scenario complete")


# ── Runner ────────────────────────────────────────────────────────────────────
SCENARIOS = {
    "cpu":     simulate_cpu_exhaustion,
    "memory":  simulate_memory_pressure,
    "latency": simulate_latency,
    "disk":    simulate_disk_io,
}


def main():
    parser = argparse.ArgumentParser(description="Incident Simulation Framework")
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIOS.keys()) + ["all"],
        required=True,
        help="Failure scenario to run",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=SCENARIO_DURATION,
        help=f"Duration in seconds (default: {SCENARIO_DURATION})",
    )
    args = parser.parse_args()

    if args.scenario == "all":
        for name, fn in SCENARIOS.items():
            log.info("═══ Running scenario: %s ═══", name.upper())
            fn(duration=args.duration)
            time.sleep(5)   # cooldown between scenarios
    else:
        fn = SCENARIOS[args.scenario]
        fn(duration=args.duration)


if __name__ == "__main__":
    main()
