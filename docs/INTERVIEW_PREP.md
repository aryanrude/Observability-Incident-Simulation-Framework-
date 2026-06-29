# Interview Prep — Observability & Incident Simulation Framework

---

## ✅ Upgraded Resume Bullets

Replace the original two bullets with these (pick the ones that fit character limits):

### Option A — Impact-first (recommended for most JDs)
> Engineered a Python-based incident simulation framework on AWS EC2 that triggers controlled failure scenarios (CPU exhaustion, memory pressure, latency injection via `tc netem`, disk I/O saturation), emitting custom CloudWatch metrics and publishing to Prometheus — reducing alarm validation effort by eliminating manual failure reproduction.

> Authored Grafana dashboards (8 panels, 5-second refresh) and scenario-specific runbooks with triage, diagnosis, and remediation steps, establishing MTTR targets of <15 min (P1) and <30 min (P2) validated through repeated drills.

### Option B — Tool-density (for JDs that keyword-match)
> Built an observability validation platform using Python (psutil, boto3, prometheus_client), AWS CloudWatch custom metrics/alarms, SNS notifications, Prometheus exporter, and Grafana dashboards — provisioned end-to-end with Terraform (VPC, EC2, IAM, SNS).

### Option C — Short version (for tight resume space)
> Developed a failure simulation framework (CPU, memory, latency, I/O) on AWS EC2 with CloudWatch alarms, Prometheus metrics, and Grafana dashboards; wrote runbooks targeting <15 min MTTR for P1 incidents.

---

## 🎤 Interview Questions & Answers

### Q1: "Walk me through what this project does."

**Answer framework (STAR):**
> "The problem I was solving is that most monitoring setups are only discovered to be broken *during* real incidents. I built a framework that deliberately induces four types of system failures — CPU exhaustion, memory pressure, network latency using Linux traffic control, and disk I/O saturation — on a sandboxed EC2 instance.

> The framework does two things simultaneously: it uses `psutil` to apply the failure, and it uses `boto3` to push custom metrics to CloudWatch. I also ran a Prometheus exporter in parallel so the same metrics appear in Grafana dashboards in real time.

> The result is that I can verify in advance whether the alarm fires, whether the Grafana panel turns red, and whether the runbook I wrote actually produces the right diagnostic output. I validated MTTR targets — under 15 minutes for a P1 incident."

---

### Q2: "Why did you use `tc netem` for latency simulation instead of mocking at the application layer?"

**Answer:**
> "`tc netem` operates at the kernel's network queueing discipline level — it affects all packets on that interface regardless of which process sends them. Application-level mocks only simulate latency for code you control; `tc` simulates it for the OS itself, which is much closer to what a real network degradation looks like.

> Companies like Netflix use this approach in their chaos engineering toolkits. The tradeoff is that it requires root/sudo and Linux-specific tooling, so it's not portable to non-Linux environments. For this framework — running on EC2 Amazon Linux — that was acceptable."

---

### Q3: "How did you structure your CloudWatch alarms? What's a PutMetricAlarm you set up?"

**Answer:**
> "I used a custom namespace called `ObservabilityFramework` to keep simulation metrics separate from the real EC2 metrics. Each alarm had three key decisions:
>
> 1. **Period and EvaluationPeriods** — for CPU I used 60-second period with 2 evaluation periods, so the alarm only fires if CPU stays above 85% for 2 full minutes. This avoids transient spikes causing false positives.
>
> 2. **TreatMissingData: notBreaching** — if the simulation script stops sending metrics, I don't want a cascade of false alarms. Missing data means the scenario ended.
>
> 3. **Unit matching** — CloudWatch is strict about units. If you emit a metric as `Percent` but define the alarm with no unit, the alarm never matches. I set the unit explicitly in both `put_metric_data` and `put_metric_alarm`."

---

### Q4: "What is the difference between Prometheus and CloudWatch? Why use both?"

**Answer:**
> "CloudWatch is AWS-managed, so there's zero operational overhead — no server to maintain. It's ideal for alarms, billing metrics, and AWS service integrations. The downside is cost at scale (custom metric + alarm pricing), limited PromQL-like querying, and vendor lock-in.

> Prometheus is open-source, pull-based (it scrapes your `/metrics` endpoint), stores time-series locally, and pairs naturally with Grafana for dashboards. It supports rich querying with PromQL.

> I used both because real production environments often have this split — AWS-native alarms for PagerDuty integration, and Prometheus/Grafana for the engineering team's dashboards. It also let me show I can work in a hybrid observability stack, not just AWS-only."

---

### Q5: "How does your Prometheus exporter work?"

**Answer:**
> "I used the `prometheus_client` Python library. It exposes an HTTP server on port 8000 at `/metrics`. I defined Gauge metrics — `sim_cpu_utilization_percent`, `sim_memory_used_percent`, etc. — and a background daemon thread updates them every 2 seconds using `psutil`.

> Prometheus is configured to scrape that endpoint at a set interval (e.g., 15 seconds). Grafana then queries Prometheus via PromQL — for example `sim_cpu_utilization_percent` — and renders the time series.

> The key design decision was running the exporter as a separate process from the simulator. That way even if the simulator crashes mid-scenario, the exporter keeps running and you can see the metric flat-line — which is itself a useful signal."

---

### Q6: "What did you learn from writing the runbooks?"

**Answer:**
> "The biggest lesson was that runbooks expose gaps in your monitoring setup. When I wrote the CPU runbook and walked through the triage steps, I realized I hadn't set up `sar` on the instance — so the diagnostic command I'd written wouldn't work. That sent me back to the Terraform `user_data` to install `sysstat`.

> Runbooks also forced me to define what 'resolved' actually means. For the CPU alarm, I specified: alarm must transition to `OK` state within 2 evaluation periods, and the `watch mpstat` command should show CPU consistently below 80%. Without writing that down, 'resolved' is ambiguous during an incident."

---

### Q7: "How would you scale this for a team environment?"

**Answer:**
> "A few things I'd add:
>
> 1. **Centralised alerting via PagerDuty** — SNS already supports PagerDuty webhooks; I'd route P1 alarms there and P3 to Slack only.
>
> 2. **Scenario parameterisation via config file** — instead of hardcoded thresholds, externalise them to a `scenarios.yaml` so different environments (staging vs. prod) can have different targets.
>
> 3. **Scheduled chaos drills** — a cron job or Step Functions state machine that runs the `--scenario all` workflow weekly in a staging environment, with automatic pass/fail reporting posted to Slack.
>
> 4. **Distributed scenarios** — extend to ECS/EKS by injecting failures into containers using tools like `chaos-mesh` or AWS Fault Injection Simulator (FIS)."

---

## 🔑 Key Technical Terms to Know Cold

| Term | One-sentence definition |
|------|------------------------|
| MTTR | Mean Time to Repair — avg time from alert to service restoration |
| `tc netem` | Linux kernel network emulator for injecting latency/packet loss |
| CloudWatch namespace | Logical container for a group of custom metrics |
| Prometheus scrape | Prometheus pulling `/metrics` from a target at a defined interval |
| Gauge (Prometheus) | Metric type that can go up and down (vs. Counter which only increases) |
| `TreatMissingData` | CloudWatch alarm behaviour when no data points arrive |
| EvaluationPeriods | Number of consecutive periods the threshold must be breached to trigger |
| PromQL | Prometheus query language (e.g. `rate(metric[5m])`) |
| `psutil` | Python library for accessing system/process information |
| IAM Instance Profile | Attaches an IAM role to an EC2 instance for AWS API access |
