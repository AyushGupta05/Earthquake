"""Work through a shared queue of train.py arms from any number of hosts without duplicates.

Before an arm starts, the host claims it with an S3 conditional write (If-None-Match: *) of
<prefix>/claims/<arm>; an arm whose claim already exists, or whose fold4.npz is already in
<prefix>/arms/<arm>/, is skipped. Finished arms (and their logs) are uploaded to <prefix>/arms/ and
<prefix>/logs/. The same queue can therefore be served by EC2 hosts and SageMaker containers at once.
A host that dies leaves its claim in place; delete the claim object to release the arm.

  TAILWORK_DIR=<cache> python claim_runner.py --queue sm_queues/queue_cwa.txt \
      --prefix s3://instance-earthquake-data/sm/cwa --gpu 0
"""
import argparse
import os
import shlex
import socket
import subprocess
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


def split(prefix):
    assert prefix.startswith('s3://')
    bucket, _, key = prefix[5:].partition('/')
    return bucket, key.rstrip('/')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--queue', required=True)
    ap.add_argument('--prefix', required=True)
    ap.add_argument('--gpu', default='0')
    ap.add_argument('--python', default=sys.executable)
    args = ap.parse_args()
    work = Path(os.environ['TAILWORK_DIR'])
    (work / 'logs').mkdir(parents=True, exist_ok=True)
    bucket, key = split(args.prefix)
    s3 = boto3.client('s3')
    here = Path(__file__).resolve().parent
    me = f'{socket.gethostname()} gpu{args.gpu}'
    lines = [l.strip() for l in Path(args.queue).read_text().splitlines() if l.strip() and not l.startswith('#')]
    for line in lines:
        parts = shlex.split(line)
        arm = parts[parts.index('--arm') + 1]
        try:
            s3.head_object(Bucket=bucket, Key=f'{key}/arms/{arm}/fold4.npz')
            continue
        except ClientError:
            pass
        try:
            s3.put_object(Bucket=bucket, Key=f'{key}/claims/{arm}', Body=f'{me} {time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}'.encode(),
                          IfNoneMatch='*')
        except ClientError as e:
            if e.response['Error']['Code'] in ('PreconditionFailed', 'ConditionalRequestConflict'):
                continue
            raise
        print(time.strftime('%H:%M:%S'), me, 'start', arm, flush=True)
        log = work / 'logs' / f'{arm}.log'
        env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(args.gpu))
        with open(log, 'w') as f:
            rc = subprocess.call([args.python, str(here / 'train.py')] + parts, stdout=f, stderr=subprocess.STDOUT, env=env, cwd=here)
        print(time.strftime('%H:%M:%S'), me, 'end', arm, 'rc', rc, flush=True)
        arm_dir = work / 'arms' / arm
        for p in sorted(arm_dir.glob('*')):
            s3.upload_file(str(p), bucket, f'{key}/arms/{arm}/{p.name}')
        s3.upload_file(str(log), bucket, f'{key}/logs/{arm}.log')


if __name__ == '__main__':
    main()
