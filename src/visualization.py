"""Boxplots mensais: um K/D agregado por jogador em cada caixa."""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

MONTHS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def plot_monthly(monthly, stats, path, *, title, period_label, source_label,
                 highlight_id=None, min_matches=1):
    # Contrato: distribuição entre jogadores por mês; duas cores, azul e ouro.
    # A caixa usa quartis lineares; bigodes chegam às observações dentro dos limites.
    fig, ax = plt.subplots(figsize=(12, 6.8))
    blue, fill, ink, gold = "#245F9B", "#DCE8F3", "#25313D", "#B07713"
    labels, highlight_label = [], None
    for position, row in enumerate(stats.to_dict("records"), start=1):
        group = monthly.loc[monthly["month"].eq(row["month"])]
        values = group["kd"].dropna().to_numpy(dtype=float)
        if len(values):
            inside = values[(values >= row["lower_bound"]) & (values <= row["upper_bound"])]
            summary = dict(q1=row["q1"], med=row["median"], q3=row["q3"],
                           whislo=float(inside.min()), whishi=float(inside.max()), fliers=[])
            ax.bxp([summary], positions=[position], widths=.46, patch_artist=True,
                   showfliers=False, manage_ticks=False,
                   boxprops={"facecolor": fill, "edgecolor": blue, "linewidth": 1.5},
                   medianprops={"color": ink, "linewidth": 2},
                   whiskerprops={"color": blue, "linewidth": 1.3},
                   capprops={"color": blue, "linewidth": 1.3})
            fliers = group.loc[group["classification"].isin(["outlier_positivo", "outlier_negativo"]), "kd"]
            ax.scatter(np.full(len(fliers), position), fliers, facecolors="none",
                       edgecolors=blue, s=36, linewidths=1.3, zorder=3)
            if highlight_id:
                focus = group.loc[group["player_id"].eq(highlight_id) & group["kd"].notna()]
                if len(focus):
                    ax.scatter([position], focus["kd"], marker="D", color=gold,
                               edgecolors="white", s=62, linewidths=.7, zorder=4)
                    highlight_label = str(focus.iloc[0]["player"])
            if not row["classification_enabled"]:
                ax.text(position, .02, "amostra pequena", transform=ax.get_xaxis_transform(),
                        ha="center", va="bottom", fontsize=8, color=ink)
        else:
            ax.text(position, .5, "Sem dados\nválidos", transform=ax.get_xaxis_transform(),
                    ha="center", color="#697580", fontsize=10)
        year, month = row["month"].split("-")
        labels.append(f"{MONTHS[int(month)-1]}/{year[-2:]}\nn={row['analyzed_players']} · j={row['player_matches']}")
    ax.set_xticks(range(1, len(labels) + 1), labels, color=ink)
    ax.set_xlim(.45, len(labels) + .55)
    ax.set_ylim(bottom=0)
    ax.set_ylabel("K/D mensal · total de kills / total de deaths", color=ink, labelpad=12)
    ax.grid(axis="y", color="#E4E8EC", linewidth=.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#B9C2CA")
    fig.text(.09, .945, title,
             fontsize=17, weight="bold", color=ink)
    fig.text(.09, .898, period_label,
             fontsize=10, color="#56616C")
    fig.text(.09, .862, f"Grupo fixo: {int(stats['cohort_players'].max())} jogadores · um valor por jogador/mês · mínimo: {min_matches} partida(s)",
             fontsize=10, color="#56616C")
    handles = [Line2D([], [], marker="o", color=blue, markerfacecolor="none", linestyle="none", label="Outlier mensal · 1,5 × IQR")]
    if highlight_label:
        handles.append(Line2D([], [], marker="D", color=gold, linestyle="none", label=highlight_label))
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0, 1.10),
              frameon=False, fontsize=9, ncol=2)
    fig.text(.09, .08, "n = jogadores com K/D válido · j = participações jogador-partida · meses de borda podem ser parciais",
             fontsize=9, color="#56616C")
    fig.text(.09, .045, source_label, fontsize=9, color="#56616C")
    fig.subplots_adjust(left=.09, right=.97, bottom=.18, top=.76)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=170, facecolor="white")
    return fig

