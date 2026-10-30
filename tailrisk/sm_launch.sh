#!/bin/bash
# Launch a SageMaker training job that runs a queue of train.py arms with sm_run.sh, one lane per
# GPU (used when the EC2 G-instance quota is full; SageMaker training quotas are separate).
#
#   sm_launch.sh JOB INSTANCE_TYPE DATA_S3_PREFIX QUEUE_FILE "TAILWORK_MAXMAG=9.5,TAILWORK_MAXLOGR=3.0" [HOURS]
#
# DATA_S3_PREFIX may also be a comma-separated list: the first is channel `data` (the default
# work directory), and NAME=PREFIX entries become channel `data_NAME`, selected by queue lines
# starting with `@NAME ` (see sm_run.sh).
#
# ENTRY=sm_claim_run.sh serves a shared S3-claimed queue instead (claim_runner.py; set
# CLAIM_PREFIX=s3://... in the environment list).
# REGION (default us-east-1) picks the region; BUCKET must then be a bucket in that region and
# DATA a prefix in it (training channels must be in the job's region).
#
# Code: src.tar.gz built from the checkout (tailrisk/*.py, *.sh, train_std_full.npy) plus the
# queue, uploaded to s3://$BUCKET/sm/jobs/JOB/code/. Arms appear under
# s3://$BUCKET/sm/jobs/JOB/checkpoints/arms/ as they finish.
set -eu
JOB=$1; TYPE=$2; DATA=$3; QUEUE=$4; ENVS=${5:-}; HOURS=${6:-10}
REGION=${REGION:-us-east-1}
BUCKET=${BUCKET:-instance-earthquake-data}
ROLE=${SM_ROLE:-arn:aws:iam::936102779163:role/service-role/AmazonSageMakerAdminIAMExecutionRole}
IMAGE=763104351884.dkr.ecr.$REGION.amazonaws.com/pytorch-training:2.8.0-gpu-py312-cu129-ubuntu22.04-sagemaker-v1.9
P=s3://$BUCKET/sm/jobs/$JOB
HERE=$(cd "$(dirname "$0")" && pwd)
TMP=$(mktemp -d)
(cd "$HERE/.." && COPYFILE_DISABLE=1 tar -czf $TMP/src.tar.gz tailrisk/*.py tailrisk/*.sh train_std_full.npy)
cp "$QUEUE" $TMP/queue.txt
cp "$HERE/sm_run.sh" $TMP/sm_run.sh
cp "$HERE/sm_claim_run.sh" $TMP/sm_claim_run.sh
ENTRY=${ENTRY:-sm_run.sh}
aws s3 cp $TMP $P/code --recursive --only-show-errors --region $REGION
CHANNELS=$(python3 -c "
import json, sys
ch = [{'ChannelName': 'code', 'DataSource': {'S3DataSource': {'S3DataType': 'S3Prefix', 'S3Uri': sys.argv[1] + '/code/', 'S3DataDistributionType': 'FullyReplicated'}}}]
for i, d in enumerate(sys.argv[2].split(',')):
    name, uri = d.split('=', 1) if '=' in d else ('', d)
    ch.append({'ChannelName': 'data' + ('_' + name if name else ''), 'DataSource': {'S3DataSource': {'S3DataType': 'S3Prefix', 'S3Uri': uri, 'S3DataDistributionType': 'FullyReplicated'}}})
print(json.dumps(ch))" "$P" "$DATA")
ENVJSON=$(python3 -c "import json,sys; print(json.dumps(dict(kv.split('=',1) for kv in sys.argv[1].split(',') if kv)))" "$ENVS")
aws sagemaker create-training-job --region $REGION --training-job-name "$JOB" \
  --role-arn "$ROLE" \
  --algorithm-specification "{\"TrainingImage\":\"$IMAGE\",\"TrainingInputMode\":\"File\",\"ContainerEntrypoint\":[\"bash\",\"/opt/ml/input/data/code/$ENTRY\"]}" \
  --input-data-config "$CHANNELS" \
  --output-data-config "{\"S3OutputPath\":\"$P/output\"}" \
  --checkpoint-config "{\"S3Uri\":\"$P/checkpoints\",\"LocalPath\":\"/opt/ml/checkpoints\"}" \
  --resource-config "{\"InstanceType\":\"$TYPE\",\"InstanceCount\":1,\"VolumeSizeInGB\":100}" \
  --stopping-condition "{\"MaxRuntimeInSeconds\":$((HOURS * 3600))}" \
  --environment "$ENVJSON" \
  --tags Key=project,Value=tailwork --query TrainingJobArn --output text
rm -rf $TMP
