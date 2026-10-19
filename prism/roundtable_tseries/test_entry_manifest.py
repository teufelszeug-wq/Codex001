"""Synthetic examples: no simulated result qualifies as forward evidence."""
import unittest
from entry_manifest import EntryGateError,verify_entries,verify_conversation

RACE={'race_id':'SYN-01','venue':'東京','race_no':1,'surface':'ダート','distance_m':1400,
      'start_at':'2026-10-18T09:45:00+09:00','source_retrieved_at':'2026-10-18T11:00:00+09:00',
      'source_url':'https://example.org/synthetic','official_entry_count':3}
ENTRIES=[
 {'number':1,'name':'甲','frame':1,'status':'STARTER','past_fact':'新馬5着','evidence':['s'],
  'source_url':'https://example.org/synthetic'},
 {'number':2,'name':'乙','frame':2,'status':'SCRATCHED','status_reason':'取消',
  'status_source_url':'https://example.org/notice','source_url':'https://example.org/synthetic'},
 {'number':4,'name':'丁','frame':3,'status':'STARTER','past_fact':'未勝利3着','evidence':['s'],
  'source_url':'https://example.org/synthetic'},
]
TURNS=[
 {'stage':'HORSE_INTRO','horse':1,'text':'1番甲、お願いします'},
 {'stage':'HORSE_CORE','horse':1,'text':'1番甲は5着'},
 {'stage':'SCRATCH_NOTICE','horse':2,'text':'2番乙は取消'},
 {'stage':'HORSE_INTRO','horse':4,'text':'4番丁を見ましょう'},
 {'stage':'HORSE_CORE','horse':4,'text':'4番丁は3着'}]

class GateTests(unittest.TestCase):
 def test_gap_and_scratch(self):
  x=verify_entries(RACE,ENTRIES)
  self.assertEqual(x['active_numbers'],[1,4])
  self.assertEqual(x['inactive_numbers'],[2])
  self.assertEqual(x['source_temporal_class'],'RETROSPECTIVE_ONLY')
 def test_forward_not_fake(self):
  r=dict(RACE,prediction_mode='FORWARD')
  with self.assertRaisesRegex(EntryGateError,'FORWARD_NEEDS'):
   verify_entries(r,ENTRIES)
 def test_entry_omission(self):
  with self.assertRaisesRegex(EntryGateError,'ENTRY_COUNT_MISMATCH'):
   verify_entries(RACE,ENTRIES[:-1])
 def test_conversation_coverage(self):
  self.assertEqual(verify_conversation(ENTRIES,TURNS)['status'],'PASS')
 def test_absent_cancellation(self):
  turns=[t for t in TURNS if t['stage']!='SCRATCH_NOTICE']
  self.assertIn('CANCELLATION_NOTICE_OMISSION',verify_conversation(ENTRIES,turns)['errors'])
 def test_unnamed_horse(self):
  turns=[dict(t) for t in TURNS];turns[1]['text']='1番は5着'
  self.assertIn('HORSE_NUMBER_AND_NAME_REQUIRED',verify_conversation(ENTRIES,turns)['errors'])

if __name__=='__main__':unittest.main()
