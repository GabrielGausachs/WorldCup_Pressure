
import os
from Utils.feature_extraction import build_global_player_mapping, compute_minutes_all_games, map_position


def clean_missing_rows(passes_df, tracking_passes_df):
    # Clean passes_df by removing rows where pressure_on_receiver is NaN
    mask = passes_df['pressure_on_receiver'].isna()
    passes_df_clean = passes_df[~mask]

    # Clean tracking_passes_df by removing rows that correspond to the NaN pressure_on_receiver rows in passes_df
    keys = ["gameId", "gameEventId", "possessionEventId"]

    pressure_nan_rows = passes_df[passes_df['pressure_on_receiver'].isna()]
    nan_keys = pressure_nan_rows[keys]

    # remove from tracking_passes_df
    tracking_passes_df_clean = tracking_passes_df.merge(
        nan_keys,
        left_on=["game_id", "game_event_id", "possession_event_id"],
        right_on=keys,
        how="left",
        indicator=True
    )

    tracking_passes_df_clean = tracking_passes_df_clean[
        tracking_passes_df_clean["_merge"] == "left_only"
    ].drop(columns=keys + ["_merge"])

    print(len(passes_df) - len(passes_df_clean))
    print(len(tracking_passes_df) - len(tracking_passes_df_clean))

    passes_df = passes_df_clean
    tracking_passes_df = tracking_passes_df_clean
    print(f"Final passes DataFrame shape: {passes_df.shape}")
    print(f"Final tracking passes DataFrame shape: {tracking_passes_df.shape}")

    return passes_df, tracking_passes_df

def add_minutes_context(base_path, passes_df):
    # Get minutes played for each player in each game and the total match minutes for each game
    minutes_df = compute_minutes_all_games(base_path)

    # Merge minutes_df with passes_df to get minutes played and total match minutes for each pass
    passes_df = passes_df.merge(minutes_df, on=["gameId", "possessionEvents.targetPlayerId"], how="left")
    print(passes_df.shape)

    return passes_df

def map_positions(base_path, passes_df):
    roster_files = [os.path.join(base_path, "rosters", f) for f in os.listdir(os.path.join(base_path, "rosters")) if f.endswith('.json')]
    global_player_mapping = build_global_player_mapping(roster_files)
    passes_df['positionGroupType'] = passes_df['possessionEvents.targetPlayerId'].map(global_player_mapping)
    passes_df['positionGroup'] = passes_df['positionGroupType'].apply(map_position)

    return passes_df