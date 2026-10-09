# AWS execution note — updated 9 October 2026, 20:42 UTC

The authorized experiment ceiling is **$2,000, from promotional credits only**. The authenticated quota is **16 G/VT vCPUs**, not 16 GPUs. A dedicated Chile benchmark g5.xlarge worker was launched at 18:05:33 UTC, adding 4 vCPUs and one A10G to the previously running 12 vCPUs. No quota increase was requested.

The authenticated Billing console, checked at 20:19 UTC, reports $4,293.82 estimated total remaining credits, including $4,118.50 from the main award expiring 31 October 2026. Eligible services include Amazon EC2 and AWS Data Transfer. These are delayed estimates, not a reserved allocation or settled invoice; other account usage shares the balance.

INSTANCE training continues on the pre-existing earthquake g5.xlarge instance i-0911a2d093e1e2a30 with one A10G. Resolution replication, instrument-factor ablations and all-record instrument training have completed. The matched future-growth comparison and four synthetic reproducibility probes are complete. The censored sequential comparison completed with a negative scientific result. The six deterministic affine-prefix controls finished successfully, followed by the reviewed proper-score grid at 20:41:24 UTC. The queue is capped at 37,600 seconds, with a 10,800-second sequential run limit and 3,600-second limits for each subsequent affine run. The original200GiB dataset volume remains mounted **read-only** at /data. Other pre-existing instances and disks are unchanged.

The new worker is **i-08b9781ed60d8497f**, named EEW-Chile-worker-20261009. It uses an official AWS PyTorch2.8 GPU image, an encrypted80GiB gp3 root volume with deletion on termination, IMDSv2 and no IAM role. Its task-owned security group allows SSH from the original earthquake instance's security group; the temporary public SSH rule was removed. No private SSH keys or repository credentials were copied. A separate temporary transfer key was generated on the original worker, accepted at the new worker through expiring EC2 Instance Connect, and removed after the single completed data-transfer session.

The current AWS Pricing API lists **$1.006/hour** for Linux shared On-Demand g5.xlarge in us-east-1. The worker has a verified operating-system shutdown scheduled for **11 October 2026, 07:28:52 UTC**, with EC2 shutdown behavior set to **stop**. Thirty-six running hours from the latest stop-timer rearm cost an estimated $36.216 in compute; a conservative $60 worker allowance includes the earlier pilots and incidental storage. The full baseline also has a 35-hour process limit. This is an estimate, not settled billing. Recovery checkpoints are available before any later extension within the existing authorized budget; rebooting requires rechecking the stop timer.

An attempted upgrade to g6e.xlarge was rejected twice for insufficient AWS capacity. The worker was restored to g5.xlarge and verified running at 19:10 UTC; no L40S training occurred. Its read-only data mount was restored and its automatic stop was rearmed. All four TRAIN-only pilots succeeded. The deterministic full baseline started at 19:30:04 UTC with 25 station-pretraining and 100 event-training epochs. Its first complete station epoch took 2,462.99 seconds (41.05 minutes), including internal calibration. Extending that rate across 25 station epochs suggests 17.10 hours before event training; the total remains a forecast, not a guaranteed bound. Checkpoints permit recovery if the process limit is reached.

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

At the AWS-listed gp3 capacity rate of $0.08/GB-month, this disk is approximately $8/month, prorated while retained. No extra IOPS, throughput, or subscription was purchased. [AWS pricing](https://aws.amazon.com/ebs/volume-types/). Snapshot **snap-0fd34ed08a1a2d675** was created at18:18:59UTC to transfer the checksum-verified Chile TRAIN/DEV caches to the new worker. The slow snapshot path was replaced by a completed private-network SSH transfer to the worker’s existing root disk. Both full-cache and metadata SHA256 values match the verified source. The files are exposed at /mnt/eew-data through a read-only bind mount, with about 22 GiB remaining writable. The snapshot was deleted and EC2 confirms it no longer exists; **no clone volume was created**. Only its brief storage lifetime may incur a small prorated charge. Exact incremental compute and storage charges have not settled, so no exact spend is claimed.

**Cleanup requirement:** preserve portable results and manifests, stop the new worker when idle, then remove only task-created worker, root, clone, scratch volume, snapshot and security group when no longer needed. Reconcile their lifecycle no later than30October2026, before the main credit expires. Do not delete pre-existing volumes or stop unrelated machines. Recheck credits before materially increasing resources or extending work beyond that date.

![Dedicated benchmark worker](aws_benchmark_worker.jpg)

![Dedicated disk attached](aws_research_volume.jpg)


At 20:16:43 UTC a reviewed TRAIN-only cache export began on the dedicated worker. The new worker's verified blank 250 GB instance SSD is mounted at `/mnt/eew-fast`; the original worker's unknown SSD remains untouched. The export is capped at one CPU, 3 GiB memory, 25,000,000 bytes/s of root-disk reads and three hours. It must preserve every float32 TRAIN waveform exactly and publish verified checksums before use. This disposable cache is not the sole location of any checkpoint or result. The separate flat-loader and explicit checkpoint-migration implementation passed ten CPU tests, including the actual final-batch sizes, and clean Codex review; real CUDA equivalence and migration remain pending. The live trainer is unchanged.
