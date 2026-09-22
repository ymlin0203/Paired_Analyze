import unittest
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon
from analysis import bh, generic, clinical, analyze, demo

class AnalysisTests(unittest.TestCase):
    def test_bh_reference_and_nan(self):
        np.testing.assert_allclose(bh([.01,.04,.03,np.nan]),[.03,.04,.04,np.nan])
    def test_duplicates_rejected(self):
        df=demo(); df.loc[1,'ID']=df.loc[0,'ID']
        with self.assertRaises(ValueError): generic(df,'ID','baseline','week8')
    def test_pair_alignment_missing_and_effect(self):
        df=pd.DataFrame({'id':['d','a','c','b','e'],'pre':[1,2,3,4,5],'post':[2,4,3,1,np.nan]})
        data,_=generic(df,'id','pre','post')
        s,_=analyze(data.sample(frac=1,random_state=7)); r=s.iloc[0]
        self.assertEqual(r.n_pairs,4); self.assertEqual(r.n_incomplete,1)
        self.assertAlmostEqual(r.p,wilcoxon([1,2,0,-3],zero_method='wilcox').pvalue)
        self.assertAlmostEqual(r.rank_biserial,0)
    def test_all_zero_unavailable(self):
        df=pd.DataFrame({'id':list('abcd'),'a':[1]*4,'b':[1]*4})
        s,_=analyze(generic(df,'id','a','b')[0])
        self.assertEqual(s.iloc[0].status,'all_zero_differences'); self.assertTrue(np.isnan(s.iloc[0].p))
    def test_strict_both_eyes_even_missing_column(self):
        df=pd.DataFrame({'序號':['a'],'Group':[1],'TBUTV1-OS':[2],'TBUTV4-OS':[4],'TBUTV4-OD':[6]})
        pt=pd.DataFrame({'ID':['a'],'TX Group':[1]})
        data,_=clinical(df,pt)
        self.assertTrue(data[data.visit=='V1'].value.isna().all())
        self.assertEqual(data[data.visit=='V4'].value.iloc[0],5)
    def test_small_sample(self):
        df=demo().head(3)
        s,_=analyze(generic(df,'ID','baseline','week8')[0])
        self.assertEqual(s.iloc[0].status,'insufficient_pairs')

if __name__=='__main__': unittest.main()
