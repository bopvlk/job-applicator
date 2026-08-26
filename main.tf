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

# 1. Додаємо наш публічний SSH ключ
resource "aws_key_pair" "deployer" {
  key_name   = "job-applicator-deploy-key"
  public_key = file("~/.ssh/job_applicator_key.pub")
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

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
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t3.micro"
  
  # 2. Прив'язуємо ключ до сервера
  key_name      = aws_key_pair.deployer.key_name 

  vpc_security_group_ids = [aws_security_group.web_sg.id]

  tags = {
    Name = "JobApplicator-Node"
  }
}

output "server_public_ip" {
  value       = aws_instance.app_server.public_ip
  description = "IP address of our new server"
}