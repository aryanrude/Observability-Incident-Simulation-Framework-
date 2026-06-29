#!/usr/bin/env python3
"""
setup_cloudwatch_alarms.py
Creates CloudWatch Alarms for all simulated metrics.
Run once after deploying the EC2 instance.

Usage:
    python setup_cloudwatch_alarms.py --sns-arn arn:aws:sns:ap-south-1:123456789:alerts
"""

import argparse
import os
import boto3
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

AWS_REGION    = os.getenv("AWS_REGION", "ap-south-1")
NAMESPACE     = os.getenv("CW_NAMESPACE", "ObservabilityFramework")
INSTANCE_ID   = os.getenv("INSTANCE_ID", "i-0000000000000000")


ALARM_DEFINITIONS = [
    {
        "name":        "HighCPUUtilization",
        "metric":      "CpuUtilizationSimulated",
        "threshold":   85.0,
        "comparison":  "GreaterThanOrEqualToThreshold",
        "description": "CPU above 85% for 2 consecutive minutes — possible runaway process",
        "unit":        "Percent",
        "period":      60,
        "eval_periods": 2,
    },
    {
        "name":        "HighMemoryUtilization",
        "metric":      "MemoryUsedPercent",
        "threshold":   80.0,
        "comparison":  "GreaterThanOrEqualToThreshold",
        "description": "Memory above 80% — potential OOM risk",
        "unit":        "Percent",
        "period":      60,
        "eval_periods": 2,
    },
    {
        "name":        "HighLatencyP99",
        "metric":      "P99ResponseTimeMs",
        "threshold":   1000.0,
        "comparison":  "GreaterThanOrEqualToThreshold",
        "description": "P99 latency above 1000ms — degraded user experience",
        "unit":        "Milliseconds",
        "period":      60,
        "eval_periods": 1,
    },
    {
        "name":        "HighDiskWriteThroughput",
        "metric":      "DiskWriteMBps",
        "threshold":   100.0,
        "comparison":  "GreaterThanOrEqualToThreshold",
        "description": "Disk write throughput exceeding 100 MB/s — I/O saturation",
        "unit":        "Count",
        "period":      60,
        "eval_periods": 2,
    },
]


def create_alarms(sns_arn: str):
    cw = boto3.client("cloudwatch", region_name=AWS_REGION)
    dimensions = [{"Name": "InstanceId", "Value": INSTANCE_ID},
                  {"Name": "Environment", "Value": "simulation"}]

    for defn in ALARM_DEFINITIONS:
        log.info("Creating alarm: %s", defn["name"])
        cw.put_metric_alarm(
            AlarmName=defn["name"],
            AlarmDescription=defn["description"],
            Namespace=NAMESPACE,
            MetricName=defn["metric"],
            Dimensions=dimensions,
            Period=defn["period"],
            EvaluationPeriods=defn["eval_periods"],
            Threshold=defn["threshold"],
            ComparisonOperator=defn["comparison"],
            Statistic="Average",
            Unit=defn["unit"],
            TreatMissingData="notBreaching",
            AlarmActions=[sns_arn],
            OKActions=[sns_arn],
        )
        log.info("  ✔ %s created", defn["name"])


def main():
    parser = argparse.ArgumentParser(description="Setup CloudWatch Alarms")
    parser.add_argument("--sns-arn", required=True, help="SNS Topic ARN for notifications")
    args = parser.parse_args()
    create_alarms(args.sns_arn)
    log.info("All alarms created successfully.")


if __name__ == "__main__":
    main()
