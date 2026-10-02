"""Figura científica: oito distribuições semanais e destaque do donk."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


def weekly_boxplot(weekly, summary, output, snapshot_date, highlight_id, min_matches=1):
    output=Path(output)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titleweight':'bold','svg.fonttype':'none'})
    fig,ax=plt.subplots(figsize=(15,8.2))
    ink,blue,fill,gold='#182A3A','#326A98','#D9E7F0','#C57515'
    labels=[]
    highlighted=weekly.loc[weekly.player_id.eq(highlight_id)]
    for row in summary.to_dict('records'):
        week=int(row['week']);group=weekly.loc[weekly.week.eq(week)]
        values=group.kd.dropna().to_numpy()
        if len(values):
            inside=values[(values>=row['lower_bound'])&(values<=row['upper_bound'])]
            # Com amostras muito pequenas os bigodes não podem ultrapassar os quartis.
            low=float(inside.min()) if len(inside) else float(row['q1'])
            high=float(inside.max()) if len(inside) else float(row['q3'])
            ax.bxp([{'q1':row['q1'],'med':row['median'],'q3':row['q3'],'whislo':low,'whishi':high,'fliers':[]}],
                   positions=[week],widths=.48,patch_artist=True,showfliers=False,manage_ticks=False,
                   boxprops={'facecolor':fill,'edgecolor':blue,'linewidth':1.7},
                   medianprops={'color':ink,'linewidth':2},whiskerprops={'color':blue},capprops={'color':blue})
            unusual=group.loc[group.classification.isin(['outlier_positivo','outlier_negativo']) & group.player_id.ne(highlight_id),'kd']
            ax.scatter(np.full(len(unusual),week),unusual,s=28,facecolors='none',edgecolors=blue,linewidths=1,alpha=.7,zorder=3)
        focus=highlighted.loc[highlighted.week.eq(week)]
        if len(focus) and pd.notna(focus.iloc[0].kd):
            value=float(focus.iloc[0].kd)
            ax.scatter([week],[value],s=85,marker='D',color=gold,edgecolors='white',linewidths=1,zorder=5)
            ax.annotate(f"{value:.2f}".replace('.',','),(week,value),xytext=(0,12),textcoords='offset points',ha='center',color=gold,weight='bold',fontsize=10)
            note=f"donk: {int(focus.iloc[0].matches)} jogos"
        else:
            note='donk: dados incompletos' if len(focus) and focus.iloc[0].status=='dados_incompletos' else 'donk: sem valor elegível'
        ax.text(week,1.025,note,transform=ax.get_xaxis_transform(),ha='center',fontsize=8,color=gold)
        dates=group.iloc[0]
        lo=pd.Timestamp(dates.week_start_utc).strftime('%d/%m')
        hi=(pd.Timestamp(dates.week_end_utc)-pd.Timedelta(days=1)).strftime('%d/%m')
        labels.append(f"S{week} · {lo}–{hi}\nn = {row['analyzed_players']}")
    ax.set_xticks(range(1,len(labels)+1),labels)
    ax.set_xlim(.4,len(labels)+.6)
    ax.set_ylim(bottom=0)
    # Reserva espaço acima do maior ponto para o rótulo do destaque.
    ymax=weekly.kd.max()
    if pd.notna(ymax):ax.set_ylim(0,max(2,float(ymax)*1.15))
    ax.set_ylabel('K/D semanal = total de kills ÷ total de deaths',labelpad=14,color=ink)
    ax.grid(axis='y',color='#E4EBF0',linewidth=.8);ax.set_axisbelow(True)
    for side in ['top','right']:ax.spines[side].set_visible(False)
    for side in ['bottom','left']:ax.spines[side].set_color('#B7C4CD')
    ax.legend(handles=[Line2D([],[],marker='D',linestyle='none',color=gold,label='donk666'),
                       Line2D([],[],marker='o',linestyle='none',color=blue,markerfacecolor='none',label='Outliers: além de 1,5 × IQR')],
              loc='upper left',bbox_to_anchor=(0,1.17),frameon=False,ncol=2,fontsize=10)
    fig.text(.08,.946,'Donk entre os top 500 EU',fontsize=23,weight='bold',color=ink)
    fig.text(.08,.904,f'Season 9 · oito semanas de 05/08 a 29/09/2026 · grupo fixado em {snapshot_date} (UTC)',fontsize=11,color='#526675')
    fig.text(.08,.104,f'Cada jogador tem peso igual na caixa · mínimo: {min_matches} partida(s) por semana · n = jogadores com K/D elegível',fontsize=10,color='#526675')
    fig.text(.08,.068,'Semanas com estatísticas faltantes são excluídas para aquele jogador. A lista representa o ranking na coleta.',fontsize=9,color='#526675')
    fig.text(.08,.037,'Fonte: FACEIT Data API · partidas 5v5 de matchmaking · ver método e cobertura no relatório.',fontsize=9,color='#526675')
    fig.subplots_adjust(left=.08,right=.975,top=.735,bottom=.20)
    output.parent.mkdir(parents=True,exist_ok=True)
    for extension in ['png','svg','pdf']:
        fig.savefig(output.with_suffix('.'+extension),dpi=220,facecolor='white')
    return fig
