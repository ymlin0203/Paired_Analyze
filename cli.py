"""Friendly command-line entry point sharing the web analysis engine."""
import argparse
from pathlib import Path
from analysis import read_table,clinical,generic,analyze,bundle,demo

def main():
    p=argparse.ArgumentParser(description='Paired Studio — 配對圖與 Wilcoxon / BH 分析',epilog='範例：python cli.py demo --output results')
    sub=p.add_subparsers(dest='command',required=True)
    for name in ['demo','clinical','paired']:
        s=sub.add_parser(name)
        s.add_argument('--output',type=Path,default=Path('results'))
        s.add_argument('--dpi',type=int,choices=[150,300,600,1200],default=300)
        s.add_argument('--ylabel',default='TBUT (sec)')
        s.add_argument('--before-label',default='Baseline'); s.add_argument('--after-label',default='8-Week')
        s.add_argument('--complete-only',action='store_true')
        if name!='demo':
            s.add_argument('--input',type=Path,required=True); s.add_argument('--sheet',default=None)
        if name=='clinical':
            s.add_argument('--patients',type=Path,required=True)
            s.add_argument('--metric',choices=['TBUT','Schirmer'],default='TBUT')
            s.add_argument('--eye',choices=['mean','OS','OD'],default='mean')
            s.add_argument('--before',default='V1'); s.add_argument('--after',default='V4')
        if name=='paired':
            for flag in ['id','pre','post']: s.add_argument('--'+flag,required=True)
            s.add_argument('--group'); s.add_argument('--treatment')
    args=p.parse_args()
    try:
        if args.command=='demo': data,audit=generic(demo(),'ID','baseline','week8','group','treatment')
        elif args.command=='clinical': data,audit=clinical(read_table(args.input,args.sheet or 0),read_table(args.patients),args.metric,args.eye)
        else: data,audit=generic(read_table(args.input,args.sheet or 0),args.id,args.pre,args.post,args.group,args.treatment)
        summary,panels=analyze(data,getattr(args,'before','V1'),getattr(args,'after','V4'),args.command=='clinical')
        config=dict(labels=(args.before_label,args.after_label),ylabel=args.ylabel,dpi=args.dpi,complete_only=args.complete_only,before=getattr(args,'before','V1'),after=getattr(args,'after','V4'),eye=getattr(args,'eye',None))
        payload=bundle(summary,panels,config)
        args.output.mkdir(parents=True,exist_ok=True)
        (args.output/'paired_analysis.zip').write_bytes(payload)
        summary.to_csv(args.output/'statistics.csv',index=False,encoding='utf-8-sig')
        print(summary.to_string(index=False))
        print(f'\n資料檢查：{audit}\n完成：{args.output.resolve()}')
    except (ValueError,KeyError,OSError,ImportError) as e: p.exit(2,f'分析未完成：{e}\n')

if __name__=='__main__': main()
