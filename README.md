# Observability & Incident Simulation Framework

A Python-based framework I built to simulate real system failures on AWS EC2 and validate that monitoring pipelines (CloudWatch, Prometheus, Grafana) actually catch them — before an actual incident does.

The core idea: most teams only discover their alerting is broken *during* a production incident. This project lets you break things on purpose, in a controlled sandbox, and confirm your runbooks work before 3 AM.

---

## What it does

Four failure scenarios, each triggering real OS-level stress:

| Scenario | How it works | Metric pushed |
|----------|-------------|---------------|
| CPU Exhaustion | Multi-threaded spin loop via Python threading | `CpuUtilizationSimulated` |
| Memory Pressure | Allocates 512 MB in bytearray blocks | `MemoryUsedPercent` |
| Latency Injection | `tc netem` adds 500ms delay at kernel level | `P99ResponseTimeMs` |
| Disk I/O Saturation | Repeated 32 MB write/read bursts to /tmp | `DiskWriteMBps` |

Each scenario pushes custom metrics to CloudWatch via `boto3` in real time. A Prometheus exporter running on `:8000/metrics` exposes the same data for Grafana.

---

## Stack

- **Python** — `psutil`, `boto3`, `prometheus_client`, threading, subprocess
- **AWS** — EC2 (t3.micro), CloudWatch custom metrics + alarms, SNS, IAM, VPC
- **Terraform** — provisions all 13 AWS resources end to end
- **Prometheus + Grafana** — open-source observability layer alongside CloudWatch
- **Linux** — `tc netem`, `sar`, `iostat`, `/proc/meminfo`

---

## Architecture

```
simulate_failures.py
    ├── psutil / tc / disk I/O  →  actual OS stress
    ├── boto3.put_metric_data   →  CloudWatch custom namespace
    └── prometheus_exporter.py  →  :8000/metrics → Grafana

CloudWatch
    └── Alarms (4) → SNS → Email notification

Terraform
    └── VPC → EC2 → IAM Role → SNS Topic → CW Log Group
```

---

## Project Structure

```
observability-framework/
├── scripts/
│   ├── simulate_failures.py        # Core simulator — all 4 scenarios
│   ├── prometheus_exporter.py      # Prometheus /metrics endpoint
│   └── setup_cloudwatch_alarms.py  # Creates 4 CloudWatch alarms
├── terraform/
│   └── main.tf                     # Full AWS infrastructure
├── dashboards/
│   └── simulation_dashboard.json   # Grafana dashboard (import-ready)
├── runbooks/
│   └── INCIDENT_RUNBOOK.md         # Per-scenario response procedures
├── docs/screenshots/               # Live proof from actual AWS run
└── requirements.txt
```

---

## Running it

### 1. Infrastructure
```bash
cd terraform/
terraform init
terraform apply \
  -var="key_name=your-key-pair" \
  -var="alert_email=you@example.com"
```
Provisions 13 resources: VPC, subnet, IGW, route table, security group, IAM role + policy + instance profile, EC2, SNS topic + subscription, CloudWatch log group.

### 2. Deploy to EC2
```bash
INSTANCE_IP=$(terraform output -raw instance_public_ip)
ssh -i "your-key.pem" ec2-user@$INSTANCE_IP
git clone https://github.com/aryanrude/Observability-Incident-Simulation-Framework-.git /opt/observability-sim
cd /opt/observability-sim
pip3 install -r requirements.txt
```

### 3. Set environment and run
```bash
export AWS_REGION=ap-south-1
export INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
export CW_NAMESPACE=ObservabilityFramework
export SCENARIO_DURATION_SECS=120

# Single scenario
python3 scripts/simulate_failures.py --scenario cpu --duration 120

# All scenarios sequentially
python3 scripts/simulate_failures.py --scenario all --duration 60
```

### 4. Create CloudWatch alarms
```bash
SNS_ARN=arn:aws:sns:ap-south-1:<account-id>:observability-sim-alerts
python3 scripts/setup_cloudwatch_alarms.py --sns-arn $SNS_ARN
```

### 5. Import Grafana dashboard
Import `dashboards/simulation_dashboard.json` → select your Prometheus data source.

---

## What I actually observed running this

When I ran `--scenario all` on a t3.micro in ap-south-1:

- **CPU** held at ~50% (t3.micro has 2 vCPUs, one core saturated) — `HighCPUUtilization` alarm fired within 1 minute
- **Memory** climbed from 45% → 90% as 512 MB was allocated in blocks, then dropped back when the scenario ended and memory was freed
- **Disk I/O** hit 2300+ MB/s write throughput — well past the 100 MB/s alarm threshold (it never fired because CloudWatch metric data didn't arrive fast enough at that burst rate)
- **Latency** — `tc netem` injected 500ms on loopback; requires sudo which I confirmed works on the instance

All 6 custom metrics landed in CloudWatch under the `ObservabilityFramework` namespace. The `HighCPUUtilization` alarm went **In alarm** state and stayed there for the duration of the CPU scenario.

One thing I learned: `TreatMissingData: notBreaching` matters — when the simulation script stops, you don't want a cascade of false alarms. The alarm correctly returned to OK when the scenario ended.

---

## Screenshots

### All 4 alarms created — HighCPUUtilization In alarm
![Alarms Overview](docs/screenshots/02-all-alarms-overview.png)

### HighCPUUtilization alarm detail — firing with graph
![CPU Alarm Fired](docs/screenshots/01-cpu-alarm-fired.png)

### All 6 custom metrics in CloudWatch namespace
![Custom Metrics](docs/screenshots/03-custom-metrics-cloudwatch.png)

### CpuUtilizationSimulated time series graph
![Metrics Graph](docs/screenshots/05-cpu-metric-timeseries.png)

### Terminal — CPU and Memory scenarios running
![Terminal CPU Memory](docs/screenshots/06-simulation-terminal-cpu-memory.png)

### Terminal — Disk I/O scenario (2300+ MB/s)
![Terminal Disk IO](docs/screenshots/07-simulation-terminal-disk-io.png)

### Terraform destroy — 13 resources cleaned up
![Terraform Destroy](docs/screenshots/08-terraform-destroy-complete.png)

---

## Runbooks

Each scenario has a runbook in `runbooks/INCIDENT_RUNBOOK.md` covering:
- Triage steps (what to look at first)
- Diagnosis commands (`top`, `iotop`, `tc qdisc show`, `free -h`)
- Remediation table — expected cause vs. action
- Verification — how to confirm the alarm resolved

MTTR targets: P1 < 15 min, P2 < 30 min. Writing the runbooks exposed a gap — `sar` wasn't installed by default, so I added `sysstat` to the Terraform `user_data` bootstrap.

---

## Teardown
```bash
cd terraform/
terraform destroy -var="key_name=your-key-pair" -var="alert_email=you@example.com"
# Destroys all 13 resources
```

---

## License
MIT
