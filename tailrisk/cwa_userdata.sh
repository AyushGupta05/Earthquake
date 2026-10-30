#!/bin/bash
# EC2 user data for an extra GPU host (DLAMI PyTorch, Amazon Linux 2023) joining the CWA queue:
# fetch the code from S3, point .venv at the image's PyTorch environment, run cwa_host.sh.
sudo -u ec2-user bash <<'EOS'
set -e
cd /home/ec2-user
mkdir -p Earthquake && cd Earthquake
aws s3 cp s3://instance-earthquake-data/sm/code/tailrisk_src.tgz /tmp/src.tgz --only-show-errors
tar xzf /tmp/src.tgz
[ -e .venv ] || ln -s /opt/pytorch .venv
cd tailrisk
nohup setsid ./cwa_host.sh /home/ec2-user/cwa > /home/ec2-user/cwa_host.log 2>&1 < /dev/null &
EOS
