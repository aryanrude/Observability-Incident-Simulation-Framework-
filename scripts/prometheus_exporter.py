#!/usr/bin/env python3
"""
prometheus_exporter.py
Exposes simulation metrics on :8000/metrics for Prometheus scraping.
Grafana dashboards point at this exporter for real-time visualisation.

Run alongside simulate_failures.py:
    python prometheus_exporter.py &
    python simulate_failures.py --scenario cpu

Metrics exposed:
    sim_cpu_utilization_percent
    sim_memory_used_percent
    sim_latency_ms{quantile="0.99"}
    sim_disk_write_mbps
    sim_disk_read_mbps
    sim_scenario_active{scenario="..."}
"""

import os
import threading
import time

import psutil
from prometheus_client import Gauge, Info, start_http_server

PORT = int(os.getenv("PROM_PORT", "8000"))

# ── Metric definitions ────────────────────────────────────────────────────────
cpu_gauge      = Gauge("sim_cpu_utilization_percent",  "Simulated CPU utilization (%)")
mem_gauge      = Gauge("sim_memory_used_percent",      "Simulated memory used (%)")
latency_gauge  = Gauge("sim_latency_p99_ms",           "Simulated P99 latency (ms)")
disk_w_gauge   = Gauge("sim_disk_write_mbps",          "Simulated disk write MB/s")
disk_r_gauge   = Gauge("sim_disk_read_mbps",           "Simulated disk read MB/s")
scenario_gauge = Gauge("sim_scenario_active",
                       "1 if scenario is active", ["scenario"])
build_info     = Info("sim_framework", "Observability framework build metadata")

build_info.info({
    "version":     "1.0.0",
    "environment": "simulation",
    "author":      "devops-portfolio",
})


# ── Collector ─────────────────────────────────────────────────────────────────
def collect_system_metrics():
    """Background thread — refreshes gauges every 2 s using psutil."""
    while True:
        cpu_gauge.set(psutil.cpu_percent(interval=1))
        mem_gauge.set(psutil.virtual_memory().percent)

        # Disk I/O delta
        io1 = psutil.disk_io_counters()
        time.sleep(1)
        io2 = psutil.disk_io_counters()
        if io1 and io2:
            write_mb = (io2.write_bytes - io1.write_bytes) / (1024 * 1024)
            read_mb  = (io2.read_bytes  - io1.read_bytes)  / (1024 * 1024)
            disk_w_gauge.set(max(write_mb, 0))
            disk_r_gauge.set(max(read_mb,  0))

        time.sleep(1)


if __name__ == "__main__":
    print(f"Starting Prometheus exporter on :{PORT}/metrics")
    start_http_server(PORT)

    collector = threading.Thread(target=collect_system_metrics, daemon=True)
    collector.start()

    # Keep main thread alive
    while True:
        time.sleep(10)
