# Observability & Incident Simulation Framework

> **A production-grade framework to simulate system failures and validate monitoring pipelines — so your on-call runbooks work before 3 AM when it matters.**

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![AWS](https://img.shields.io/badge/AWS-CloudWatch-orange)](https://aws.amazon.com/cloudwatch/)
[![Terraform](https://img.shields.io/badge/IaC-Terraform-7B42BC)](https://terraform.io)
[![Prometheus](https://img.shields.io/badge/Metrics-Prometheus-E6522C)](https://prometheus.io)
[![Grafana](https://img.shields.io/badge/Dashboards-Grafana-F46800)](https://grafana.com)

---

## Problem Statement

Monitoring setups are often only tested *during real incidents* — too late. This framework deliberately triggers controlled failure scenarios (CPU exhaustion, memory pressure, network latency, disk I/O saturation) on a sandboxed EC2 instance, then validates that:
- CloudWatch alarms fire within SLA
- Grafana dashboards reflect anomalies in real-time
- On-call runbooks produce the expected diagnostic output

---

## Architecture

```
┌───────────────────────────────────────────────────────┐
│                   EC2 Instance (t3.micro)              │
│                                                       │
│  simulate_failures.py ──► psutil / tc / disk I/O     │
│         │                                             │
│         ▼                                             │
│  prometheus_exporter.py (:8000/metrics)               │
│         │                                             │
│         ├──► Prometheus scrape ──► Grafana dashboards │
│         │                                             │
│         └──► boto3.CloudWatch.put_metric_data         │
│                    │                                  │
│                    ▼                                  │
│            CloudWatch Alarms                          │
│                    │                                  │
│                    ▼                                  │
│              SNS Topic ──► Email notification         │
└───────────────────────────────────────────────────────┘

Infrastructure provisioned by Terraform (VPC, EC2, IAM, SNS, CW Log Group)
```

---

## Failure Scenarios

| Scenario | Trigger | CloudWatch Metric | Alert Threshold |
|----------|---------|-------------------|-----------------|
| CPU Exhaustion | Multi-threaded spin loop | `CpuUtilizationSimulated` | ≥ 85% for 2 min |
| Memory Pressure | `bytearray` allocation | `MemoryUsedPercent` | ≥ 80% for 2 min |
| Network Latency | `tc netem` delay injection | `P99ResponseTimeMs` | ≥ 1000 ms |
| Disk I/O Saturation | Repeated 32 MB write/read bursts | `DiskWriteMBps` | ≥ 100 MB/s |

---

## Project Structure

```
observability-framework/
├── scripts/
│   ├── simulate_failures.py        # Core failure simulator
│   ├── prometheus_exporter.py      # Prometheus metrics server
│   └── setup_cloudwatch_alarms.py  # One-time alarm provisioning
├── terraform/
│   └── main.tf                     # EC2 + VPC + IAM + SNS + CW
├── dashboards/
│   └── simulation_dashboard.json   # Grafana dashboard (import-ready)
├── runbooks/
│   └── INCIDENT_RUNBOOK.md         # Response procedures per scenario
├── requirements.txt
└── README.md
```

---

## Quick Start

### 1. Provision infrastructure
```bash
cd terraform/
terraform init
terraform apply \
  -var="key_name=your-key-pair" \
  -var="alert_email=you@example.com"
```

### 2. Deploy scripts to EC2
```bash
INSTANCE_IP=$(terraform output -raw instance_public_ip)
scp -r ../scripts requirements.txt ec2-user@$INSTANCE_IP:/opt/observability-sim/
ssh ec2-user@$INSTANCE_IP "cd /opt/observability-sim && pip3 install -r requirements.txt"
```

### 3. Set environment variables
```bash
export AWS_REGION=ap-south-1
export INSTANCE_ID=$(terraform output -raw instance_id)
export CW_NAMESPACE=ObservabilityFramework
export SCENARIO_DURATION_SECS=120
```

### 4. Create CloudWatch alarms
```bash
SNS_ARN=$(terraform output -raw sns_topic_arn)
python3 scripts/setup_cloudwatch_alarms.py --sns-arn $SNS_ARN
```

### 5. Start Prometheus exporter
```bash
python3 scripts/prometheus_exporter.py &
```

### 6. Run a scenario
```bash
# Single scenario
python3 scripts/simulate_failures.py --scenario cpu --duration 120

# All scenarios sequentially
python3 scripts/simulate_failures.py --scenario all --duration 60
```

### 7. Import Grafana dashboard
1. Open Grafana → `+` → **Import**
2. Upload `dashboards/simulation_dashboard.json`
3. Select your Prometheus data source → **Import**

---

## Observing Results

### CloudWatch Console
- Navigate to **CloudWatch → Alarms**
- Watch `HighCPUUtilization` / `HighMemoryUtilization` transition to `ALARM` state
- SNS sends email notification automatically

### Grafana
- Open the _Observability Simulation Framework_ dashboard
- All 4 panels update every 5 seconds
- Stat panels turn red when thresholds are breached

### Logs
```bash
tail -f /tmp/simulation.log
```

---

## Key Design Decisions

**Why custom CloudWatch namespace?**  
Separates simulation metrics from real EC2 metrics — avoids noise in production dashboards during testing.

**Why `tc netem` for latency?**  
Kernel-level traffic shaping is the most realistic way to simulate network degradation without touching application code. Used in production chaos engineering at Netflix/Amazon.

**Why Prometheus + CloudWatch (dual-stack)?**  
Mirrors real-world hybrid setups where teams run open-source (Prometheus/Grafana) alongside managed cloud monitoring (CloudWatch). Demonstrates ability to work across both ecosystems.

---

## Skills Demonstrated

- **Python** — `psutil`, `boto3`, `prometheus_client`, threading, subprocess
- **AWS CloudWatch** — custom metrics, alarms, SNS notifications, log groups
- **Prometheus** — custom exporter, Gauge metrics, scrape configuration
- **Grafana** — dashboard JSON, threshold-based coloring, stat panels, alertlist
- **Linux internals** — `tc` / netem, `sar`, `iostat`, `iotop`, `/proc/meminfo`
- **Terraform** — VPC, EC2, IAM roles/policies, SNS, CloudWatch log groups
- **Incident management** — runbook authoring, MTTR targets, post-incident checklist

---

## Teardown
```bash
cd terraform/
terraform destroy -var="key_name=your-key-pair" -var="alert_email=you@example.com"
```

---

## License
MIT — use freely for portfolio, learning, and interview demonstrations.
