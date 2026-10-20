from pathlib import Path
import json,statistics as st
f=Path(__file__).resolve().parents[2]/'experiments/data/tour_study'
r=json.loads((f/'results.json').read_text(encoding='utf8'));m=json.loads((f/'manifest.json').read_text(encoding='utf8'))
summary={}
def stats(rows):
 return {'runs':len(rows),'mean_score':[round(st.mean(x['score'][i] for x in rows),2) for i in range(3)],'full_U':sum(x['score'][0]==x['U_bound'] for x in rows),'full_D':sum(x['full_D'] for x in rows),'min_D':min(x['score'][1] for x in rows),'max_D':max(x['score'][1] for x in rows),'Q_range':[min(x['score'][2] for x in rows),max(x['score'][2] for x in rows)],'mean_day_seconds':round(st.mean(d['planning_seconds'] for x in rows for d in x['daily']),3),'max_day_seconds':round(max(d['planning_seconds'] for x in rows for d in x['daily']),3)}
summary['matched']={c['case']:{v:stats([x for x in r if x['experiment']=='matched' and x['case']==c['case'] and x['variant']==v]) for v in ['greedy','full']} for c in m['cases']}
for group in ['practice','generated']:
 summary['ablation_'+group]={v:stats([x for x in r if x['experiment']=='matched' and x['source']==group and x['case'] in m['ablation_cases'] and x['variant']==v]) for v in ['full','no_local','no_cover','no_anchor']}
summary['pairs']={}
for v in ['greedy','no_local','no_cover','no_anchor']:
 candidates=[x for x in r if x['experiment']=='matched' and x['variant']==v]
 lookup={(x['case'],x['seed']):x for x in r if x['experiment']=='matched' and x['variant']=='full'}
 pairs=[(lookup[x['case'],x['seed']]['score'],x['score']) for x in candidates]
 summary['pairs'][v]={'wins':sum(a>b for a,b in pairs),'ties':sum(a==b for a,b in pairs),'losses':sum(a<b for a,b in pairs)}
summary['roles']={}
for variant in ['greedy','full']:
 for label,exp in [('all_patrol','roles'),('one_supply','matched')]:
  summary['roles'][variant+'_'+label]=stats([x for x in r if x['case']=='Q01' and x['variant']==variant and x['experiment']==exp])
summary['budget']={c:{str(b):stats([x for x in r if x['case']==c and x['variant']=='full' and x['seconds']==b and x['experiment'] in ['budget','matched']]) for b in [1.,3.]} for c in ['Q01','Q06','G16']}
summary['overall']={'valid_runs':sum(x['valid'] for x in r),'daily_plans':sum(len(x['daily']) for x in r),'max_day_seconds':max(d['planning_seconds'] for x in r for d in x['daily'])}
(f/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
print('Đã lưu summary.json. Mỗi dòng dưới đây là trung bình ba lượt chạy:')
for case,values in summary['matched'].items():
    print(case,'Greedy',values['greedy']['mean_score'],'Tour',values['full']['mean_score'])
print('Tour so với các đối chứng:',summary['pairs'])
print('Kiểm tra chung:',summary['overall'])
