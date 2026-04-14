from scipy.stats import pointbiserialr
from itertools import combinations
import pandas as pd
import os

def stats_passes(passes_df):
    # Total passes
    total_passes = passes_df.shape[0]

    # Successful / unsuccessful passes
    successful_passes = passes_df[passes_df['possessionEvents.passOutcomeType'] == "C"].shape[0]
    unsuccessful_passes = passes_df[passes_df['possessionEvents.passOutcomeType'] != "C"].shape[0]

    # Ratios
    ratio_successful = successful_passes / total_passes if total_passes > 0 else 0
    ratio_unsuccessful = unsuccessful_passes / total_passes if total_passes > 0 else 0

    # Pressure summary
    summary = passes_df.groupby(passes_df['possessionEvents.passOutcomeType'] == "C")['pressure_on_receiver'].agg(['mean', 'std'])
    summary_formatted = summary.apply(lambda row: f"{row['mean']:.2f} ± {row['std']:.2f}", axis=1)

    # Print
    print(f"Total passes: {total_passes}")
    print(f"Successful passes: {successful_passes} ({ratio_successful:.2%}) - Mean pressure: {summary_formatted[True]}")
    print(f"Unsuccessful passes: {unsuccessful_passes} ({ratio_unsuccessful:.2%}) - Mean pressure: {summary_formatted[False]}")

    # Continuous variable
    pressure = passes_df['pressure_on_receiver']

    # Binary variable: 1 = successful, 0 = unsuccessful
    success_binary = (passes_df['possessionEvents.passOutcomeType'] == "C").astype(int)

    r, p_value = pointbiserialr(success_binary, pressure)
    print(f"Point Biserial Correlation: R = {r:.2f}, p = {p_value:.6f}")

def player_stats(passes_df):
    minutes_per_player = passes_df[
    ["gameId", "possessionEvents.targetPlayerName", "minutes_played"]
    ].drop_duplicates()

    minutes_per_player = minutes_per_player.groupby(
        "possessionEvents.targetPlayerName"
    )["minutes_played"].sum().reset_index(name="total_minutes")

    # Aggregate stats per player
    player_stats = passes_df.groupby('possessionEvents.targetPlayerName').agg(
    pass_count=('possessionEventId', 'count'),
    avg_pressure=('pressure_on_receiver', 'mean'),
    position=('positionGroupType', 'first'),
    position_group=('positionGroup', 'first'),
    n_games=('gameId', 'nunique'),
    team_name=('gameEvents.teamName', 'first')
    ).reset_index()

    player_stats = player_stats.merge(
    minutes_per_player,
    on="possessionEvents.targetPlayerName",
    how="left"
    )

    # Filter players with at least 3 games and an average of more than 60 minutes per game
    player_stats = player_stats[
    (player_stats["n_games"] >= 3) &
    (player_stats["total_minutes"] / player_stats["n_games"] > 60)
    ].copy()

    # Calculate targeted passes per 90 minutes
    player_stats["targeted_passes_per90"] = (
        player_stats["pass_count"] / player_stats["total_minutes"]
    ) * 90

    # Calculate stats for successful passes only
    successful_passes = passes_df[passes_df['possessionEvents.passOutcomeType'] == "C"]
    
    successful_passes = successful_passes.copy()
    if "ball_lost_after" in successful_passes.columns:
        successful_passes["ball_lost_after"] = successful_passes["ball_lost_after"].fillna(False).astype(bool)
    else:
        successful_passes["ball_lost_after"] = False
    successful_passes["ball_retained_after"] = ~successful_passes["ball_lost_after"]

    for col in ["attacking_third_entry", "box_entry", "shot_or_cross_after"]:
        if col in successful_passes.columns:
            successful_passes[col] = successful_passes[col].fillna(False).astype(bool)
        else:
            successful_passes[col] = False

    successful_stats = successful_passes.groupby('possessionEvents.targetPlayerName').agg(
        successful_pass_count=('possessionEventId', 'count'),
        avg_pressure_successful=('pressure_on_receiver', 'mean'),
        possessions_lost=('ball_lost_after', 'sum'),
        possessions_retained=('ball_retained_after', 'sum'),
        attacking_third_entry_count=('attacking_third_entry', 'sum'),
        box_entry_count=('box_entry', 'sum'),
        shot_or_cross_after_count=('shot_or_cross_after', 'sum')
    ).reset_index()
    
    player_stats = player_stats.merge(
        successful_stats,
        on="possessionEvents.targetPlayerName",
        how="left"
    )
    
    # Calculate successful targeted passes per 90 minutes
    player_stats["successful_passes_per90"] = (
        player_stats["successful_pass_count"] / player_stats["total_minutes"]
    ) * 90

    # Per-100 metrics based on successful passes
    player_stats["possessions_lost_per_100_successful_passes"] = (
        player_stats["possessions_lost"] / player_stats["successful_pass_count"]
    ) * 100
    player_stats["possessions_retained_per_100_successful_passes"] = (
        player_stats["possessions_retained"] / player_stats["successful_pass_count"]
    ) * 100
    player_stats["net_possession_ratio"] = (
        player_stats["possessions_retained_per_100_successful_passes"]
        - player_stats["possessions_lost_per_100_successful_passes"]
    )
    player_stats["attacking_third_entry_per_100_successful_passes"] = (
        player_stats["attacking_third_entry_count"] / player_stats["successful_pass_count"]
    ) * 100
    player_stats["box_entry_per_100_successful_passes"] = (
        player_stats["box_entry_count"] / player_stats["successful_pass_count"]
    ) * 100
    player_stats["shot_or_cross_after_per_100_successful_passes"] = (
        player_stats["shot_or_cross_after_count"] / player_stats["successful_pass_count"]
    ) * 100

    percentile_columns = [
        "possessions_lost_per_100_successful_passes",
        "possessions_retained_per_100_successful_passes",
        "net_possession_ratio",
        "attacking_third_entry_per_100_successful_passes",
        "box_entry_per_100_successful_passes",
        "shot_or_cross_after_per_100_successful_passes",
    ]

    for column in percentile_columns:
        player_stats[f"{column}_percentile_in_position_group"] = player_stats.groupby(
            "position_group"
        )[column].transform(lambda series: series.rank(pct=True, method="average") * 100)

    player_stats = player_stats.dropna(
        subset=[
            "avg_pressure",
            "targeted_passes_per90",
            "avg_pressure_successful",
            "successful_passes_per90"
        ]
    )

    return player_stats


def identify_similar_players_with_divergent_net_ratio(
    player_stats_df,
    max_avg_pressure_diff=0.05,
    max_successful_passes_per90_diff=0.5,
    min_net_possession_ratio_diff=20.0,
    position_groups=None,
    top_n=10,
):
    required_columns = [
        "possessionEvents.targetPlayerName",
        "position_group",
        "avg_pressure",
        "successful_passes_per90",
        "net_possession_ratio",
    ]
    missing_columns = [column for column in required_columns if column not in player_stats_df.columns]
    if missing_columns:
        raise ValueError(f"player_stats_df is missing required columns: {missing_columns}")

    comparison_df = player_stats_df.copy()
    if position_groups is not None:
        comparison_df = comparison_df[comparison_df["position_group"].isin(position_groups)].copy()

    comparison_df = comparison_df.dropna(subset=required_columns).copy()

    candidate_rows = []
    for position_group, group_df in comparison_df.groupby("position_group"):
        group_df = group_df.reset_index(drop=True)
        if len(group_df) < 2:
            continue

        for left_index, right_index in combinations(group_df.index, 2):
            left_row = group_df.loc[left_index]
            right_row = group_df.loc[right_index]

            avg_pressure_diff = abs(left_row["avg_pressure"] - right_row["avg_pressure"])
            successful_passes_diff = abs(left_row["successful_passes_per90"] - right_row["successful_passes_per90"])
            net_possession_ratio_diff = abs(left_row["net_possession_ratio"] - right_row["net_possession_ratio"])

            if (
                avg_pressure_diff <= max_avg_pressure_diff
                and successful_passes_diff <= max_successful_passes_per90_diff
                and net_possession_ratio_diff >= min_net_possession_ratio_diff
            ):
                candidate_rows.append({
                    "position_group": position_group,
                    "player_1": left_row["possessionEvents.targetPlayerName"],
                    "player_2": right_row["possessionEvents.targetPlayerName"],
                    "team_1": left_row.get("team_name", None),
                    "team_2": right_row.get("team_name", None),
                    "avg_pressure_1": left_row["avg_pressure"],
                    "avg_pressure_2": right_row["avg_pressure"],
                    "avg_pressure_diff": avg_pressure_diff,
                    "successful_passes_per90_1": left_row["successful_passes_per90"],
                    "successful_passes_per90_2": right_row["successful_passes_per90"],
                    "successful_passes_per90_diff": successful_passes_diff,
                    "net_possession_ratio_1": left_row["net_possession_ratio"],
                    "net_possession_ratio_2": right_row["net_possession_ratio"],
                    "net_possession_ratio_diff": net_possession_ratio_diff,
                    "similarity_score": avg_pressure_diff + successful_passes_diff,
                })

    if not candidate_rows:
        return pd.DataFrame(columns=[
            "position_group",
            "player_1",
            "player_2",
            "team_1",
            "team_2",
            "avg_pressure_1",
            "avg_pressure_2",
            "avg_pressure_diff",
            "successful_passes_per90_1",
            "successful_passes_per90_2",
            "successful_passes_per90_diff",
            "net_possession_ratio_1",
            "net_possession_ratio_2",
            "net_possession_ratio_diff",
            "similarity_score",
        ])

    result_df = pd.DataFrame(candidate_rows)
    result_df = result_df.sort_values(
        ["similarity_score", "net_possession_ratio_diff"],
        ascending=[True, False]
    ).head(top_n).reset_index(drop=True)

    return result_df


def extract_highlight_players_from_pairs(similar_players_df):
    if similar_players_df is None or similar_players_df.empty:
        return []

    required_columns = ["player_1", "player_2"]
    missing_columns = [column for column in required_columns if column not in similar_players_df.columns]
    if missing_columns:
        raise ValueError(f"similar_players_df is missing required columns: {missing_columns}")

    highlight_players = pd.unique(
        pd.concat(
            [similar_players_df["player_1"], similar_players_df["player_2"]],
            ignore_index=True
        ).dropna()
    ).tolist()

    return highlight_players
    
