"""Đọc bảng điểm Practice được chia sẻ, chỉ dùng token đội mình và chỉ gửi GET."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import time
import threading
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'experiments/data/shared_leaderboard'
sys.path.insert(0,str(ROOT/'src'))
from hexudon.live_api import LiveAPI,APIError
REQUEST_LOCK=threading.Lock()
NEXT_REQUEST=0.


def game_get(api,path,game_id):
    global NEXT_REQUEST
    # Gửi chậm và chờ khi bị giới hạn, không đổi tài khoản để né hạn mức.
    with REQUEST_LOCK:
        time.sleep(max(0,NEXT_REQUEST-time.monotonic()))
        NEXT_REQUEST=time.monotonic()+1.1
        for attempt in range(3):
            try:return api.request('GET',path,game_id=game_id,timeout=20)
            except APIError as error:
                if error.status!=429 or attempt==2:raise
                print('API 429: chờ 60 giây trước khi đọc tiếp.',flush=True)
                time.sleep(60)


def manager_get(api,path):
    # API giao diện dùng token thô; API trò chơi dùng Bearer qua LiveAPI.
    request=Request(api.base_url+path,headers={'Authorization':api.token,'Accept':'application/json','User-Agent':'Mozilla/5.0'})
    with urlopen(request,timeout=20) as response:return json.load(response)


def score(detail):
    return [detail.get('distinct_types',0),detail.get('cumulative_daily_types',0),detail.get('total_servings',0)]


def read_pair(api,question,team):
    game_id=f"{question['id']}:{team['id']}"
    row={'case':question['name'],'question_id':question['id'],'team_id':str(team['id']),'team':team['name'],
         'read_at_utc':datetime.now(timezone.utc).isoformat(),'expected_days':question['days']}
    try:
        raw_score=game_get(api,'/api/game/practice/score',game_id)
        peer=game_get(api,'/api/game/practice/peer',game_id)
        detail=raw_score.get('detail',{}).get(str(team['id']))
        daily=[]
        for day in peer.get('days',[]):
            own=next((t for t in day.get('teams',[]) if str(t['team_id'])==str(team['id'])),None)
            if own:daily.append({'day':day['day'],'types':own['types'],'servings':own['servings'],'submitted':own.get('submitted',False)})
        row.update(score=score(detail) if detail else None,daily=daily,response_seconds=detail.get('cumulative_response_time') if detail else None,
                   days_submitted_field=detail.get('days_submitted') if detail else None)
        row['complete']=({d['day'] for d in daily}==set(range(question['days'])) and all(d['submitted'] for d in daily))
        row['consistent']=(detail is not None and sum(d['types'] for d in daily)==row['score'][1] and sum(d['servings'] for d in daily)==row['score'][2])
        if not row['consistent'] and detail:
            # Đội có thể đang nộp khi đọc: đọc lại điểm một lần để phát hiện snapshot lệch.
            again=game_get(api,'/api/game/practice/score',game_id).get('detail',{}).get(str(team['id']))
            if again:
                row['score']=score(again)
                row['consistent']=(sum(d['types'] for d in daily)==row['score'][1] and sum(d['servings'] for d in daily)==row['score'][2])
        row['status']='complete' if row['complete'] and row['consistent'] else ('partial' if daily else 'no_days')
        if not row['consistent']:row['status']='inconsistent' if detail else 'no_score'
    except APIError as error:
        row.update(status='no_record' if error.status==404 else 'error',http_status=error.status,complete=False,consistent=False,score=None,daily=[])
    except (TimeoutError,OSError) as error:
        row.update(status='error',error=type(error).__name__,complete=False,consistent=False,score=None,daily=[])
    return row


def compare(a,b):
    return 0 if a>b else (1 if a==b else 2)


def summarize(snapshot):
    rows=snapshot['records'];own=snapshot['own_team_id'];names={str(t['id']):t['name'] for t in snapshot['teams']}
    lookup={(r['team_id'],r['case']):r for r in rows}
    baseline={r['case']:r['server_score'] for r in json.loads((ROOT/'experiments/data/tour_api_evidence/summary.json').read_text(encoding='utf8'))}
    per_case=[];per_team=[];baseline_losses=[];current_losses=[]
    for q in snapshot['questions']:
        ours=lookup[own,q['name']]
        peers=[r for r in rows if r['case']==q['name'] and r['team_id']!=own and r['complete'] and r['consistent']]
        best=max((r['score'] for r in peers),default=None)
        current_counts=[0,0,0];old_counts=[0,0,0]
        for peer in peers:
            if ours['complete'] and ours['consistent']:
                result=compare(ours['score'],peer['score']);current_counts[result]+=1
                if result==2:current_losses.append({'case':q['name'],'team':peer['team'],'team_id':peer['team_id'],'ours':ours['score'],'peer':peer['score']})
            if q['name'] in baseline:
                result=compare(baseline[q['name']],peer['score']);old_counts[result]+=1
                if result==2:baseline_losses.append({'case':q['name'],'team':peer['team'],'team_id':peer['team_id'],'ours':baseline[q['name']],'peer':peer['score']})
        per_case.append({'case':q['name'],'question_id':q['id'],'baseline':baseline.get(q['name']),'ours':ours.get('score'),
                         'own_complete':ours['complete'] and ours['consistent'],'best_peer_score':best,
                         'best_peer_teams':[r['team'] for r in peers if r['score']==best],'complete_opponents':len(peers),
                         'current_wins_ties_losses':current_counts,'baseline_wins_ties_losses':old_counts})
    for team_id,name in names.items():
        if team_id==own:continue
        counts=[0,0,0];old=[0,0,0];complete=0;partial=0;unknown=0;comparable=0
        unfinished_with_days=0;no_days=0
        for q in snapshot['questions']:
            peer=lookup[team_id,q['name']];ours=lookup[own,q['name']]
            if peer['complete'] and peer['consistent']:
                complete+=1
                if ours['complete'] and ours['consistent']:counts[compare(ours['score'],peer['score'])]+=1;comparable+=1
                if q['name'] in baseline:old[compare(baseline[q['name']],peer['score'])]+=1
            elif peer['status'] in ('no_days','no_record','partial'):
                partial+=1
                if peer['status']=='partial':unfinished_with_days+=1
                else:no_days+=1
            else:unknown+=1
        per_team.append({'team_id':team_id,'team':name,'complete_questions':complete,'comparable_questions':comparable,
                         'current_wins_ties_losses':counts,'baseline_wins_ties_losses':old,'incomplete_or_no_days':partial,'unknown':unknown,
                         'unfinished_with_days':unfinished_with_days,'no_days':no_days})
    return {'started_at_utc':snapshot['started_at_utc'],'finished_at_utc':snapshot['finished_at_utc'],'team_count':len(names),
            'question_count':len(snapshot['questions']),'per_case':per_case,'per_team':per_team,
            'current_losses':current_losses,'baseline_losses':baseline_losses,
            'error_records':sum(r['status'] in ('error','inconsistent','no_score') for r in rows),
            'completed_records':sum(r['complete'] and r['consistent'] for r in rows)}


def write_tables(snapshot, summary):
    # Giữ cả bộ ba điểm để không xếp hạng sai khi D chưa đạt cận.
    cases = [q['name'] for q in snapshot['questions']]
    rows = snapshot['records']
    lookup = {(r['team_id'], r['case']): r for r in rows}
    def point(value):
        return '(' + ', '.join(map(str, value)) + ')'
    def cell(team_id, case):
        row = lookup[str(team_id), case]
        if row['complete'] and row['consistent']:
            return point(row['score'])
        return 'Chưa hoàn tất' if row['status'] == 'partial' else 'Chưa có lượt hoàn tất'
    lines = ['# Bảng điểm Practice tại thời điểm tra cứu', '',
             f"Khoảng thu thập UTC: {snapshot['started_at_utc']} đến {snapshot['finished_at_utc']}.", '',
             'Điểm được so theo thứ tự (U, D, Q), không cộng thành phần hoặc cộng các bài để tạo thứ hạng chung. '
             'Chỉ dùng lượt có đủ ngày và tổng D, Q khớp replay. Q01 và Q02 cùng cấu hình nhưng là hai lượt nộp riêng.', '',
             '| Bài | Điểm hiện tại đội ta (U, D, Q) | Đối thủ cao nhất | Điểm đối thủ | Hạng đội ta / số đội hoàn tất |',
             '|---|---|---|---|---|']
    for case in summary['per_case']:
        rank = 1 + case['current_wins_ties_losses'][2]
        lines.append(f"| {case['case']} | {point(case['ours'])} | {', '.join(case['best_peer_teams'])} | {point(case['best_peer_score']) if case['best_peer_score'] else '-'} | {rank}/{case['complete_opponents'] + 1} |")
    lines += ['', '## Điểm của toàn bộ tài khoản', '',
              '| Đội (mã đội) | ' + ' | '.join(cases) + ' |',
              '|---|' + '---|' * len(cases)]
    for team in snapshot['teams']:
        lines.append(f"| {team['name']} ({team['id']}) | " + ' | '.join(cell(team['id'], c) for c in cases) + ' |')
    lines += ['', '## Đối chiếu với đội ta', '',
              'Không có dữ liệu ngày hiện tại không chứng minh đội chưa từng nộp: lịch sử có thể đã được reset. '
              'Bài đang dở được tách khỏi bài không có dữ liệu ngày; lỗi API hoặc điểm chưa khớp cũng được báo riêng.', '',
              '| Đối thủ | Số bài hoàn tất | Bài đang dở | Bài không có dữ liệu ngày hiện tại | Bài lỗi hoặc chưa khớp | Đội ta thắng | Bằng điểm | Đội ta thua |',
              '|---|---|---|---|---|---|---|---|']
    for team in summary['per_team']:
        w, t, l = team['current_wins_ties_losses']
        lines.append(f"| {team['team']} ({team['team_id']}) | {team['complete_questions']} | {team['unfinished_with_days']} | {team['no_days']} | {team['unknown']} | {w} | {t} | {l} |")
    lines += ['', '## Số loại và số suất thu được từng ngày', '',
              'Mỗi ô ghi (số loại trong ngày, số suất trong ngày). Ngày API 0 được trình bày là ngày 1. '
              'Bảng này chỉ gồm các lượt đã hoàn tất và kiểm tra khớp điểm.', '']
    for case in cases:
        lines += [f'### {case}', '', '| Đội | ' + ' | '.join(f'Ngày {i+1}' for i in range(10)) + ' |',
                  '|---|' + '---|' * 10]
        for row in rows:
            if row['case'] != case or not row['complete'] or not row['consistent']:
                continue
            days = sorted(row['daily'], key=lambda x: x['day'])
            lines.append(f"| {row['team']} | " + ' | '.join(point([day['types'], day['servings']]) for day in days) + ' |')
        lines.append('')
    lines += ['## Nguồn và cách đọc lại', '',
              'Chỉ dùng token đội ta và các yêu cầu GET. API giao diện cung cấp danh sách đội và câu hỏi; '
              'API Practice chia sẻ cung cấp điểm và replay. Không sử dụng token của đội khác, không gửi bài hoặc reset.', '',
              *['- `' + e + '`' for e in snapshot['endpoints']], '',
              'Token được đọc từ `.env` và không lưu trong các file dữ liệu. '
              'Điểm hiện tại có thể khác lượt tour đã lưu trong báo cáo; summary.json giữ hai nguồn riêng.', '',
              'Đọc mới: `python -X utf8 experiments/run.py compare_practice_leaderboard`.', '',
              'Đọc bù mục lỗi: thêm `--resume`. Tạo lại bảng từ dữ liệu đã lưu: thêm `--summarize-only`.', '']
    (DATA / 'bang_diem.md').write_text('\n'.join(lines), encoding='utf8')


def main():
    global DATA
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env',default=str(ROOT/'.env'))
    parser.add_argument('--match',type=int,default=11)
    parser.add_argument('--workers',type=int,default=1)
    parser.add_argument('--resume',action='store_true',help='Đọc lại các mục lỗi, giữ các mục đã kiểm tra được')
    parser.add_argument('--summarize-only',action='store_true')
    parser.add_argument('--output',default=str(DATA),help='Thư mục lưu lần tra cứu; dùng thư mục mới để giữ số liệu cũ')
    args=parser.parse_args();DATA=Path(args.output);DATA.mkdir(parents=True,exist_ok=True)
    if args.summarize_only:snapshot=json.loads((DATA/'snapshot.json').read_text(encoding='utf8'))
    else:
        api=LiveAPI(args.env,timeout=20);start=datetime.now(timezone.utc).isoformat()
        match=manager_get(api,f'/manager/api/match/{args.match}')
        response=manager_get(api,'/manager/api/question?limit=100')
        questions=[]
        for q in response['data']:
            if q['match_id']==args.match:
                config=json.loads(q['question_data'])
                questions.append({'id':q['id'],'name':q['name'],'days':len(config['daySteps'])})
        questions.sort(key=lambda q:q['name'])
        teams=[{'id':t['id'],'name':t['name']} for t in match['teams']]
        previous=json.loads((DATA/'snapshot.json').read_text(encoding='utf8')) if args.resume and (DATA/'snapshot.json').exists() else None
        rows=[r for r in previous['records'] if r['status'] not in ('error','inconsistent','no_score')] if previous else []
        existing={(r['team_id'],r['case']) for r in rows}
        if previous:start=previous['started_at_utc']
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            jobs=[(q,t) for q in questions for t in teams if (str(t['id']),q['name']) not in existing]
            jobs.sort(key=lambda qt:str(qt[1]['id'])!=api.team_id)
            futures=[pool.submit(read_pair,api,q,t) for q,t in jobs]
            for n,future in enumerate(as_completed(futures),1):
                row=future.result();rows.append(row)
                if n%25==0:print('Đã đọc',n,'/',len(futures),flush=True)
        snapshot={'started_at_utc':start,'finished_at_utc':datetime.now(timezone.utc).isoformat(),'match_id':args.match,
                  'own_team_id':api.team_id,'teams':teams,'questions':questions,
                  'endpoints':['GET /manager/api/match/{id}','GET /manager/api/question?limit=100','GET /api/game/practice/score?game_id={question_id}:{team_id}','GET /api/game/practice/peer?game_id={question_id}:{team_id}'],
                  'records':sorted(rows,key=lambda r:(int(r['team_id']),r['case']))}
        (DATA/'snapshot.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf8')
    summary=summarize(snapshot)
    (DATA/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    write_tables(snapshot, summary)
    print('Đội:',summary['team_count'],'Bài:',summary['question_count'],'Lỗi/chưa khớp:',summary['error_records'])
    print('Tài khoản hiện tại thua:',summary['current_losses'])
    print('Phương án trong báo cáo thua:',summary['baseline_losses'])


if __name__=='__main__':main()
