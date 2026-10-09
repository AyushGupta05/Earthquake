# AWS execution note — updated 9 October 2026, 18:23 UTC

The authorized experiment ceiling is **$2,000, from promotional credits only**. The authenticated quota is **16 G/VT vCPUs**, not 16 GPUs. A dedicated Chile benchmark g5.xlarge worker was launched at18:05:33UTC, adding4vCPUs and one A10G to the previously running12vCPUs. No quota increase was requested.

The authenticated Billing console reports $4,312.64 estimated total remaining credits, including $4,137.32 from the main award expiring 31 October 2026. Eligible services include Amazon EC2 and AWS Data Transfer. These are delayed estimates, not a reserved allocation or settled invoice; other account usage shares the balance.

INSTANCE training continues on the pre-existing earthquake g5.xlarge instance i-0911a2d093e1e2a30 with one A10G. Each current resolution comparison has a2,400-second process limit; the replication queue has a22,000-second outer limit including waiting. Instrument factor comparisons are queued serially with3,600-second per-window limits. The original200GiB dataset volume remains mounted **read-only** at /data. Other pre-existing instances and disks are unchanged.

The new worker is **i-08b9781ed60d8497f**, named EEW-Chile-worker-20261009. It uses an official AWS PyTorch2.8 GPU image, an encrypted80GiB gp3 root volume with deletion on termination, IMDSv2 and no IAM role. Its task-owned security group allows SSH from the original earthquake instance's security group; the temporary public SSH rule was removed. No private SSH keys or repository credentials were copied.

The current AWS Pricing API lists **$1.006/hour** for Linux shared On-Demand g5.xlarge in us-east-1. The worker has a verified operating-system shutdown scheduled for **10October2026,18:06:09UTC**, with EC2 shutdown behavior set to **stop**. Its first24hours of compute therefore estimate$24.144; a conservative$40 initial resource allowance includes incidental storage. This is an estimate, not settled billing. Recovery checkpoints are available before any later approved extension within the existing budget; rebooting requires rechecking the stop timer.

One new research resource was created at 17:11:56 UTC:

| Property | Value |
|---|---|
| Name | EEW-Chile-research-20261009 |
| Volume ID | vol-01642a78ffb59234f |
| Type and capacity | gp3, 100 GiB |
| Performance | 3,000 IOPS, 125 MiB/s; included baseline |
| Availability zone | us-east-1d |
| Encryption | AWS-managed EBS key |
| Attachment | Existing earthquake instance, /dev/sdf API mapping |
| Host serial / device | vol01642a78ffb59234f / nvme3n1 |
| Mount | /mnt/eew-research, XFS, nosuid/nodev |
| Purpose | Public Chile train/development caches and checkpoints |

The disk was formatted only after matching the new volume's exact serial and size and checking for filesystem signatures. The pre-existing instance SSD contained unknown nonzero data and was left untouched.

At the AWS-listed gp3 capacity rate of $0.08/GB-month, this disk is approximately $8/month, prorated while retained. No extra IOPS, throughput, or subscription was purchased. [AWS pricing](https://aws.amazon.com/ebs/volume-types/). Snapshot **snap-0fd34ed08a1a2d675** was created at18:18:59UTC to transfer the checksum-verified Chile TRAIN/DEV caches to the new worker. Snapshot storage and its subsequent worker clone are additional prorated costs, recorded in the resource ledger. Exact incremental compute and storage charges have not settled, so no exact spend is claimed.

**Cleanup requirement:** preserve portable results and manifests, stop the new worker when idle, then remove only task-created worker, root, clone, scratch volume, snapshot and security group when no longer needed. Reconcile their lifecycle no later than30October2026, before the main credit expires. Do not delete pre-existing volumes or stop unrelated machines. Recheck credits before materially increasing resources or extending work beyond that date.

![Dedicated benchmark worker](aws_benchmark_worker.jpg)

![Dedicated disk attached](aws_research_volume.jpg)
