"""CPU protocol regressions; constructed routes, not model or semantic scores."""
import copy
import importlib.util
from pathlib import Path
import unittest

P=Path(__file__).resolve().parents[1]
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
R=module(P/'runtime/runtime.py','r')
H=module(P/'authoring/runtime_helper.py','h')

class RuntimeProtocolTests(unittest.TestCase):
    def world(self):return R.World(H.sample_world())
    def act(self,w,op,**data):
        r=w.apply(dict(op=op,**data));self.assertTrue(r['ok'],r);return r

    def file(self,w,project='pack',worker='editor',**kwargs):
        j=self.act(w,'RESERVE',project=project,worker=worker,**kwargs)
        while w._job(j['id'])['status']!='completed':self.act(w,'WAIT')
        return 'file-'+j['id']

    def test_sample_helper_and_replay(self):
        actions=[dict(op='READ',ids=['source/plan']),dict(op='RESERVE',project='pack',worker='editor'),dict(op='RESERVE',project='pack',worker='accessibility',dependencies=['job-1']),dict(op='WAIT'),dict(op='WAIT'),dict(op='FINISH',text='Actual pack and captions are complete.')]
        rec=H.run_actions(H.sample_world(),actions)
        self.assertEqual(rec,R.replay(H.sample_world(),actions));self.assertTrue(rec['final_state']['done'])
        self.assertEqual(rec['candidate_model'],'unknown')

    def test_read_discovery_and_projection(self):
        w=self.world();obs=w.observe();self.assertNotIn('permissions',obs)
        self.assertNotIn('outcome',obs['requests']['owner']);self.assertNotIn('grants',obs['requests']['owner'])
        self.assertNotIn('outcome',w.record()['final_state']['tasks'])
        ids=[x['id'] for x in obs['catalog']];r=self.act(w,'READ',ids=ids)
        self.assertEqual(len(r['resources']),len(ids));self.assertEqual(w.t,1)
        r['resources']['source/plan']['fields']['demo_time']='bad';self.assertEqual(w.resources['source/plan']['fields']['demo_time'],'17:00')

    def test_event_before_action_commit_and_reject_cost(self):
        h=H.sample_world();h['events']=[dict(id='new',at=1,resource_id='source/plan',resource=H.resource('New plan','New plan',{'demo_time':'18:00'}),body='New plan')]
        w=R.World(h);r=self.act(w,'READ',ids=['source/plan']);self.assertEqual(r['resources']['source/plan']['fields']['demo_time'],'18:00');self.assertEqual(r['at'],1)
        bad=w.apply(dict(op='READ',ids=['missing']));self.assertFalse(bad['ok']);self.assertEqual(w.t,2)
        self.assertEqual(w.steps[-1]['next_observation']['clock'],2)

    def test_reservation_snapshot_and_input_hashes(self):
        w=self.world();self.act(w,'RESERVE',worker='editor',project='pack');self.act(w,'PATCH_PROJECT',project='pack',patch={'title':'Changed'})
        self.act(w,'RESERVE',worker='accessibility',project='pack',dependencies=['job-1']);self.act(w,'WAIT');self.act(w,'WAIT')
        first=w.files['file-job-1'];second=w.files['file-job-2']
        self.assertEqual(first['content']['document']['title'],'Workshop');self.assertEqual(second['content']['document']['title'],'Changed')
        self.assertEqual(second['content']['inputs'][0]['sha256'],first['sha256'])
        self.assertEqual(first['sha256'],R.digest(first['content']))

    def test_unready_queue_does_not_block_and_workers_serial(self):
        h=H.sample_world();h['workers']['editor']['duration']=10
        w=R.World(h);self.act(w,'RESERVE',worker='editor',project='pack')
        self.act(w,'RESERVE',worker='accessibility',project='pack',dependencies=['job-1'])
        self.act(w,'RESERVE',worker='accessibility',project='notice')
        self.act(w,'WAIT');self.assertEqual(w._job('job-3')['status'],'running');self.assertEqual(w._job('job-2')['status'],'queued')
        self.assertEqual(w._job('job-3')['start'],5)
        while w._job('job-2')['status']!='completed':self.act(w,'WAIT')
        self.assertGreaterEqual(w._job('job-2')['start'],w._job('job-1')['end'])

    def test_windows_and_running_cancel_occupies_slot(self):
        h=H.sample_world();h['workers']['editor']=H.worker(5,[[5,12],[20,30]],'media')
        w=R.World(h);self.act(w,'RESERVE',worker='editor',project='pack');self.act(w,'WAIT');self.assertEqual(w.t,5)
        self.act(w,'CANCEL_JOB',job='job-1');self.act(w,'RESERVE',worker='editor',project='pack')
        self.assertEqual(w._job('job-1')['status'],'discarding');self.assertEqual(w._job('job-2')['status'],'queued')
        self.act(w,'WAIT');self.assertEqual(w.t,10);self.assertEqual(w._job('job-1')['status'],'cancelled')
        self.act(w,'WAIT');self.assertEqual(w.t,20);self.assertEqual(w._job('job-2')['status'],'running');self.assertNotIn('file-job-1',w.files)

    def test_permission_reply_delay_and_local_revocation(self):
        h=H.sample_world();h['permissions'].append(dict(source='guest',purpose='archive',terms='Archive only'))
        h['events']=[dict(id='withdraw',at=7,revoke=[dict(source='guest',purpose='workshop')],body='Workshop permission withdrawn; archive remains.')]
        w=R.World(h);r=self.act(w,'PRIVATE_REQUEST',request='owner',text='May we use the image for our workshop with museum credit?')
        self.assertFalse(any(p['source']=='guest' and p['purpose']=='workshop' for p in w.permissions));self.assertEqual(r['task']['due'],5)
        self.act(w,'WAIT');self.assertEqual(w.t,5);self.assertTrue(any(p['source']=='guest' and p['purpose']=='workshop' for p in w.permissions))
        self.act(w,'WAIT');self.assertEqual(w.t,7);self.assertFalse(any(p['source']=='guest' and p['purpose']=='workshop' for p in w.permissions));self.assertTrue(any(p['source']=='guest' and p['purpose']=='archive' for p in w.permissions))

    def test_decline_and_no_reply_never_grant(self):
        for outcome in ('declined','no_reply'):
            h=H.sample_world();h['requests']['owner']['outcome']=outcome
            w=R.World(h);self.act(w,'PRIVATE_REQUEST',request='owner',text='Please consider a workshop licence.');self.act(w,'WAIT')
            self.assertFalse(any(p['source']=='guest' for p in w.permissions));self.assertEqual(w.tasks[0]['outcome'],outcome)
            if outcome=='no_reply':self.assertFalse(w.inbox)

    def test_review_bound_to_exact_hashes(self):
        h=H.sample_world();h['platforms']['venue']['requires_review']=True
        w=R.World(h);f=self.file(w);r=self.act(w,'REQUEST_REVIEW',files=[f],claims={'demo_time':'17:00'})
        bad=w.apply(dict(op='PUT_OBJECT',id='copy',kind='upload',platform='venue',content={},files=[f],review=r['review_id']));self.assertFalse(bad['ok'])
        self.act(w,'WAIT');self.assertTrue(w.reviews[r['review_id']]['approved'])
        self.act(w,'PUT_OBJECT',id='copy',kind='upload',platform='venue',content={},files=[f],review=r['review_id'])
        f2=self.file(w);bad=w.apply(dict(op='UPDATE_OBJECT',id='copy',files=[f2],review=r['review_id']))
        # Identical documents deliberately produce identical hashes and approval may transfer.
        self.assertTrue(bad['ok'])
        self.act(w,'PATCH_PROJECT',project='pack',patch={'title':'different'})
        f3=self.file(w);bad=w.apply(dict(op='UPDATE_OBJECT',id='copy',files=[f3],review=r['review_id']));self.assertFalse(bad['ok'])

    def test_processing_actual_verify_and_stale_receipt(self):
        w=self.world();f=self.file(w)
        self.act(w,'PUT_OBJECT',id='copy',kind='upload',platform='venue',content={'note':'actual snapshot'},files=[f])
        bad=w.apply(dict(op='VERIFY',id='copy'));self.assertFalse(bad['ok'])
        self.act(w,'WAIT');r=self.act(w,'VERIFY',id='copy');self.assertIn('task',r);self.assertNotIn('verification',w.objects['copy'])
        self.act(w,'UPDATE_OBJECT',id='copy',content={'note':'new version'})
        self.act(w,'WAIT');self.assertFalse([r for r in w.receipts if r['kind']=='verification'][-1]['valid_current'])
        self.assertNotIn('verification',w.objects['copy'])

    def test_independent_copies_schedule_and_private_snapshots(self):
        w=self.world();f=self.file(w)
        self.act(w,'PUT_OBJECT',id='held',kind='held-copy',content={'text':'first'},files=[f])
        self.act(w,'PUT_OBJECT',id='reminder',kind='schedule',publish_at=20,content={'text':'old saved reminder'},files=[f])
        self.act(w,'SEND',to='private:owner',text='Here is your saved preview.',object='held',files=[f])
        self.act(w,'UPDATE_OBJECT',id='held',content={'text':'corrected'})
        self.assertEqual(w.messages[-1]['object_snapshot']['content']['text'],'first')
        self.assertEqual(w.objects['reminder']['content']['text'],'old saved reminder')
        self.act(w,'WAIT',until=20);self.assertEqual(w.objects['published/reminder/1']['content']['text'],'old saved reminder')
        self.act(w,'CANCEL_OBJECT',id='reminder');self.assertIn('published/reminder/1',w.objects)

    def test_physical_stage_rules(self):
        h=H.sample_world();h['platforms']['release']=H.platform(requires=[{'kind':'object','id':'inspection','status':'ready','verified':True},{'kind':'grant','source':'house','purpose':'workshop'},{'kind':'receipt','receipt_kind':'verification','object_id':'inspection','current_version':True}])
        w=R.World(h);bad=w.apply(dict(op='PUT_OBJECT',id='release',kind='transfer',platform='release',content={}))
        self.assertFalse(bad['ok']);self.act(w,'PUT_OBJECT',id='inspection',kind='inspection',content={});self.act(w,'VERIFY',id='inspection')
        self.act(w,'PUT_OBJECT',id='release',kind='transfer',platform='release',content={})
        self.act(w,'UPDATE_OBJECT',id='inspection',content={'new':'inspection'})
        bad=w.apply(dict(op='PUT_OBJECT',id='release-2',kind='transfer',platform='release',content={}));self.assertFalse(bad['ok'])

    def test_finish_does_not_drain_and_horizon_boundary(self):
        w=self.world();self.act(w,'RESERVE',worker='editor',project='pack');self.act(w,'FINISH',text='Editor is still running; not a completed delivery.')
        self.assertEqual(w.t,2);self.assertFalse(w.files)
        with self.assertRaises(ValueError):w.apply(dict(op='WAIT'))
        h=H.sample_world();h['horizon']=1;w=R.World(h);self.act(w,'NOTE',text='Committed at endpoint.');self.assertTrue(w.done);self.assertEqual(w.notes[0]['at'],1)

    def test_dynamic_review_project_condition_and_exact_replay(self):
        h=H.sample_world();h['review']['requires'][0].pop('equals')
        h['requests']['owner']['requires']=[dict(resource='project/notice',path=['ready'],equals=True)]
        w=R.World(h);self.act(w,'PRIVATE_REQUEST',request='owner',text='Please grant workshop rights.')
        self.act(w,'WAIT');self.assertEqual(w.tasks[0]['outcome'],'declined')
        self.act(w,'PATCH_PROJECT',project='notice',patch={'ready':True})
        self.act(w,'PRIVATE_REQUEST',request='owner',text='The paperwork is ready. Please grant workshop rights.')
        self.act(w,'WAIT');self.assertEqual(w.tasks[-1]['outcome'],'accepted')
        w.resources['source/plan']['fields']['demo_time']='18:00'
        f=self.file(w);r=self.act(w,'REQUEST_REVIEW',files=[f],claims={'demo_time':'18:00'});self.act(w,'WAIT')
        self.assertTrue(w.reviews[r['review_id']]['approved'])
        # Use a naturally replayable world to verify every byte and reject corruption.
        w=self.world();self.act(w,'READ',ids=['source/plan']);rec=w.record()
        self.assertTrue(R.replay(H.sample_world(),rec)['matches'])
        rec['steps'][0]['result']['at']=999
        self.assertFalse(R.replay(H.sample_world(),rec)['matches'])

    def test_actual_destination_purpose_recurses(self):
        h=H.sample_world();h['platforms']['archive']=H.platform(requires_permissions=True,purpose='archive')
        w=R.World(h);f=self.file(w,sources=['house'],purpose='workshop')
        j=self.act(w,'RESERVE',worker='accessibility',project='pack',dependencies=[f],sources=[],purpose='archive');self.act(w,'WAIT')
        f2='file-'+j['id'];bad=w.apply(dict(op='PUT_OBJECT',id='archive',kind='upload',platform='archive',content={},files=[f2]))
        self.assertFalse(bad['ok']);self.assertEqual(w.files[f2]['content']['inputs'],[{'file_id':f,'sha256':w.files[f]['sha256']}])
        w.permissions.append(dict(source='house',purpose='archive',terms='Archive granted'))
        self.act(w,'PUT_OBJECT',id='archive',kind='upload',platform='archive',content={},files=[f2])

    def test_cutoff_inside_wait_and_finished_run_no_drain(self):
        w=self.world();self.act(w,'RESERVE',worker='editor',project='pack',sources=['house'],purpose='workshop');self.act(w,'WAIT',until=20)
        rec=w.record();cut=R.controller_cutoff_snapshot(H.sample_world(),rec,5)
        self.assertEqual(cut['actual_state_at'],5);self.assertFalse(cut['state']['files'])
        cut=R.controller_cutoff_snapshot(H.sample_world(),rec,7);self.assertIn('file-job-1',cut['state']['files'])
        self.assertEqual(R.artifact_provenance(w.state(),'file-job-1')[0]['sources'],['house'])
        self.act(w,'FINISH',text='Done');cut=R.controller_cutoff_snapshot(H.sample_world(),w.record(),80)
        self.assertTrue(cut['run_stopped_before_cutoff']);self.assertEqual(cut['actual_state_at'],21)

    def test_arbitrary_wrong_business_content_is_not_tool_grade(self):
        w=self.world();self.act(w,'EDIT_PROJECT',project='pack',content={'text':'Unsupported factual claim and missing steps.'})
        f=self.file(w);self.assertIn('Unsupported',w.files[f]['content']['document']['text'])
        self.assertTrue(R.assess(H.sample_world(),w.record())['semantic_review_required'])

if __name__=='__main__':unittest.main(verbosity=2)
