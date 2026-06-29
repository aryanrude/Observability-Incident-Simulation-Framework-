# Observability Incident Simulation Framework

> A practical framework I built to simulate real system failures and test monitoring + on-call runbooks before they matter at 3 AM.

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![AWS](https://img.shields.io/badge/AWS-CloudWatch-orange)](https://aws.amazon.com/cloudwatch/)
[![Terraform](https://img.shields.io/badge/IaC-Terraform-7B42BC)](https://terraform.io)
[![Prometheus](https://img.shields.io/badge/Metrics-Prometheus-E6522C)](https://prometheus.io)
[![Grafana](https://img.shields.io/badge/Dashboards-Grafana-F46800)](https://grafana.com)

---

## Why I Built This

After dealing with a few production incidents where alerts fired late or runbooks were unclear, I got tired of testing monitoring only during real outages. So I created this framework to **deliberately** trigger failures in a safe environment and validate the entire observability stack.

It helps answer: "If this breaks, will we actually know — and will we know what to do?"

---

## What It Does

- Triggers realistic failure scenarios (CPU exhaustion, memory pressure, network latency, disk I/O) on an EC2 instance
- Validates CloudWatch alarms, Prometheus metrics, and Grafana dashboards
- Tests on-call runbooks against actual failures
- Sends SNS notifications just like in production

---

## Architecture
┌───────────────────────────────────────────────────────┐
│                EC2 Instance (t3.micro)                | 
│                                                       │
│  simulate_failures.py  →  psutil / tc / disk I/O      │
│         │                                             │
│         ▼                                             │
│  prometheus_exporter.py (:8000/metrics)               │
│         │                                             │
│    ├────► Prometheus → Grafana Dashboards             │
│    └────► boto3 → CloudWatch Custom Metrics           │
│                    │                                  │
│                    ▼                                  │
│               CloudWatch Alarms                       │
│                    │                                  │
│                    ▼                                  │
│                 SNS → Email                           │
└───────────────────────────────────────────────────────┘



Infrastructure is fully managed with Terraform.

---

## Failure Scenarios

| Scenario              | Trigger                        | CloudWatch Metric       | Alert Threshold          |
|-----------------------|--------------------------------|-------------------------|--------------------------|
| CPU Exhaustion        | Multi-threaded spin loop       | `CpuUtilizationSimulated` | ≥ 85% for 2 min        |
| Memory Pressure       | `bytearray` allocation         | `MemoryUsedPercent`     | ≥ 80% for 2 min          |
| Network Latency       | `tc netem` delay injection     | `P99ResponseTimeMs`     | ≥ 1000 ms                |
| Disk I/O Saturation   | Repeated 32MB write/read bursts| `DiskWriteMBps`         | ≥ 100 MB/s               |

---

## Project Structure

observability-framework/
├── scripts/
│   ├── simulate_failures.py        # Main failure injector
│   ├── prometheus_exporter.py      # Prometheus metrics endpoint
│   └── setup_cloudwatch_alarms.py  # Creates CloudWatch alarms
├── terraform/
│   └── main.tf                     # Full infra (VPC, EC2, IAM, SNS)
├── dashboards/
│   └── simulation_dashboard.json    # Grafana dashboard
├── runbooks/
│   └── INCIDENT_RUNBOOK.md         # Tested response procedures
├── requirements.txt
└── README.md




## Observing Results

CloudWatch: Check Alarms — you should see them go into ALARM state + receive email via SNS
Grafana: Open the imported dashboard — panels turn red during simulations
Logs: tail -f /tmp/simulation.log


Key Design Decisions

Custom CloudWatch namespace (ObservabilityFramework): Prevents simulation metrics from polluting real production dashboards.
tc netem for latency: Most realistic kernel-level approach without modifying application code (widely used in chaos engineering).
Dual-stack monitoring (CloudWatch + Prometheus/Grafana): Mirrors real-world hybrid environments I’ve worked with.


Skills Demonstrated / Learned

Python — psutil, boto3, prometheus_client, threading, subprocess
AWS — Custom metrics, CloudWatch alarms, IAM policies, SNS notifications
IaC — Terraform (VPC, EC2, Security Groups, IAM roles)
Observability — Prometheus custom exporter + Grafana dashboard authoring
Linux — tc / netem, iostat, sar, iotop, memory analysis
Incident Management — Runbook creation and validation through live simulations


Teardown
Bashcd terraform/
terraform destroy -var="key_name=your-key-pair" -var="alert_email=your@email.com"

Status: Fully working. I tested it end-to-end multiple times with different scenarios. Screenshots from real runs are available in the screenshot/ folder.
