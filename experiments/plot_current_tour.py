"""Vẽ diễn biến của riêng phương pháp hiện tại từ kết quả BTC đã lưu."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]


def main():
    rows=json.loads((ROOT/'experiments/tour_api_evidence/summary.json').read_text(encoding='utf8'))
    row=next(r for r in rows if r['case']=='Q01')
    plt.rcParams.update({'font.family':'DejaVu Serif','font.size':10})
    fig,axes=plt.subplots(1,2,figsize=(9,3.2))
    days=range(1,11)
    axes[0].plot(days,row['daily_types'],marker='o',color='#235789',label='Loại thu được/ngày')
    axes[0].axhline(row['ud_bound'][0],color='gray',linestyle=':',label='Cận số loại/ngày')
    axes[0].set_ylim(0,22)
    axes[0].set_ylabel('Số loại udon')
    axes[0].legend(fontsize=8,loc='lower right')
    total=0; cumulative=[]
    for value in row['daily_servings']:
        total+=value;cumulative.append(total)
    axes[1].plot(days,cumulative,marker='s',color='#235789')
    axes[1].set_ylabel('Tổng số suất tích lũy')
    for ax in axes:
        ax.set_xlabel('Ngày');ax.set_xticks(list(days));ax.grid(alpha=.25)
    fig.tight_layout()
    fig.savefig(ROOT/'docs/figures/tour_current_q01.png',dpi=200)
    plt.close(fig)


if __name__=='__main__':main()
