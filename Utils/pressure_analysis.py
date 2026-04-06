from scipy.stats import pointbiserialr
import os
from Utils.feature_extraction import player_position_mapping

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

def target_pressure_players(dict_events, passes_df, base_path):
    for game_id in dict_events.keys():
        passes_df = player_position_mapping(os.path.join(base_path,"rosters",f"{game_id}.json"), passes_df)
    target_player_pass_counts = passes_df.groupby('possessionEvents.targetPlayerName').agg(
    pass_count=('possessionEventId', 'count'),
    avg_pressure=('pressure_on_receiver', 'mean'),
    position = ('positionGroupType', 'first')
    ).reset_index()
    return target_player_pass_counts