"""Fictional JSON production world. CPU-only; no semantic/keyword scoring."""
import copy
import hashlib
import json


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def need(condition,message):
    if not condition:
        raise ValueError(message)


OPS={
 'READ':{'ids':'nonempty list of available IDs'},'SEARCH':{'query':'string'},
 'EDIT_PROJECT':{'project':'project ID','content':'JSON object'},'PATCH_PROJECT':{'project':'project ID','patch':'JSON object'},
 'RESERVE':{'worker':'worker ID','project':'project ID','dependencies':'optional job/file IDs','content':'optional JSON object','kind':'optional output kind','purpose':'optional string','sources':'optional source IDs'},
 'CANCEL_JOB':{'job':'job ID'},'PRIVATE_REQUEST':{'request':'request catalog ID','text':'actual private request'},
 'REQUEST_REVIEW':{'files':'completed file IDs','claims':'optional JSON object'},
 'PUT_OBJECT':{'id':'new object ID','kind':'string','content':'JSON object','platform':'optional platform ID','files':'optional file IDs','review':'optional approved review ID','publish_at':'required future integer minute for kind=schedule'},
 'UPDATE_OBJECT':{'id':'object ID','content':'optional JSON object','files':'optional file IDs','review':'optional review ID','publish_at':'optional future integer minute'},
 'CANCEL_OBJECT':{'id':'object ID'},'VERIFY':{'id':'processed object ID'},
 'SEND':{'to':'recipient string','text':'actual private message','files':'optional completed file IDs','object':'optional object ID'},
 'NOTE':{'text':'string'},'WAIT':{'until':'optional future integer minute <=horizon; otherwise next event'},'FINISH':{'text':'final handoff'}
}


class World:
    def __init__(self,hidden):
        self.hidden=copy.deepcopy(hidden)
        self.case=hidden['case'];self.t=hidden.get('initial_time',0);self.horizon=hidden.get('horizon',180)
        self.done=False;self.steps=[];self.resources=copy.deepcopy(hidden.get('resources',{}))
        self.projects=copy.deepcopy(hidden.get('projects',{}));self.workers=copy.deepcopy(hidden.get('workers',{}))
        self.platforms=copy.deepcopy(hidden.get('platforms',{}));self.permissions=copy.deepcopy(hidden.get('permissions',[]))
        self.files=copy.deepcopy(hidden.get('initial_files',{}))
        for fid,f in self.files.items():
            f.setdefault('id',fid);f.setdefault('sha256',digest(f['content']));f.setdefault('kind','document')
        self.jobs=[];self.tasks=[];self.reviews={};self.inbox=[]
        self.messages=[];self.receipts=[];self.notes=[];self.fired=[];self.final_text='';self.objects={};self.object_history=[]
        for oid,obj in hidden.get('objects',{}).items():
            o=copy.deepcopy(obj);o.update(id=oid,version=1,created_at=self.t,updated_at=self.t,status='scheduled' if obj.get('kind')=='schedule' else 'ready',artifacts=self._files(obj.get('artifacts',[])))
            self.objects[oid]=o
        self._tick()

    def _notify(self,text,**data):
        self.inbox.append(dict(at=self.t,text=text,**copy.deepcopy(data)))

    def _job(self,jid):
        return next((j for j in self.jobs if j['id']==jid),None)

    def _file(self,fid):
        need(fid in self.files,'Expected an actual completed artifact ID.')
        return self.files[fid]

    def _files(self,ids):
        need(isinstance(ids,list),'files must be a list of completed artifact IDs.')
        return [copy.deepcopy(self._file(fid)) for fid in ids]

    def _input_files(self,job):
        out=[]
        for dep in job['dependencies']:
            if dep in self.files:out.append(self.files[dep]);continue
            j=self._job(dep)
            if not j or j['status']!='completed':return None
            out.append(self.files[j['file_id']])
        return out

    def _fits(self,worker,t):
        spec=self.workers[worker]
        return any(left<=t and t+spec['duration']<=right for left,right in spec['windows'])

    def _start_jobs(self):
        for worker in self.workers:
            if any(j['worker']==worker and j['status'] in ('running','discarding') for j in self.jobs):continue
            for job in self.jobs:
                if job['worker']!=worker or job['status']!='queued' or not self._fits(worker,self.t):continue
                inputs=self._input_files(job)
                if inputs is None:continue
                job.update(status='running',start=self.t,end=self.t+self.workers[worker]['duration'])
                job['snapshot']['inputs']=[dict(file_id=f['id'],sha256=f['sha256']) for f in inputs]
                self._notify('Reserved job started.',job_id=job['id'])
                break

    def _task(self,kind,delay,**data):
        task=dict(id='task-'+str(len(self.tasks)+1),kind=kind,at=self.t,due=self.t+delay,status='pending',**copy.deepcopy(data))
        self.tasks.append(task)
        return task

    def _receipt(self,kind,**data):
        r=dict(id='receipt-'+str(len(self.receipts)+1),kind=kind,at=self.t,**copy.deepcopy(data))
        self.receipts.append(r);return copy.deepcopy(r)

    def _conditions(self,conditions,claims=None):
        results=[]
        for cond in conditions:
            rid=cond['resource']
            value=self.projects.get(rid[8:]) if rid.startswith('project/') else self.resources.get(rid)
            for key in cond.get('path',[]):
                if isinstance(value,dict):value=value.get(key)
                elif isinstance(value,list) and isinstance(key,int) and 0<=key<len(value):value=value[key]
                else:value=None
            expected=cond.get('equals')
            ok=value==expected if 'equals' in cond else True
            if claims is not None:ok=ok and claims.get(cond.get('claim',cond.get('path',['value'])[-1]))==value
            results.append(dict(resource=cond['resource'],path=cond.get('path',[]),current_value=copy.deepcopy(value),matches=ok))
        return results

    def _tick(self):
        for ev in self.hidden.get('events',[]):
            if ev['id'] in self.fired or ev['at']>self.t:continue
            self.fired.append(ev['id'])
            if 'resource_id' in ev:self.resources[ev['resource_id']]=copy.deepcopy(ev['resource'])
            for item in ev.get('revoke',[]):self.permissions=[p for p in self.permissions if not (p['source']==item['source'] and p['purpose']==item['purpose'])]
            self.permissions.extend(copy.deepcopy(ev.get('grant',[])))
            self._notify(ev.get('body','New information is available.'),event_id=ev['id'],resource_id=ev.get('resource_id'))
        for job in self.jobs:
            if job['status'] not in ('running','discarding') or job['end']>self.t:continue
            if job['status']=='discarding':job['status']='cancelled';self._notify('Running cancellation finished; output discarded.',job_id=job['id']);continue
            job['status']='completed';fid='file-'+job['id'];job['file_id']=fid
            c=copy.deepcopy(job['snapshot']);self.files[fid]=dict(id=fid,kind=job['kind'],project=job['project'],completed_at=self.t,content=c,sha256=digest(c),media_label='FICTIONAL STRUCTURED JSON ARTIFACT')
            self._notify('Completed artifact is available.',job_id=job['id'],file_id=fid)
        for task in self.tasks:
            if task['status']!='pending' or task['due']>self.t:continue
            task.update(status='completed',completed_at=self.t)
            if task['kind']=='request':
                spec=self.hidden['requests'][task['request']];checks=self._conditions(spec.get('requires',[]))
                outcome=spec.get('outcome','accepted') if all(x['matches'] for x in checks) else 'declined'
                task.update(outcome=outcome,conditions=checks)
                if outcome=='accepted':self.permissions.extend(copy.deepcopy(spec.get('grants',[])))
                if outcome!='no_reply':
                    task['body']=spec.get('body','Request accepted.') if outcome=='accepted' else spec.get('decline_body','Request declined.')
                    self._notify(task['body'],task_id=task['id'],channel='private',outcome=outcome)
                self._receipt('request_resolution',task_id=task['id'],outcome=outcome,grants=spec.get('grants',[]) if outcome=='accepted' else [])
            elif task['kind']=='review':
                checks=self._conditions(self.hidden.get('review',{}).get('requires',[]),task['claims'])
                result=dict(id=task['review_id'],approved=all(x['matches'] for x in checks),at=self.t,hashes=task['hashes'],claims=task['claims'],conditions=checks)
                self.reviews[result['id']]=result
                self._notify('Artifact review completed.',review_id=result['id'],approved=result['approved'])
                self._receipt('review',review_id=result['id'],approved=result['approved'],hashes=result['hashes'],claims=result['claims'],conditions=result['conditions'])
            elif task['kind']=='process':
                obj=self.objects.get(task['object'])
                task['applied']=bool(obj and obj['version']==task['version'] and obj['status']!='cancelled')
                if task['applied']:
                    obj['status']='scheduled' if obj['kind']=='schedule' else 'ready';obj['processed_at']=self.t
                    self._notify('Platform processing completed.',object_id=obj['id'],version=obj['version'])
                    self._receipt('processing',object_id=obj['id'],version=obj['version'],hashes=[x['sha256'] for x in obj['artifacts']])
            elif task['kind']=='verify':
                obj=self.objects.get(task['object'])
                valid=bool(obj and obj['version']==task['version'] and obj['status'] not in ('cancelled','processing'))
                r=self._receipt('verification',object_id=task['object'],version=task['version'],valid_current=valid,snapshot=task['snapshot'],hashes=task['hashes'],rights_at_use=task['rights_at_use'])
                if valid:obj['verification']=r['id']
                self._notify('Platform verification completed.',receipt_id=r['id'],object_id=task['object'],valid_current=valid)
        for obj in list(self.objects.values()):
            if obj['kind']=='schedule' and obj['status']=='scheduled' and obj['publish_at']<=self.t:
                pid='published/'+obj['id']+'/'+str(obj['version']);post=copy.deepcopy(obj)
                post.update(id=pid,kind='post',status='ready',published_at=self.t,source_schedule=obj['id'])
                self.objects[pid]=post;obj.update(status='published',published_object=pid)
                self._receipt('publication',object_id=pid,snapshot=post)
                self._notify('Scheduled snapshot published.',object_id=pid)
        self._start_jobs()

    def _advance(self,end):
        while self.t<min(end,self.horizon):self.t+=1;self._tick()

    def _wake(self):
        times=[ev['at'] for ev in self.hidden.get('events',[]) if ev['id'] not in self.fired and ev['at']>self.t]
        times += [t['due'] for t in self.tasks if t['status']=='pending' and t['due']>self.t]
        times += [j['end'] for j in self.jobs if j['status'] in ('running','discarding') and j['end']>self.t]
        times += [o['publish_at'] for o in self.objects.values() if o['kind']=='schedule' and o['status']=='scheduled' and o['publish_at']>self.t]
        for j in self.jobs:
            if j['status']!='queued' or self._input_files(j) is None:continue
            if any(k['worker']==j['worker'] and k['status'] in ('running','discarding') for k in self.jobs):continue
            for left,right in self.workers[j['worker']]['windows']:
                t=max(left,self.t+1)
                if t+self.workers[j['worker']]['duration']<=right:times.append(t)
        return min(times+[self.horizon])

    def _read(self,rid):
        if rid=='state/grants':return {'title':'Current actual source/purpose grants','grants':copy.deepcopy(self.permissions)}
        for mapping in (self.resources,self.files,self.objects,self.reviews):
            if rid in mapping:return mapping[rid]
        if rid.startswith('project/') and rid[8:] in self.projects:return self.projects[rid[8:]]
        j=self._job(rid)
        if j:return j
        task=next((t for t in self.tasks if t['id']==rid),None)
        if task:
            out=copy.deepcopy(task)
            # No hidden future reply contents exist in pending task state.
            return out
        raise ValueError('Resource is not currently available; consult catalog and returned IDs.')

    def _object_payload(self,a,old=None):
        obj=copy.deepcopy(old or {})
        for field in ('kind','platform','content','review','publish_at'):
            if field in a:obj[field]=copy.deepcopy(a[field])
        need(isinstance(obj.get('kind'),str) and isinstance(obj.get('content'),dict),'Object requires kind string and content object.')
        if 'files' in a:obj['artifacts']=self._files(a['files'])
        obj.setdefault('artifacts',[])
        p=obj.get('platform');need(p is None or p in self.platforms,'Unknown platform.')
        spec=self.platforms.get(p,{})
        for rule in spec.get('requires',[]):
            need(self._requirement(rule),'Platform physical prerequisite is not yet satisfied; inspect its public requires rules and actual receipts.')
        allowed=spec.get('allowed_kinds',[])
        need(not allowed or all(f['kind'] in allowed for f in obj['artifacts']),'Platform does not support this artifact kind; see platform allowed_kinds.')
        if spec.get('requires_review'):
            review=self.reviews.get(obj.get('review'))
            need(review and review['approved'] and review['hashes']==[f['sha256'] for f in obj['artifacts']],'Platform requires approved review for this exact ordered artifact hash list.')
        if spec.get('requires_permissions'):
            need(isinstance(spec.get('purpose'),str),'Permission-gated platform must declare its actual purpose.')
            need(self._has_rights(obj['artifacts'],spec['purpose']),'Platform requires current permissions for its actual destination purpose; inspect grants and artifacts.')
        if obj['kind']=='schedule':need(isinstance(obj.get('publish_at'),int) and obj['publish_at']>self.t,'Schedule publish_at must be a future integer minute.')
        return obj

    def _requirement(self,rule):
        kind=rule['kind']
        if kind=='grant':
            return any(p['source']==rule['source'] and p['purpose']==rule['purpose'] for p in self.permissions)
        if kind=='object':
            obj=self.objects.get(rule['id'])
            if not obj:return False
            statuses=rule.get('status')
            if isinstance(statuses,str):statuses=[statuses]
            if statuses and obj['status'] not in statuses:return False
            if rule.get('verified') and not obj.get('verification'):return False
            return True
        if kind=='receipt':
            for r in self.receipts:
                if r['kind']!=rule['receipt_kind']:continue
                if 'object_id' in rule and r.get('object_id')!=rule['object_id']:continue
                if rule.get('current_version'):
                    obj=self.objects.get(r.get('object_id'))
                    if not obj or r.get('version')!=obj['version'] or not r.get('valid_current',True):continue
                return True
            return False
        return False

    def _has_rights(self,files,purpose=None):
        def check_content(c):
            return all(any(p['source']==s and p['purpose']==(purpose if purpose is not None else c.get('purpose')) for p in self.permissions) for s in c.get('sources',[])) and all(f['file_id'] in self.files and self.files[f['file_id']]['sha256']==f['sha256'] and check_content(self.files[f['file_id']]['content']) for f in c.get('inputs',[]))
        return all(check_content(f['content']) for f in files)

    def _store_object(self,obj,is_update=False):
        obj['version']=obj.get('version',0)+1;obj.setdefault('created_at',self.t)
        obj.update(updated_at=self.t,status='processing',rights_at_use=copy.deepcopy(self.permissions));obj.pop('verification',None)
        self.objects[obj['id']]=obj
        delay=self.platforms.get(obj.get('platform'),{}).get('process_minutes',0)
        if delay:self._task('process',delay,object=obj['id'],version=obj['version'])
        else:obj['status']='scheduled' if obj['kind']=='schedule' else 'ready';obj['processed_at']=self.t
        self.object_history.append(dict(at=self.t,operation='update' if is_update else 'create',snapshot=copy.deepcopy(obj)))
        return copy.deepcopy(obj)

    def _execute(self,a):
        op=a['op']
        if op=='READ':
            ids=a.get('ids');need(isinstance(ids,list) and bool(ids),'READ requires a nonempty IDs list.')
            return dict(resources={rid:copy.deepcopy(self._read(rid)) for rid in ids})
        if op=='SEARCH':
            q=a.get('query');need(isinstance(q,str) and q.strip(),'Nonempty query required.')
            return dict(matches=[dict(id=rid,title=r.get('title',rid),kind=r.get('kind','resource')) for rid,r in self.resources.items() if q.casefold() in json.dumps(r,ensure_ascii=False).casefold()])
        if op in ('EDIT_PROJECT','PATCH_PROJECT'):
            p=a.get('project');need(p in self.projects,'Unknown project ID.')
            c=a.get('content') if op=='EDIT_PROJECT' else a.get('patch');need(isinstance(c,dict),'Provide actual JSON document/patch.')
            if op=='EDIT_PROJECT':self.projects[p]=copy.deepcopy(c)
            else:self.projects[p].update(copy.deepcopy(c))
            return dict(project=p,sha256=digest(self.projects[p]))
        if op=='RESERVE':
            worker=a.get('worker');p=a.get('project');need(worker in self.workers and p in self.projects,'Unknown worker or project ID.')
            deps=a.get('dependencies',[]);need(isinstance(deps,list) and all(d in self.files or self._job(d) for d in deps),'Dependencies must name existing file or reserved job IDs.')
            content=a.get('content',self.projects[p]);need(isinstance(content,dict),'Actual JSON content required.')
            sources=a.get('sources',[]);need(isinstance(sources,list) and all(isinstance(s,str) for s in sources),'sources must be source IDs list.')
            j=dict(id='job-'+str(len(self.jobs)+1),worker=worker,project=p,status='queued',reserved_at=self.t,dependencies=copy.deepcopy(deps),kind=a.get('kind',self.workers[worker].get('output_kind','document')),snapshot=dict(document=copy.deepcopy(content),inputs=[],sources=copy.deepcopy(sources),purpose=a.get('purpose')))
            self.jobs.append(j);self._start_jobs();return copy.deepcopy(j)
        if op=='CANCEL_JOB':
            j=self._job(a.get('job'));need(j and j['status'] in ('queued','running'),'Only queued or running jobs may be cancelled.')
            j['status']='cancelled' if j['status']=='queued' else 'discarding';j['cancel_requested_at']=self.t
            return copy.deepcopy(j)
        if op=='PRIVATE_REQUEST':
            rid=a.get('request');need(rid in self.hidden.get('requests',{}),'Unknown request catalog ID.')
            need(isinstance(a.get('text'),str) and a['text'].strip(),'Actual private request text required.')
            spec=self.hidden['requests'][rid]
            self.messages.append(dict(id='message-'+str(len(self.messages)+1),at=self.t,to=spec['to'],text=a['text'],kind='request',request=rid))
            task=self._task('request',spec['delay'],request=rid)
            return dict(task=copy.deepcopy(task),message_id=self.messages[-1]['id'])
        if op=='REQUEST_REVIEW':
            fs=self._files(a.get('files',[]));need(bool(fs),'Review needs actual artifacts.')
            claims=a.get('claims',{});need(isinstance(claims,dict),'claims must be JSON object.')
            rid='review-'+str(sum(t['kind']=='review' for t in self.tasks)+1)
            task=self._task('review',self.hidden.get('review',{}).get('delay',1),review_id=rid,hashes=[f['sha256'] for f in fs],files=[f['id'] for f in fs],claims=claims)
            return dict(review_id=rid,task=copy.deepcopy(task))
        if op in ('PUT_OBJECT','UPDATE_OBJECT'):
            oid=a.get('id');need(isinstance(oid,str) and oid.strip(),'Object id required.')
            if op=='PUT_OBJECT':need(oid not in self.objects,'Object ID already exists.');old=None
            else:
                need(oid in self.objects,'Unknown object ID.');old=self.objects[oid]
            obj=self._object_payload(a,old);obj['id']=oid
            return dict(object=self._store_object(obj,op=='UPDATE_OBJECT'))
        if op=='CANCEL_OBJECT':
            oid=a.get('id');need(oid in self.objects,'Unknown object ID.')
            obj=self.objects[oid];obj.update(status='cancelled',cancelled_at=self.t,version=obj['version']+1);obj.pop('verification',None)
            self.object_history.append(dict(at=self.t,operation='cancel',snapshot=copy.deepcopy(obj)))
            return dict(object=copy.deepcopy(obj))
        if op=='VERIFY':
            oid=a.get('id');need(oid in self.objects,'Unknown object ID.');obj=self.objects[oid]
            need(obj['status'] not in ('processing','cancelled'),'Object must finish processing and be active before verification.')
            delay=self.platforms.get(obj.get('platform'),{}).get('verify_minutes',0)
            data=dict(object=oid,version=obj['version'],snapshot=copy.deepcopy(obj),hashes=[f['sha256'] for f in obj['artifacts']],rights_at_use=copy.deepcopy(self.permissions))
            if delay:return dict(task=copy.deepcopy(self._task('verify',delay,**data)))
            r=self._receipt('verification',object_id=oid,version=obj['version'],valid_current=True,snapshot=data['snapshot'],hashes=data['hashes'],rights_at_use=data['rights_at_use']);obj['verification']=r['id'];return dict(receipt=r)
        if op=='SEND':
            need(isinstance(a.get('to'),str) and isinstance(a.get('text'),str),'Recipient and actual text required.')
            addressed_to=a['to'];recipient=addressed_to
            communication=self.hidden.get('communication',{})
            routes=communication.get('recipients')
            if routes is not None:
                matches=[canonical for canonical,aliases in routes.items() if addressed_to==canonical or addressed_to in aliases]
                need(len(matches)==1,'Unknown or ambiguous private recipient; inspect protocol.communication.recipients and its public aliases.')
                recipient=matches[0]
            fs=self._files(a.get('files',[]));oid=a.get('object');need(oid is None or oid in self.objects,'Unknown attached object ID.')
            m=dict(id='message-'+str(len(self.messages)+1),at=self.t,to=recipient,text=a['text'],artifacts=fs,object_snapshot=copy.deepcopy(self.objects.get(oid)),rights_at_use=copy.deepcopy(self.permissions))
            if routes is not None:m['addressed_to']=addressed_to
            self.messages.append(m);return dict(message=copy.deepcopy(m))
        if op=='NOTE':
            need(isinstance(a.get('text'),str),'Actual note text required.');self.notes.append(dict(at=self.t,text=a['text']));return dict(saved=True)
        if op=='FINISH':
            need(isinstance(a.get('text'),str),'Final handoff text required.');self.final_text=a['text'];self.done=True;return dict(closed=True)
        raise ValueError('Unsupported operation; inspect protocol.operations.')

    def observe(self):
        requests={rid:{k:copy.deepcopy(v) for k,v in spec.items() if k in ('to','delay','requires')} for rid,spec in self.hidden.get('requests',{}).items()}
        return dict(case=self.case,brief=self.hidden['brief'],clock=self.t,horizon=self.horizon,done=self.done,
          protocol=dict(schema='coupled10-api-v1',operations=copy.deepcopy(OPS),time='Ordinary actions advance 1 minute, fire due events, then commit. Rejected actions cost 1 minute. WAIT jumps to next event/start/completion or explicit until. FINISH does not drain pending work. Actions commit at horizon, then close.',job_statuses=['queued','running','discarding','completed','cancelled'],object_statuses=['processing','ready','scheduled','published','cancelled'],request_outcomes=['accepted','declined','no_reply'],review=copy.deepcopy(self.hidden.get('review',{'delay':1,'requires':[]})),artifact_format={'content':{'document':'reservation document snapshot','inputs':'immutable input artifact snapshots at start','sources':'declared source IDs','purpose':'declared purpose'}},semantics='All actual arbitrary content is accepted subject to physical/API checks. Tool success is not semantic/rubric success.',communication=copy.deepcopy(self.hidden.get('communication',{}))),
          catalog=[dict(id='state/grants',title='Current actual source/purpose grants',kind='grant_register')]+[dict(id=rid,title=r.get('title',rid),kind=r.get('kind','resource')) for rid,r in self.resources.items()],workers=copy.deepcopy(self.workers),platforms=copy.deepcopy(self.platforms),projects=[dict(id=p,read_id='project/'+p) for p in self.projects],objects=copy.deepcopy(self.objects),jobs=copy.deepcopy(self.jobs),available_files=[dict(id=f,kind=v['kind'],project=v.get('project'),sha256=v['sha256']) for f,v in self.files.items()],requests=requests,reviews=copy.deepcopy(self.reviews),inbox=copy.deepcopy(self.inbox))

    def apply(self,action):
        need(not self.done,'World is closed.')
        before=self.observe();a=copy.deepcopy(action)
        if isinstance(a,dict) and a.get('op')=='WAIT':
            try:
                target=a.get('until',self._wake());need(isinstance(target,int) and self.t<target<=self.horizon,'WAIT until must be future integer minute <=horizon.')
                self._advance(target);result=dict(ok=True,waited_until=self.t)
            except (ValueError,TypeError,KeyError) as exc:
                self._advance(self.t+1);result=dict(ok=False,rejected=True,error=str(exc))
        else:
            self._advance(self.t+1)
            try:
                need(isinstance(a,dict) and a.get('op') in OPS,'Action must be object with supported op; see protocol.operations.')
                result=dict(ok=True,**self._execute(a))
            except (ValueError,TypeError,KeyError) as exc:result=dict(ok=False,rejected=True,error=str(exc))
        if self.t>=self.horizon:self.done=True
        result['at']=self.t
        self.steps.append(dict(index=len(self.steps)+1,observation=before,action=a,result=copy.deepcopy(result),next_observation=self.observe()))
        return result

    def state(self):
        return dict(clock=self.t,done=self.done,resources=copy.deepcopy(self.resources),projects=copy.deepcopy(self.projects),jobs=copy.deepcopy(self.jobs),files=copy.deepcopy(self.files),objects=copy.deepcopy(self.objects),object_history=copy.deepcopy(self.object_history),permissions=copy.deepcopy(self.permissions),tasks=copy.deepcopy(self.tasks),reviews=copy.deepcopy(self.reviews),messages=copy.deepcopy(self.messages),receipts=copy.deepcopy(self.receipts),inbox=copy.deepcopy(self.inbox),notes=copy.deepcopy(self.notes),fired=copy.deepcopy(self.fired),final_text=self.final_text)

    def record(self):
        return dict(case=self.case,schema='coupled10-record-v1',input_sha256=digest(self.hidden),candidate_model='unknown',steps=copy.deepcopy(self.steps),final_state=self.state())


def replay_actions(hidden,actions):
    w=World(hidden)
    for action in actions:w.apply(action)
    return w.record()


def replay(hidden,record_or_actions):
    if isinstance(record_or_actions,list):return replay_actions(hidden,record_or_actions)
    record=record_or_actions
    w=World(hidden);matches=record.get('input_sha256')==digest(hidden)
    details=[]
    for index,row in enumerate(record['steps']):
        before=w.observe()
        try:result=w.apply(copy.deepcopy(row['action']))
        except (ValueError,TypeError,KeyError) as exc:
            return dict(matches=False,steps=index,clock=w.t,done=w.done,error=str(exc))
        checks=dict(observation=before==row['observation'],result=result==row['result'],next_observation=w.observe()==row['next_observation'])
        details.append(dict(index=index+1,checks=checks));matches=matches and all(checks.values())
    exact=w.record()==record
    return dict(matches=bool(matches and exact),steps=len(record['steps']),clock=w.t,done=w.done,exact_record=exact,checks=details)


def assess(hidden,record):
    s=record['final_state']
    return dict(case=hidden['case'],clock=s['clock'],receipt_inventory=copy.deepcopy(s['receipts']),semantic_review_required=True,not_a_model_score=True)


def controller_cutoff_snapshot(hidden,record,cutoff):
    """Controller-only exact actual state within a recorded run, without future drain.

    An event inside a long WAIT is replayed up to cutoff. Actions committing after
    cutoff are not applied. A run stopped before cutoff remains stopped.
    """
    need(isinstance(cutoff,int) and cutoff>=hidden.get('initial_time',0),'Invalid cutoff minute.')
    w=World(hidden);boundary=min(cutoff,record['final_state']['clock'])
    for row in record['steps']:
        commit=row['next_observation']['clock']
        if commit>boundary:
            w._advance(boundary)
            break
        w.apply(copy.deepcopy(row['action']))
        if w.done or w.t>=boundary:break
    return dict(requested_cutoff=cutoff,actual_state_at=w.t,run_stopped_before_cutoff=record['final_state']['clock']<cutoff,state=w.state())


def artifact_provenance(state,file_id):
    """Controller-only factual DAG walk; no inferred rights or semantic verdict."""
    found={}
    def visit(fid,expected=None):
        f=state['files'][fid]
        need(expected is None or f['sha256']==expected,'Immutable input SHA mismatch.')
        if fid in found:return
        found[fid]=dict(id=fid,sha256=f['sha256'],kind=f['kind'],project=f.get('project'),sources=copy.deepcopy(f['content'].get('sources',[])),declared_purpose=f['content'].get('purpose'))
        for dep in f['content'].get('inputs',[]):visit(dep['file_id'],dep['sha256'])
    visit(file_id)
    return list(found.values())
