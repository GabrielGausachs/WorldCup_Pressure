from scipy.stats import pointbiserialr
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

def target_pressure_players(passes_df):
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
    n_games=('gameId', 'nunique')
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

    player_stats = player_stats.dropna(subset=["avg_pressure", "targeted_passes_per90"])

    return player_stats
    
