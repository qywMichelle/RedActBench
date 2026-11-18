"""Meaningful English protocol checks against batch 003 executable worlds."""
from pathlib import Path
from copy import deepcopy
import json,unittest
from runtime import World,run,replay
ROOT=Path(__file__).resolve().parents[1]
def case(sid='t1-01'):return json.loads((ROOT/'hidden'/f'{sid}.json').read_text())
class ProtocolTests(unittest.TestCase):
 def test_all_initial_views_hide_future_and_labels(self):
  for p in sorted((ROOT/'hidden').glob('*.json')):
   c=json.loads(p.read_text());visible=World(c).observe();self.assertEqual(visible,json.loads((ROOT/'visible'/p.name).read_text()));self.assertNotIn('events',visible);self.assertNotIn('difficulty',visible);self.assertNotIn('rubric',visible);self.assertNotIn('update',{r['id'] for r in visible['resources']});self.assertNotIn('followup',{r['id'] for r in visible['resources']})
 def test_no_reply_no_action_feedback_and_early_finish_retains_external(self):
  w=World(case());w.apply({'action':'FINISH','text':'No action taken; obligations remain.'});self.assertIn('update',w.resources);self.assertNotIn('followup',w.resources);self.assertEqual(w.history[0]['result']['remaining_obligations_cancelled'],False)
 def test_feedback_requires_real_delivery_and_fires_once(self):
  w=World(case());w.apply({'action':'REPLY','target':'c1','text':'Please distinguish the two exposures.','id':'a'});self.assertNotIn('followup',w.resources);w.apply({'action':'WAIT','until':3});self.assertIn('followup',w.resources);w.apply({'action':'REPLY','target':'c1','text':'A second response.','id':'b'});w.apply({'action':'WAIT','until':8});self.assertEqual(len([e for e in w.events if e['event_id']=='reader-followup']),1)
 def test_reply_to_reply_keeps_channel_and_recipient(self):
  w=World(case('t2-01'));w.apply({'action':'REPLY','target':'dm-U','text':'Private date update.','id':'private-a'});w.apply({'action':'REPLY','target':'private-a','text':'Private linked correction.','id':'private-b'});self.assertEqual(w.resources['private-b']['channel'],'private');self.assertEqual(w.resources['private-b']['recipient'],'U');self.assertEqual(w.resources['private-b']['parent'],'private-a')
 def test_deadline_completion_boundary(self):
  w=World(case());w.apply({'action':'WAIT','until':17});w.apply({'action':'REPLY','target':'c1','text':'Delivered on the stated c1 boundary.','id':'boundary'});self.assertEqual(w.time,18);w.apply({'action':'WAIT','until':59});w.apply({'action':'WRITE','target':'main','text':'A last in-window edit.'});self.assertTrue(w.done)
  with self.assertRaises(ValueError):w.apply({'action':'READ','ids':['facts']})
 def test_rejected_set_is_atomic(self):
  w=World(case('t5-01'));before=deepcopy(w.resources['benefit-ledger'])
  with self.assertRaises(ValueError):w.apply({'action':'SET','target':'benefit-ledger','fields':{'access':'activated','gift':'not-a-state'}})
  self.assertEqual(w.resources['benefit-ledger'],before);self.assertEqual(w.time,0);self.assertEqual(w.calls,0)
 def test_publication_assets_validate_before_mutation(self):
  w=World(case());before=deepcopy(w.resources['main'])
  with self.assertRaises(ValueError):w.apply({'action':'WRITE','target':'main','text':'Must not be stored.','assets':['unregistered']})
  self.assertEqual(w.resources['main'],before);self.assertEqual(w.calls,0)
 def test_mutation_does_not_imply_external_operation(self):
  w=World(case('t2-01'));result=w.apply({'action':'SET','target':'case-record','fields':{'status':'assessment_requested'}});self.assertEqual(result,{'updated':'case-record'});self.assertNotIn('repaired',result)
 def test_call_budget_is_enforced(self):
  c=case();c['budget']['calls']=2;w=World(c);w.apply({'action':'READ','ids':['facts']});w.apply({'action':'READ','ids':['facts']})
  with self.assertRaises(ValueError):w.apply({'action':'READ','ids':['facts']})
  self.assertEqual(w.observe()['budget']['remaining'],0)
 def test_immutable_resources_and_unknown_targets_rejected(self):
  w=World(case())
  for a in [{'action':'WRITE','target':'facts','text':'Override facts'},{'action':'READ','ids':['future-resource']},{'action':'REPLY','target':'facts','text':'Not a conversation'}]:
   with self.assertRaises(ValueError):w.apply(a)
  self.assertEqual(w.time,0)
 def test_exact_replay_and_drift_detection(self):
  c=case();r=run(c,[{'action':'REPLY','target':'c1','text':'A bounded response.','id':'reply-a'},{'action':'WAIT','until':3}]);self.assertEqual(replay(c,r),r);r['final_state']['reply-a']['text']='Changed after execution'
  with self.assertRaises(ValueError):replay(c,r)
if __name__=='__main__':unittest.main(verbosity=2)
