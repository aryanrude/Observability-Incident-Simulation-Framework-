terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ── Variables ─────────────────────────────────────────────────────────────────
variable "aws_region"    { default = "ap-south-1" }
variable "instance_type" { default = "t3.micro" }
variable "key_name"      { description = "EC2 key pair name" }
variable "alert_email"   { description = "Email for CloudWatch alarm notifications" }

data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
}

# ── Networking ────────────────────────────────────────────────────────────────
resource "aws_vpc" "sim" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  tags = { Name = "observability-sim-vpc" }
}

resource "aws_subnet" "sim_public" {
  vpc_id                  = aws_vpc.sim.id
  cidr_block              = "10.0.1.0/24"
  map_public_ip_on_launch = true
  tags = { Name = "sim-public-subnet" }
}

resource "aws_internet_gateway" "sim" {
  vpc_id = aws_vpc.sim.id
  tags   = { Name = "sim-igw" }
}

resource "aws_route_table" "sim" {
  vpc_id = aws_vpc.sim.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.sim.id
  }
}

resource "aws_route_table_association" "sim" {
  subnet_id      = aws_subnet.sim_public.id
  route_table_id = aws_route_table.sim.id
}

resource "aws_security_group" "sim" {
  name        = "observability-sim-sg"
  description = "Allow SSH + Prometheus scrape"
  vpc_id      = aws_vpc.sim.id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # restrict to your IP in production
  }

  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"]  # internal Prometheus only
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ── IAM ───────────────────────────────────────────────────────────────────────
resource "aws_iam_role" "sim_ec2" {
  name = "observability-sim-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "cw_publish" {
  name = "cw-publish"
  role = aws_iam_role.sim_ec2.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["cloudwatch:PutMetricData", "cloudwatch:PutMetricAlarm",
                  "cloudwatch:DescribeAlarms"]
      Resource = "*"
    }]
  })
}

resource "aws_iam_instance_profile" "sim" {
  name = "observability-sim-profile"
  role = aws_iam_role.sim_ec2.name
}

# ── EC2 Instance ──────────────────────────────────────────────────────────────
resource "aws_instance" "sim" {
  ami                    = data.aws_ami.amazon_linux_2023.id
  instance_type          = var.instance_type
  key_name               = var.key_name
  subnet_id              = aws_subnet.sim_public.id
  vpc_security_group_ids = [aws_security_group.sim.id]
  iam_instance_profile   = aws_iam_instance_profile.sim.name

  user_data = <<-EOF
    #!/bin/bash
    dnf update -y
    dnf install -y python3-pip iproute-tc git stress-ng
    pip3 install boto3 psutil prometheus-client
    mkdir -p /opt/observability-sim
    echo "Bootstrap complete" > /var/log/sim-bootstrap.log
  EOF

  tags = { Name = "observability-sim-host", Project = "observability-framework" }
}

# ── SNS for Alarm Notifications ───────────────────────────────────────────────
resource "aws_sns_topic" "alerts" {
  name = "observability-sim-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# ── CloudWatch Log Group ──────────────────────────────────────────────────────
resource "aws_cloudwatch_log_group" "sim" {
  name              = "/observability-framework/simulation"
  retention_in_days = 7
}

# ── Outputs ───────────────────────────────────────────────────────────────────
output "instance_id"        { value = aws_instance.sim.id }
output "instance_public_ip" { value = aws_instance.sim.public_ip }
output "sns_topic_arn"      { value = aws_sns_topic.alerts.arn }
