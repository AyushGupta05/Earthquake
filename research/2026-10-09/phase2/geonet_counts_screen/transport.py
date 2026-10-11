"""Reviewed durable transport with a narrow frozen GET/POST request adapter."""
import copy
import hashlib
import json
import signal
import os
import urllib.request


def checkpoint(path,obj):
    temporary=path.with_name(path.name+'.temporary.'+str(os.getpid()))
    temporary.write_text(json.dumps(obj,indent=2,sort_keys=True,allow_nan=False)+'\n')
    temporary.replace(path)


def factory(lib,outer_started,request_specs):
    by_name={r['file']:r for r in request_specs}
    if len(by_name)!=len(request_specs):raise ValueError('duplicate frozen request file')
    # Native finally must not truncate the durable ledger before the wrapper can
    # reconcile it. This persistence hook leaves Fetcher/parser/UTC bytes unchanged.
    lib.dump=checkpoint
    class DeadlineSocket:
        def __init__(self,sock,owner):self.sock=sock;self.owner=owner
        def __getattr__(self,name):return getattr(self.sock,name)
        def recv_into(self,*args,**kwargs):
            now=self.owner.clock()
            if now>=self.owner.deadline:raise lib.LimitReached('time limit')
            remaining=min(self.owner.last_start+20,self.owner.deadline)-now
            if remaining<=0:raise TimeoutError('20-second whole-request deadline')
            # SocketIO may recv repeatedly inside chunk-size/CRLF parsing. Reduce
            # the socket timeout before EACH recv, keeping the absolute deadline
            # effective while soft signals are masked across read/persistence.
            self.sock.settimeout(remaining)
            return self.sock.recv_into(*args,**kwargs)
    class Response:
        def __init__(self,response,owner):
            self.response=response;self.owner=owner
            fp=getattr(response,'fp',None)
            if fp is not None:
                raw=getattr(fp,'raw',None);sock=getattr(raw,'_sock',None)
                if sock is None:raise ValueError('unexpected pinned HTTPResponse socket adapter')
                raw._sock=DeadlineSocket(sock,owner)
            elif not getattr(response,'isclosed',lambda:False)():raise ValueError('unexpected pinned HTTPResponse stream')
        @property
        def status(self):return self.response.status
        @property
        def headers(self):return self.response.headers
        def __enter__(self):self.response=self.response.__enter__();return self
        def __exit__(self,*args):return self.response.__exit__(*args)
        def read1(self,n):
            previous=signal.pthread_sigmask(signal.SIG_BLOCK,{signal.SIGTERM,signal.SIGALRM})
            try:
                chunk=self.response.read1(n)
                if chunk:
                    with self.owner.received_file.open('ab') as f:f.write(chunk)
                    self.owner.active_hash.update(chunk);self.owner.active_bytes+=len(chunk)
                    self.owner.persist()
                return chunk
            finally:signal.pthread_sigmask(signal.SIG_SETMASK,previous)

    class Opener:
        def __init__(self,owner):self.owner=owner;self.opener=urllib.request.build_opener(lib.NoRedirect())
        def open(self,request,timeout):
            spec=by_name[self.owner.active_name]
            if request.full_url!=spec['url']:raise ValueError('frozen request URL changed')
            entry=self.owner.log[-1]
            entry.update(start_from_outer_seconds=self.owner.last_start-outer_started,method=spec['method'])
            if spec['method']=='POST':
                body=spec['post_body'].encode('ascii')
                if hashlib.sha256(body).hexdigest()!=spec['post_body_sha256']:raise ValueError('frozen POST body changed')
                entry.update(post_body_sha256=spec['post_body_sha256'],post_body_bytes=len(body))
                request=urllib.request.Request(request.full_url,data=body,headers=dict(request.header_items()),method='POST')
                request.add_header('Content-Type','text/plain; charset=ascii')
            elif spec['method']!='GET':raise ValueError('unsupported frozen method')
            request.add_header('User-Agent','geonet-counts-screen-v1 bounded research')
            self.owner.received_file.touch(exist_ok=False)
            self.owner.persist()
            return Response(self.opener.open(request,timeout=timeout),self.owner)

    class DurableFetcher(lib.Fetcher):
        def __init__(self,root,**kwargs):
            super().__init__(root,**kwargs);self.opener=Opener(self)
        def persist(self):
            entries=copy.deepcopy(self.log);entry=entries[-1]
            entry.update(bytes=self.active_bytes,sha256=self.active_hash.hexdigest(),status='in_flight')
            checkpoint(self.root.parent/'requests.json',entries)
        def fetch(self,url,name,cap):
            self.active_name=name;self.active_bytes=0;self.active_hash=hashlib.sha256()
            self.received_file=self.root/(name+'.received');previous_attempts=len(self.log);previous_total=self.bytes
            try:return super().fetch(url,name,cap)
            finally:
                # An alarm can arrive after read1 returns but before native bytearray
                # accounting. Retain every delivered durable chunk in that case.
                if len(self.log)>previous_attempts and self.received_file.exists():
                    entry=self.log[-1];self.bytes=previous_total+self.active_bytes
                    entry.update(bytes=self.active_bytes,sha256=self.active_hash.hexdigest())
                    # Ledger first; until the rename, the recovery sidecar remains
                    # available if a hard kill interrupts this finalization.
                    checkpoint(self.root.parent/'requests.json',self.log)
                    self.received_file.replace(self.root/name)
                else:checkpoint(self.root.parent/'requests.json',self.log)
    return DurableFetcher
