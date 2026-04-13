import re
import matplotlib.pyplot as plt

def avg_pressure_targeted_players(player_stats, highlight_players=None):
    
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 11,
        "axes.titlesize": 16,
        "axes.titleweight": "bold",
        "axes.labelsize": 12,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10
    })


    player_name_col = "possessionEvents.targetPlayerName"

    colors = {
        "Goalkeeper": "orange",
        "Defender": "blue",
        "Midfielder": "green",
        "Forward": "red"
    }

    order = ["Goalkeeper", "Defender", "Midfielder", "Forward"]

    fig = plt.figure(figsize=(10, 6), facecolor="#f5f1e6")
    ax = plt.gca()
    ax.set_facecolor("#f5f1e6")

    # 1. Normal players (transparent)
    for pos in order:
        group = player_stats[player_stats["position_group"] == pos]

        plt.scatter(
            group["targeted_passes_per90"],
            group["avg_pressure"],
            color=colors.get(pos, "gray"),
            alpha=0.4,
            s=60,
            edgecolors="black",
            linewidth=0.5,
            label=pos
        )


    highlight_df = player_stats[player_stats[player_name_col].isin(highlight_players)].copy()

    plt.scatter(
        highlight_df["targeted_passes_per90"],
        highlight_df["avg_pressure"],
        c=highlight_df["position_group"].map(colors),
        s=60,
        alpha=1,
        edgecolors="black",
        linewidth=1,
        zorder=10
    )


    # 3. Style (only left + bottom axis)
    ax = plt.gca()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # 4. Legend (forced correct order)
    handles, labels = ax.get_legend_handles_labels()
    label_to_handle = dict(zip(labels, handles))
    ordered_handles = [label_to_handle[pos] for pos in order if pos in label_to_handle]

    legend = plt.legend(
        ordered_handles,
        order,
        fontsize=9,
        title="Position Group",
        title_fontsize=10,
        loc="upper right",
        bbox_to_anchor=(1, 0.95),
        frameon=True
    )

    frame = legend.get_frame()
    frame.set_facecolor("none")
    frame.set_edgecolor("none")
    frame.set_alpha(0)

    plt.title("Who Teams Still Target Under Pressure", fontsize=15, fontweight="bold", pad=15)

    plt.suptitle(
        "Receiver pressure intensity and targeted passes per 90min by positional group",
        fontsize=10,
        y=0.9,
    )

    ax = plt.gca()
    ax.set_xlabel("Targeted Passes per 90", fontsize=12, labelpad=10)
    ax.set_ylabel("Average Pressure per Pass", fontsize=12, labelpad=10)

    plt.grid(False)
    plt.show()