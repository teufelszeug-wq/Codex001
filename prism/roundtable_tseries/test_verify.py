"""Self-contained regression checks for the portable roundtable acceptance gate."""
import copy
import unittest
from verify import verify

def good():
    r={'venue':'東京','race_no':1,'class':'2歳未勝利','surface':'ダート',
       'distance_m':1400,'start_jst':'09:45','expected_count':2,'source_url':'https://www.jra.go.jp/'}
    h=[{'number':1,'frame':1,'name':'試験甲','past_fact':'過去走の情報','evidence':['official']},
       {'number':2,'frame':2,'name':'試験乙','past_fact':'過去走の情報','evidence':['official']}]
    t=[
      {'id':1,'stage':'RACE_INTRO','speaker':'篠宮律','text':'東京1Rのレースを紹介します'},
      {'id':2,'stage':'COURSE','speaker':'りお','text':'コースはどうでしょう？','responds_to':1},
      {'id':3,'stage':'COURSE','speaker':'宮坂直矩','text':'脚質を決め打ちしません','responds_to':2,'event_type':'COUNTERARGUMENT'},
      {'id':4,'stage':'HORSE_INTRO','horse':1,'speaker':'篠宮律','text':'1番試験甲からお願いします','responds_to':3},
      {'id':5,'stage':'HORSE_CORE','horse':1,'speaker':'堂前岳','text':'1番試験甲は資料確認が必要','responds_to':4},
      {'id':6,'stage':'HORSE_INTRO','horse':2,'speaker':'篠宮律','text':'次は2番試験乙です','responds_to':5},
      {'id':7,'stage':'HORSE_CORE','horse':2,'speaker':'堂前岳','text':'2番試験乙の過去走を検証','responds_to':6},
      {'id':8,'stage':'COMPARE_START','speaker':'篠宮律','text':'全頭診断を終えて比較します','responds_to':7},
      {'id':9,'stage':'CLOSE','speaker':'篠宮律','text':'結論は保留します','responds_to':8}
    ]
    return {'race':r,'horses':h,'turns':t,'meeting_mode':'SINGLE_MODEL_ROLE_SIMULATION','independent_ai_calls':0}

class GateTests(unittest.TestCase):
    def test_honest_dialogue(self):
        self.assertEqual(verify(good())['status'],'PASS')
    def test_horse_omission(self):
        x=good();x['turns']=[t for t in x['turns'] if t['id']!=7]
        self.assertIn('HORSE_CORE_NOT_EXACTLY_ONCE',verify(x)['errors'])
    def test_missing_horse_name(self):
        x=good();x['turns'][6]['text']='2番の候補'
        errs=verify(x)['errors']
        self.assertIn('HORSE_NAME_MISSING',errs)
        self.assertIn('HORSE_NUMBER_WITHOUT_NAME',errs)
    def test_second_place_number_not_a_horse_reference(self):
        x=good();x['turns'][8]['text']='2番手で進めた例です'
        self.assertEqual(verify(x)['status'],'PASS')
    def test_false_independent_call(self):
        x=good();x['independent_ai_calls']=3
        self.assertIn('FALSE_INDEPENDENT_AI_CLAIM',verify(x)['errors'])

if __name__=='__main__':
    unittest.main()
