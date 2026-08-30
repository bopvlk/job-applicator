terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "eu-central-1"
}

# 1. SSH key
resource "aws_key_pair" "deployer" {
  key_name   = "job-applicator-deploy-key"
  public_key = file("~/.ssh/job_applicator_key.pub")
}

# 2. Security Group
resource "aws_security_group" "web_sg" {
  name        = "job-applicator-sg"
  description = "Allow SSH and HTTP traffic"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "app_server" {
  ami           = "ami-0faab6bdbac9486fb"  # Ubuntu 22.04 LTS (eu-central-1)
  instance_type = "t3.micro"
  
  key_name      = aws_key_pair.deployer.key_name 
  vpc_security_group_ids = [aws_security_group.web_sg.id]

  user_data = <<-EOF
              #!/bin/bash
              apt update -y && apt install -y docker.io git
              systemctl enable --now docker
              usermod -aG docker ubuntu
              EOF

  tags = {
    Name = "JobApplicator-Node"
  }
}

output "server_public_ip" {
  value       = aws_instance.app_server.public_ip
  description = "IP address of our new server"
}

# 1. Створюємо IAM Role для читання SSM
resource "aws_iam_role" "ec2_ssm_role" {
  name = "job-applicator-ssm-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ssm_policy" {
  role       = aws_iam_role.ec2_ssm_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMReadOnlyAccess"
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "job-applicator-instance-profile"
  role = aws_iam_role.ec2_ssm_role.name
}