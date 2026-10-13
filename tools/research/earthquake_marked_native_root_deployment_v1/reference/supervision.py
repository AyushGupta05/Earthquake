"""Inherited bounded stream supervisor; no SSH/provider/science imports."""
import hashlib,os,selectors,subprocess,time

def managed_process(args,timeout,popen=subprocess.Popen,clock=time.monotonic):
 buffers={k:bytearray()for k in('stdout','stderr')};hashes={k:hashlib.sha256()for k in buffers};counts={k:0 for k in buffers};caps={'stdout':65536,'stderr':131072};proc=None;selector=None;code=None;interrupted=False;failure=None
 try:
  start=clock();proc=popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE);selector=selectors.DefaultSelector()
  for k,pipe in(('stdout',proc.stdout),('stderr',proc.stderr)):os.set_blocking(pipe.fileno(),False);selector.register(pipe,selectors.EVENT_READ,k)
  while selector.get_map():
   if clock()-start>timeout:interrupted=True;proc.terminate();break
   for key,_ in selector.select(.1):
    b=os.read(key.fileobj.fileno(),65536)
    if not b:selector.unregister(key.fileobj);continue
    k=key.data;hashes[k].update(b);counts[k]+=len(b);buffers[k].extend(b[:max(0,caps[k]-len(buffers[k]))])
  try:code=proc.wait(timeout=5)
  except subprocess.TimeoutExpired:interrupted=True;proc.kill();code=proc.wait(timeout=5)
 except Exception as error:
  interrupted=True;failure=type(error).__name__
  if proc is not None:
   try:proc.terminate()
   except Exception:pass
   try:code=proc.wait(timeout=5)
   except Exception:
    try:proc.kill();code=proc.wait(timeout=5)
    except Exception:pass
 finally:
  if selector is not None:
   try:selector.close()
   except Exception:interrupted=True
  if proc is not None:
   for pipe in(proc.stdout,proc.stderr):
    try:pipe.close()
    except Exception:interrupted=True
 streams={k:dict(original_bytes=counts[k],original_sha256=hashes[k].hexdigest(),retained_bytes=len(buffers[k]),truncated=counts[k]>len(buffers[k]),complete_observation=not interrupted)for k in buffers}
 answer=dict(code=code,timeout=interrupted,raw={k:bytes(v)for k,v in buffers.items()},streams=streams)
 if failure is not None:answer['exception_type']=failure
 return answer

