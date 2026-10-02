import unittest
import pandas as pd
from src.weekly import aggregate_weekly,classify_weekly

class WeeklyTests(unittest.TestCase):
    def setUp(self):
        self.cohort=pd.DataFrame([{'player_id':'a','player':'A','position':1}])
        self.start='2026-08-05T00:00:00Z';self.end='2026-09-30T00:00:00Z'
    def row(self,mid,time,k=10,d=10):
        return {'player_id':'a','match_id':mid,'finished_at':time,'kills':k,'deaths':d}
    def test_boundaries_and_fixed_eight_weeks(self):
        rows=[self.row('first',self.start),self.row('second','2026-08-12T00:00:00Z'),self.row('last','2026-09-29T23:59:59Z'),self.row('excluded',self.end)]
        result,audit=aggregate_weekly(self.cohort,pd.DataFrame(rows),self.start,self.end)
        self.assertEqual(len(result),8)
        self.assertEqual(result.matches.tolist(),[1,1,0,0,0,0,0,1])
        self.assertEqual(audit['outside_period_rows'],1)
    def test_incomplete_week_suppressed_not_zero(self):
        rows=pd.DataFrame([self.row('known',self.start)])
        missing=pd.DataFrame([{'player_id':'a','match_id':'missing','finished_at':self.start}])
        result,_=aggregate_weekly(self.cohort,rows,self.start,self.end,missing)
        self.assertEqual(result.iloc[0].status,'dados_incompletos')
        self.assertEqual(result.iloc[0].expected_matches,2)
        self.assertTrue(pd.isna(result.iloc[0].kd))
        self.assertEqual(result.iloc[1].status,'sem_partidas')
    def test_ratio_is_weighted_by_deaths(self):
        rows=pd.DataFrame([self.row('one',self.start,10,1),self.row('two',self.start,0,9)])
        result,_=aggregate_weekly(self.cohort,rows,self.start,self.end)
        self.assertEqual(result.iloc[0].kd,1)
    def test_missing_duplicate_of_collected_rejected(self):
        row=self.row('same',self.start)
        with self.assertRaises(ValueError):aggregate_weekly(self.cohort,pd.DataFrame([row]),self.start,self.end,pd.DataFrame([row]))
    def test_classification_independent_by_week(self):
        data=pd.DataFrame({'player_id':list('abcde')*2,'week':[1]*5+[2]*5,'status':['ok']*10,'matches':[5]*10,'kd':[1,1,1,1,3,3,3,3,3,3]})
        result,stats=classify_weekly(data)
        self.assertEqual(result.loc[result.player_id.eq('e'),'classification'].tolist(),['outlier_positivo','normal'])
        self.assertEqual(stats.positive_outliers.tolist(),[1,0])

class RealApiRegressionTests(unittest.TestCase):
    def test_repeated_map_not_double_counted(self):
        from src.faceit import FaceitClient,ApiError
        from unittest.mock import patch
        import tempfile
        import copy
        # Valores encontrados na resposta real de 1-16acb1bd-db99-45f0-8765-391f147f0591.
        one={'match_id':'m','match_round':'1','round_stats':{'Map':'de_dust2','Score':'16 / 12','Rounds':'28'},
             'teams':[{'players':[{'player_id':'p','player_stats':{'Kills':'26','Deaths':'17'}}]}]}
        with tempfile.TemporaryDirectory() as directory:
            client=FaceitClient('unit-test-only',directory)
            with patch.object(client,'get',return_value={'rounds':[one,copy.deepcopy(one)]}):
                self.assertEqual(client.player_match('m','p'),(26,17))
            other=copy.deepcopy(one);other['teams'][0]['players'][0]['player_stats']['Kills']='27'
            with patch.object(client,'get',return_value={'rounds':[one,other]}):
                with self.assertRaises(ApiError):client.player_match('m','p')

if __name__=='__main__':unittest.main()
