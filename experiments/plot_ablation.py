"""Vẽ diễn biến điểm D của hai ví dụ đối chứng có kết quả trái chiều."""

import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'experiments/ablation_results/mechanisms.json').read_text(encoding='utf8'))
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10})
fig,axes=plt.subplots(1,2,figsize=(9,3.4),sharey=True)
for ax,name,title in zip(axes,['generated_8_42000','generated_16_42000'],
                        ['8×8, seed 42000: phối hợp tăng điểm','16×16, seed 42000: phối hợp giảm điểm']):
    for method,label,style,marker in [('independent','Lập tuyến độc lập','--','o'),
                                     ('coordinated','Phối hợp chọn mục tiêu','-','s')]:
        values=[0]+[r['score'][1] for r in data[name][method]]
        ax.plot(range(5),values,color='black',linestyle=style,marker=marker,label=label)
    ax.set_title(title,fontsize=10)
    ax.set_xlabel('Ngày đã hoàn tất')
    ax.set_xticks(range(5))
    ax.grid(alpha=.3)
axes[0].set_ylabel('Tổng số loại qua các ngày D')
axes[0].legend(fontsize=8,loc='upper left')
fig.tight_layout()
fig.savefig(ROOT/'docs/figures/ablation_daily_types.png',dpi=200,bbox_inches='tight')
