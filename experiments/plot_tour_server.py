"""Vẽ đối chứng Q01 từ số liệu ngày đã được BTC xử lý."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]


def main():
    base=json.loads((ROOT/'experiments/tour_results/server_baseline.json').read_text(encoding='utf8'))['Q01']
    new=next(r for r in json.loads((ROOT/'experiments/tour_api_evidence/summary.json').read_text(encoding='utf8')) if r['case']=='Q01')
    plt.rcParams.update({'font.family':'DejaVu Serif','font.size':10})
    fig,axes=plt.subplots(1,2,figsize=(9,3.2))
    days=range(1,11)
    for name,values,marker in [('Greedy',base,'o'),('Lập tuyến cả đội',new,'s')]:
        axes[0].plot(days,values['daily_types'],marker=marker,label=name)
        total=0; cumulative=[]
        for value in values['daily_servings']:
            total+=value;cumulative.append(total)
        axes[1].plot(days,cumulative,marker=marker,label=name)
    axes[0].axhline(20,color='gray',linestyle=':',label='Cận 20 loại/ngày')
    axes[0].set_ylabel('Số loại thu được trong ngày')
    axes[1].set_ylabel('Tổng số suất tích lũy')
    for ax in axes:
        ax.set_xlabel('Ngày');ax.set_xticks(list(days));ax.grid(alpha=.25);ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(ROOT/'docs/figures/tour_server_q01.png',dpi=200)
    plt.close(fig)


if __name__=='__main__':main()
