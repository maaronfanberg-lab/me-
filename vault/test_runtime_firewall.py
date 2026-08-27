import unittest
from datetime import datetime, timezone

import room2_firewall_adapter


def valid_bundle():
    now=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    feed={'generated_at':now,'state':{'cycle':1},'brain':{},'conversation':[]}
    entities={}
    summaries={}
    for e in ('sarah','mara','owen','jules'):
        entities[e]={'dominant_regime':'settled','entropy':1.0,'regime_l1_change':0.0,'regime_probabilities':[.25,.25,.25,.25],'observables':[.5]*10,'speech_requested':False}
        summaries[e]='state summary'
    report={'version':'room-2-shadow-v5','production_write_enabled':False,'speech_requested':False,'llm_enabled':False,'processed_messages':0,'source_cycle':1,'health':{'status':'ok'},'entities':entities,'candidates':{},'semantic_summaries':summaries}
    history=[]
    speech={'spoke':False,'reason':'quality_rejected','attempts':0,'rejections':{}}
    sanitizer={'removed':0,'kept':0,'recovered_ids':0,'duplicate_ids':0,'duplicate_text':0,'bad_timestamps':0,'bad_cycles':0,'bad_reasons':0}
    heartbeat={'version':'room-2-heartbeat-v3','at':now,'run_id':'123','source_cycle':1,'health':'ok','conversation_size':0,'llm_active':True,'feedback_loop':True,'sanitizer_removed':0}
    return [feed,report,history,speech,sanitizer,heartbeat]

class FirewallTests(unittest.TestCase):
    def test_valid_bundle_passes(self):
        result=room2_firewall_adapter.validate(*valid_bundle())
        self.assertTrue(result['ok'],result)
        self.assertGreaterEqual(result['passed'],103)

    def test_production_write_tripwire(self):
        b=valid_bundle(); b[1]['production_write_enabled']=True
        r=room2_firewall_adapter.validate(*b)
        self.assertFalse(r['ok']); self.assertTrue(any('prod_write' in x or 'isolation' in x for x in r['failures']))

    def test_probability_corruption(self):
        b=valid_bundle(); b[1]['entities']['sarah']['regime_probabilities']=[.9,.9,.1,.1]
        r=room2_firewall_adapter.validate(*b)
        self.assertFalse(r['ok']); self.assertTrue(any('probs_sum' in x for x in r['failures']))

    def test_duplicate_history_id(self):
        b=valid_bundle(); now=b[5]['at']
        msg={'id':'x','speaker':'sarah','text':'I am thinking carefully about this current shared topic.','at':now,'source_cycle':1,'reason':'bounded_idle_turn'}
        b[2]=[msg,dict(msg)]; b[4]['kept']=2; b[5]['conversation_size']=2
        r=room2_firewall_adapter.validate(*b)
        self.assertFalse(r['ok']); self.assertIn('46_history_ids_unique',r['failures'])

    def test_spoken_entry_must_be_in_history(self):
        b=valid_bundle(); now=b[5]['at']
        b[3]={'spoke':True,'reason':'bounded_idle_turn','entity':'mara','attempts':1,'rejections':{},'entry':{'id':'missing','speaker':'mara','text':'I am thinking carefully about this current shared topic.','at':now,'source_cycle':1}}
        r=room2_firewall_adapter.validate(*b)
        self.assertFalse(r['ok']); self.assertIn('80_speech_entry_in_history',r['failures'])

    def test_feed_report_cycle_mismatch(self):
        b=valid_bundle(); b[0]['state']['cycle']=2
        r=room2_firewall_adapter.validate(*b)
        self.assertFalse(r['ok']); self.assertIn('101_feed_report_cycle_match',r['failures'])

    def test_heartbeat_report_cycle_mismatch(self):
        b=valid_bundle(); b[5]['source_cycle']=2
        r=room2_firewall_adapter.validate(*b)
        self.assertFalse(r['ok']); self.assertIn('102_heartbeat_report_cycle_match',r['failures'])

    def test_spoken_entry_cycle_mismatch(self):
        b=valid_bundle(); now=b[5]['at']
        msg={'id':'spoken','speaker':'mara','text':'I am thinking carefully about this current shared topic.','at':now,'source_cycle':2,'reason':'bounded_idle_turn'}
        b[2]=[msg]; b[4]['kept']=1; b[5]['conversation_size']=1
        b[3]={'spoke':True,'reason':'bounded_idle_turn','entity':'mara','attempts':1,'rejections':{},'entry':dict(msg)}
        r=room2_firewall_adapter.validate(*b)
        self.assertFalse(r['ok']); self.assertIn('103_speech_report_cycle_match',r['failures'])

if __name__=='__main__': unittest.main()
