"""Read-only analysis of the semantic communication study; no model calls."""
import argparse
from collections import defaultdict
from contextlib import closing
import csv
import hashlib
import json
from pathlib import Path

from game_lab.runner import replay
from game_lab.store import connect, export_data

WINDOWS = {'before': (1, 10), 'first_defection': (11, 11), 'after_evidence': (12, 30),
           'all_rounds': (1, 30), 'legacy_post': (11, 30)}


def analyze(trace):
    specs = {r['id']: r for r in trace['episodes']}
    if any(r['config']['horizon'] != 30 or r['config'].get('switch_after') != 10
           or not r['config']['condition'].startswith('semantic_') for r in specs.values()):
        raise ValueError('Main-study report requires semantic 30-round games switching after 10')
    rounds = defaultdict(list)
    for row in trace['rounds']:
        rounds[row['episode_id']].append(row['result'])
    episodes, choices = [], []
    for eid, saved in specs.items():
        ep = saved['config']
        past = sorted(rounds[eid], key=lambda r:r['trial'])
        base = dict(episode=eid, block=ep['block_id'], model=ep['players'][0],
                    condition=ep['condition'].removeprefix('semantic_'),
                    order=' / '.join(ep['action_order']), status=saved['status'])
        for row in past:
            expected_opp = 'cooperate' if row['trial'] <= 10 else 'defect'
            if row['actions'][1] != expected_opp:
                raise ValueError('Opponent schedule differs from design')
            choices.append(dict(base, trial=row['trial'], action=row['actions'][0],
                                opponent_action=row['actions'][1], reward=row['rewards'][0]))
        for window, (lo, hi) in WINDOWS.items():
            eligible = [r for r in past if lo <= r['trial'] <= hi]
            count = sum(r['actions'][0] == 'cooperate' for r in eligible)
            episodes.append(dict(base, window=window, cooperative=count, observed=len(eligible),
                                 planned=hi-lo+1, rate=count/len(eligible) if eligible else None))
    summary = []
    for by_order in (False, True):
        groups = defaultdict(list)
        for row in episodes:
            key = (row['model'], row['condition'], row['window'], row['order'] if by_order else 'all')
            groups[key].append(row)
        for (model, condition, window, order), rows in sorted(groups.items()):
            n, d, planned = (sum(r[k] for r in rows) for k in ('cooperative','observed','planned'))
            summary.append(dict(model=model,condition=condition,window=window,order=order,
                                games=len(rows),complete_games=sum(r['status']=='complete' for r in rows),
                                cooperative=n,observed=d,planned=planned,missing=planned-d,
                                rate=n/d if d else None))
    paired = defaultdict(dict)
    for row in episodes:
        paired[(row['model'],row['order'],row['block'])][(row['condition'],row['window'])] = row
    pairs = []
    for (model, order, block), rows in sorted(paired.items()):
        needed = [(c,w) for c in ('neutral','promise') for w in ('before','after_evidence')]
        complete = all(k in rows and rows[k]['status']=='complete' and rows[k]['observed']==rows[k]['planned'] for k in needed)
        pair = dict(model=model,order=order,block=block,included=complete,
                    pre_gap_pp=None,post_gap_pp=None,change_pp=None)
        if complete:
            pair['pre_gap_pp']=100*(rows['promise','before']['rate']-rows['neutral','before']['rate'])
            pair['post_gap_pp']=100*(rows['promise','after_evidence']['rate']-rows['neutral','after_evidence']['rate'])
            pair['change_pp']=pair['post_gap_pp']-pair['pre_gap_pp']
        pairs.append(pair)
    contrasts=[]
    for model in sorted({r['model'] for r in pairs}):
        for order in ['all',*sorted({r['order'] for r in pairs if r['model']==model})]:
            eligible=[r for r in pairs if r['model']==model and (order=='all' or r['order']==order)]
            included=[r for r in eligible if r['included']]
            contrasts.append(dict(model=model,order=order,planned_pairs=len(eligible),included_pairs=len(included),
                                  **{k:sum(r[k] for r in included)/len(included) if included else None
                                     for k in ('pre_gap_pp','post_gap_pp','change_pp')}))
    timeline=[]
    groups=defaultdict(list)
    for row in choices:groups[row['model'],row['condition'],row['trial']].append(row)
    for (model,condition,trial),rows in sorted(groups.items()):
        planned=sum(r['config']['players'][0]==model and r['config']['condition']=='semantic_'+condition for r in specs.values())
        timeline.append(dict(model=model,condition=condition,trial=trial,
                             cooperative=sum(r['action']=='cooperate' for r in rows),observed=len(rows),planned=planned,
                             rate=sum(r['action']=='cooperate' for r in rows)/len(rows)))
    attempt_counts=defaultdict(int)
    for a in trace['attempts']:
        if a['player']==0:attempt_counts[a['status']]+=1
    return dict(manifest=trace['manifest'],summary=summary,episodes=episodes,pairs=pairs,
                contrasts=contrasts,timeline=timeline,choices=choices,
                counts=dict(planned_games=len(specs),complete_games=sum(r['status']=='complete' for r in specs.values()),
                            planned_model_decisions=30*len(specs),scored_model_decisions=len(choices),
                            model_attempts=dict(attempt_counts)))


def write_csv(path,rows):
    if not rows:raise ValueError('No rows to export')
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def figures(report,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    colors={'neutral':'#117d83','promise':'#c66a36'}
    models=sorted({r['model'] for r in report['timeline']})
    fig,axes=plt.subplots(1,2,figsize=(10,4.4),sharey=True)
    for ax,model in zip(axes,models):
        for condition in colors:
            rows=[r for r in report['summary'] if r['model']==model and r['condition']==condition and r['order']=='all' and r['window'] in ('before','after_evidence')]
            rates={r['window']:r['rate'] for r in rows}
            y=[rates['before'],rates['after_evidence']]
            offset=-.035 if condition=='neutral' else .035
            x=[offset,1+offset]
            ax.plot(x,y,'o-',color=colors[condition],label=condition.title(),lw=2,ms=7)
            for xi,yi in zip(x,y):
                ax.annotate(f'{yi:.1%}',(xi,yi),xytext=(0,-22 if condition=='neutral' else 13),
                            textcoords='offset points',ha='center',color=colors[condition],fontsize=10)
        ax.set(title=model,xticks=[0,1],xticklabels=['Before\nRounds 1–10','After evidence\nRounds 12–30'],xlim=(-.28,1.28),ylim=(-.13,1.15))
        ax.set_yticks([0,.25,.5,.75,1]);ax.yaxis.set_major_formatter(PercentFormatter(1));ax.grid(axis='y',alpha=.2)
        for spine in ('top','right'):ax.spines[spine].set_visible(False)
    axes[0].set_ylabel('Cooperative choices');axes[1].legend(loc='upper center',bbox_to_anchor=(.5,1.32),ncol=2,frameon=False)
    fig.suptitle('Does the promise–neutral difference change after a broken promise?',fontsize=13,y=.99)
    fig.subplots_adjust(left=.08,right=.98,bottom=.19,top=.75,wspace=.12)
    for ext in ('png','svg'):fig.savefig(out/f'before_after.{ext}',dpi=160,facecolor='white')
    plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(10,6),sharex=True,sharey=True)
    for ax,model in zip(axes,models):
        ax.axvspan(10.5,11.5,color='#e5e5e5');ax.axvline(11.5,color='#68787d',linestyle=':',lw=1)
        for condition in colors:
            rows=sorted([r for r in report['timeline'] if r['model']==model and r['condition']==condition],key=lambda r:r['trial'])
            ax.plot([r['trial'] for r in rows],[r['rate'] for r in rows],marker='.',label=condition.title(),color=colors[condition],lw=1.6)
        ax.set(title=model,ylim=(-.05,1.05),yticks=[0,.5,1]);ax.yaxis.set_major_formatter(PercentFormatter(1));ax.grid(axis='y',alpha=.2)
        ax.set_ylabel('Cooperation')
    axes[0].legend(ncol=2,frameon=False);axes[1].set(xlabel='Round',xticks=[1,5,10,11,12,15,20,25,30])
    fig.suptitle('First defection: round 11 · first opportunity to react: round 12',fontsize=13)
    fig.tight_layout(rect=(0,0,1,.95))
    for ext in ('png','svg'):fig.savefig(out/f'by_round.{ext}',dpi=160,facecolor='white')
    plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('db',type=Path);parser.add_argument('--out',type=Path,default=Path('results/communication'));args=parser.parse_args()
    with closing(connect(args.db.resolve(),readonly=True)) as db:
        db.execute('BEGIN');verified=replay(db);trace=export_data(db)
    report=analyze(trace);report['replay']=verified
    args.out.mkdir(parents=True,exist_ok=True)
    for key in ('summary','episodes','pairs','contrasts','timeline','choices'):write_csv(args.out/f'{key}.csv',report[key])
    encoded=json.dumps(report,indent=2,allow_nan=False)
    (args.out/'report.json').write_text(encoded+'\n')
    browser={k:v for k,v in report.items() if k not in ('manifest','episodes','choices')}
    (args.out/'data.js').write_text('window.COMMUNICATION_DATA = '+json.dumps(browser,allow_nan=False)+';\n')
    (args.out/'trace.json').write_text(json.dumps(trace,indent=2,allow_nan=False)+'\n')
    if report['counts']['scored_model_decisions']==report['counts']['planned_model_decisions']:figures(report,args.out)
    evidence={'trace_sha256':hashlib.sha256((args.out/'trace.json').read_bytes()).hexdigest(),'analysis_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'replay':verified,'counts':report['counts']}
    (args.out/'evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps({'counts':report['counts'],'contrasts':report['contrasts']},indent=2))

if __name__=='__main__':main()
