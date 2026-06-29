# Incident Runbook — Observability Simulation Framework

> **Purpose:** Step-by-step response procedures for each simulated failure type.  
> These runbooks were written alongside the simulation to validate that alerts fire correctly and responders have clear, tested guidance — reducing Mean Time to Repair (MTTR).

---

## RB-01 · High CPU Utilization

**Alert trigger:** `CpuUtilizationSimulated ≥ 85%` for 2 consecutive minutes

### Triage (< 2 min)
1. Open Grafana → _Observability Simulation_ dashboard → CPU panel.
2. Identify if spike is sustained or transient (single poll vs. continuous red).
3. SSH to host: `ssh -i ~/.ssh/<key>.pem ec2-user@<instance-ip>`

### Diagnosis
```bash
# Top CPU consumers
top -bn1 | head -20

# Check if simulation is running
ps aux | grep simulate_failures

# CPU history (last 10 min)
sar -u 2 5
```

### Remediation
| Cause | Action |
|-------|--------|
| `simulate_failures.py` (expected) | Let scenario complete; confirm CloudWatch alarm resolves |
| Unknown runaway process | `kill -9 <PID>` then investigate root cause |
| High-traffic microservice | Scale horizontally via Auto Scaling Group |

### Verification
```bash
# Confirm CPU drops below threshold
watch -n2 "mpstat 1 1 | tail -1"
```
**Expected:** CloudWatch alarm transitions to `OK` within 2 evaluation periods (2 min).

---

## RB-02 · High Memory Utilization

**Alert trigger:** `MemoryUsedPercent ≥ 80%` for 2 consecutive minutes

### Triage
```bash
free -h
cat /proc/meminfo | grep -E "MemTotal|MemAvailable|Cached"
```

### Diagnosis
```bash
# Top memory consumers
ps aux --sort=-%mem | head -15

# OOM killer activity
dmesg | grep -i "oom\|killed"

# Detailed memory breakdown
smem -r | head -20
```

### Remediation
| Cause | Action |
|-------|--------|
| Simulation allocation (expected) | Wait for scenario to complete; `del chunks` frees memory automatically |
| Memory leak in application | Restart service: `systemctl restart <service>` |
| Insufficient instance size | Resize: stop → change instance type → start |

---

## RB-03 · High P99 Latency

**Alert trigger:** `P99ResponseTimeMs ≥ 1000ms` for 1 evaluation period

### Triage
```bash
# Check if tc netem rule is active (simulation)
tc qdisc show dev lo

# Measure round-trip on loopback
ping -c5 127.0.0.1
```

### Diagnosis
```bash
# Network interface stats
ss -s
netstat -i

# Active connections count
ss -tn | awk '{print $4}' | cut -d: -f1 | sort | uniq -c | sort -rn
```

### Remediation
| Cause | Action |
|-------|--------|
| Latency simulation via tc | `sudo tc qdisc del dev lo root` |
| Network congestion | Check VPC flow logs; adjust NACLs / security groups |
| Overloaded downstream service | Scale that service; enable circuit breaker |

---

## RB-04 · Disk I/O Saturation

**Alert trigger:** `DiskWriteMBps ≥ 100` for 2 consecutive minutes

### Triage
```bash
iostat -xz 2 5
```

### Diagnosis
```bash
# Which process is doing I/O
iotop -o -b -n 3

# Find large temp files from simulation
du -sh /tmp/* | sort -rh | head -10
```

### Remediation
| Cause | Action |
|-------|--------|
| `_sim_disk_payload` temp file | Kill simulator or wait; file auto-deleted |
| Log file explosion | `truncate -s 0 /path/to/logfile`; check logrotate config |
| Runaway backup | Identify and throttle: `ionice -c 3 -p <PID>` |

---

## Post-Incident Checklist

- [ ] Alarm fired within SLA (< 3 min of threshold breach)
- [ ] Grafana dashboard reflected anomaly in real-time
- [ ] Runbook steps produced expected output
- [ ] Simulation metrics visible in CloudWatch console
- [ ] `simulation.log` captured full scenario timeline
- [ ] SNS email notification received
- [ ] Document any gaps found → open GitHub Issue

---

## MTTR Targets

| Severity | Target MTTR |
|----------|------------|
| P1 — Production outage | < 15 min |
| P2 — Degraded service | < 30 min |
| P3 — Performance anomaly | < 60 min |

> These runbooks are living documents. Update after every incident drill.
