import json
import numpy as np
import pandas as pd
from Utils.logger import get_logger

logger = get_logger()

def get_passes(event_df, tracking_df):
    # Filter the event DataFrame to include only rows where:
    # - possessionEvents.passerPlayerName is not null
    # - possessionEvents.passOutcomeType is not null
    # - possessionEvents.targetPlayerName is not null
    passes = event_df[
        (event_df['possessionEvents.passerPlayerName'].notnull()) &
        (event_df['possessionEvents.passOutcomeType'].notnull()) &
        (event_df['possessionEvents.targetPlayerName'].notnull())
    ].copy()

    tracking_passes = tracking_df[
        tracking_df["possession_event"].apply(
            lambda x: isinstance(x, dict) and x.get("possession_event_type") == "PA"
        )
    ].copy()

    # only keep the rows in passes where the possessionEventId is in the tracking_passes possession_event_id
    passes = passes[passes['possessionEventId'].isin(tracking_passes['possession_event_id'])]

    # Common pairs
    pairs_passes = passes[['possessionEventId', 'gameEventId']].drop_duplicates()
    pairs_tracking = tracking_passes[
        ['possession_event_id', 'game_event_id']
    ].drop_duplicates().rename(columns={
        'possession_event_id': 'possessionEventId',
        'game_event_id': 'gameEventId'
    })
    common_pairs = pairs_passes.merge(
        pairs_tracking,
        on=['possessionEventId', 'gameEventId'],
        how='inner'
    )
    passes_clean = passes.merge(
        common_pairs,
        on=['possessionEventId', 'gameEventId'],
        how='inner'
    )

    tracking_passes_clean = tracking_passes.merge(
        common_pairs.rename(columns={
            'possessionEventId': 'possession_event_id',
            'gameEventId': 'game_event_id'
        }),
        on=['possession_event_id', 'game_event_id'],
        how='inner'
    )

    # if possessionEvents.passOutcomeType is "C", then is_success is True, otherwise False
    passes_clean['is_success'] = passes_clean['possessionEvents.passOutcomeType'].apply(lambda x: True if x == "C" else False)
    
    logger.info(f"Number of successful passes: {passes_clean['is_success'].sum()}")

    return passes_clean, tracking_passes_clean



def get_pass_frame(tracking_passes_df):
    tracking_passes_df["possession_start_frame"] = tracking_passes_df["possession_event"].apply(
        lambda x: x.get("start_frame") if isinstance(x, dict) else None)
    return tracking_passes_df



def pressure_on_receiver(passes_df, tracking_passes_df, game):
    tracking_passes_df = get_pass_frame(tracking_passes_df)
    passes_df["pressure_on_receiver"] = np.nan  # Initialize the pressure column with NaN values
    for idx, row in tracking_passes_df.iterrows():

        # Get the start frame of the possession event for this pass
        possession_start_frame = row.get("possession_start_frame")
        game_id = row.get("gameRefId")
        
        # Get the receiver's name from the event data using the possession_event_id
        possession_event_id = row["possession_event_id"]
        try:
            if isinstance(possession_event_id, float):
                target_player_id = passes_df[passes_df['possessionEventId'] == possession_event_id]['possessionEvents.targetPlayerId'].iloc[0]
                home_team = passes_df[passes_df['possessionEventId'] == possession_event_id]['gameEvents.homeTeam'].iloc[0]
                # Find the player shirt_num
                if home_team:
                    player_info = game.home_players[game.home_players["id"].astype(int) == int(target_player_id)]
                    if player_info.empty:
                        logger.error(f"Player {target_player_id} not found in home team for possession event ID: {possession_event_id}")
                else:
                    player_info = game.away_players[game.away_players["id"].astype(int) == int(target_player_id)]
                    if player_info.empty:
                        logger.error(f"Player {target_player_id} not found in away team for possession event ID: {possession_event_id}")
                player_id = player_info["id"].iloc[0]

                # Get the pressure on the target player at the start frame
                idx = game.tracking_data[game.tracking_data["frame"] == int(possession_start_frame)].index[0]
                try:
                    pressure = game.tracking_data.get_pressure_on_player(index=idx, column_id=game.player_id_to_column_id(player_id), pitch_size=game.pitch_dimensions)

                except Exception as e:
                    logger.error(f"Error occurred while calculating pressure for possession event ID: {possession_event_id}, Error: {e}")
                    continue

                # Add pressure in the passes_df for the corresponding possession_event_id
                passes_df.loc[(passes_df['possessionEventId'] == possession_event_id), 'pressure_on_receiver'] = pressure / 100  # Convert to percentage
        except Exception as e:
            logger.error(f"Error occurred while processing possession event ID: {possession_event_id}, Error: {e}")
            continue
    
    # print number of rows in passes_df where pressure_on_receiver is still NaN
    logger.info(f"Number of rows in passes_df where pressure_on_receiver is NaN: {passes_df['pressure_on_receiver'].isna().sum()}")
    return passes_df



def build_global_player_mapping(roster_files):
    mapping = {}
    
    for file in roster_files:
        with open(file, 'r') as f:
            rosters_data = json.load(f)
        
        for p in rosters_data:
            mapping[float(p['player']['id'])] = p['positionGroupType']
    
    return mapping



def retain_lose_after_pass(passes_df, tracking_passes_df, tracking_df):
    # Get succesfull passes
    successfull_passes = passes_df[passes_df['is_success'] == True].copy()
    passes_df["ball_lost_after"] = False

    for idx, row in successfull_passes.iterrows():
        # get the row in the tracking_passes_df with the same possession_event_id as the current row in successfull_passes
        possession_event_id = row['possessionEventId']
        game_id = row['gameId']
        tracking_succ_pass = tracking_passes_df[tracking_passes_df['possession_event_id'] == possession_event_id].iloc[0]
        if not tracking_succ_pass.empty:
            possession_start_frame = tracking_succ_pass.get("possession_start_frame")

            # Get the next game_event_id
            game_event_id = tracking_succ_pass["game_event_id"]
            period = tracking_succ_pass["period"]
            subset = tracking_df[
                    (tracking_df["frameNum"] >= possession_start_frame) &
                    (tracking_df["period"] == period) & (tracking_df["game_event_id"] != game_event_id) & tracking_df["game_event_id"].notnull()
                ].copy()
            subset["team_name"] = subset["game_event"].apply(
                lambda x: x.get("team_name") if isinstance(x, dict) else None
            )
            subset["possession_event_type"] = subset["possession_event"].apply(
                lambda x: x.get("possession_event_type") if isinstance(x, dict) else None
            )
            if not subset.empty:
                # list of unique game_event_id in subset in order of appearance
                unique_game_event_ids = subset["game_event_id"].unique()
                # get the next and the second next game_event_id
                next_game_event_id = unique_game_event_ids[0]

                # get the rows of next_game_event_id
                subset_next_game_event = subset[subset["game_event_id"] == next_game_event_id]
                # if there is any row with possession_event_type equals to shot or cross, then we consider the pass as not lost
                if subset_next_game_event["possession_event_type"].isin(["SH", "CR"]).any():
                    continue
                
                second_next_game_event_id = unique_game_event_ids[1] if len(unique_game_event_ids) > 1 else None
                team_name = subset[subset['game_event_id'] == next_game_event_id]['team_name'].iloc[0]
                second_team_name = subset[subset['game_event_id'] == second_next_game_event_id]['team_name'].iloc[0] if second_next_game_event_id is not None else None
                if second_team_name != team_name and second_team_name is not None:
                    passes_df.loc[idx, "ball_lost_after"] = True
    return passes_df



def check_attacking_box(df, pitch_dims, home_team):
    # Vectorized check
    df['attacking_third'] = False
    df['in_box'] = False
    if home_team == 'home':
        df['attacking_third'] = df['ball_x'] > pitch_dims[0]*2/3
        df['in_box'] = df['ball_x'].between(36.0, 52.5) & df['ball_y'].between(-20.16, 20.16)
    else:
        df['attacking_third'] = df['ball_x'] < pitch_dims[0]/3
        df['in_box'] = df['ball_x'].between(-52.5, -36.0) & df['ball_y'].between(-20.16, 20.16)
    return df



def what_leads(passes_df, tracking_passes_df, tracking_df, game):
    successfull_retained_passes = passes_df[(passes_df['ball_lost_after'] == False) & (passes_df["is_success"] == True) & (passes_df["pressure_on_receiver"].notnull())].copy()
    passes_df["attacking_third_entry"] = False
    passes_df["box_entry"] = False
    passes_df["shot_or_cross_after"] = False

    for idx, row in successfull_retained_passes.iterrows():
        # get the row in the tracking_passes_df with the same possession_event_id as the current row in successfull_retained_passes
        possession_event_id = row['possessionEventId']
        game_id = row['gameId']
        tracking_succ_pass = tracking_passes_df[tracking_passes_df['possession_event_id'] == possession_event_id].iloc[0]
        if not tracking_succ_pass.empty:
            possession_start_frame = tracking_succ_pass.get("possession_start_frame")

            # Get the next game_event_id
            game_event_id = tracking_succ_pass["game_event_id"]
            period = tracking_succ_pass["period"]
            game_clock = tracking_succ_pass["periodGameClockTime"]
            team_name = tracking_succ_pass["game_event"].get("team_name") if isinstance(tracking_succ_pass["game_event"], dict) else None

            # get position of the ball
            ball_position = game.tracking_data[game.tracking_data["frame"] == int(possession_start_frame)].copy()
            home_team = passes_df[passes_df['possessionEventId'] == possession_event_id]['gameEvents.homeTeam'].iloc[0]

            # check if the ball is already in the attacking third
            ball_position = check_attacking_box(ball_position, game.pitch_dimensions, home_team)
            if ball_position['attacking_third'].iloc[0]:
                attacking_third_start = True
            else:
                attacking_third_start = False

            subset = tracking_df[
                    (tracking_df["frameNum"] >= possession_start_frame) & 
                    (tracking_df["period"] == period) &
                    (tracking_df["game_event_id"] != game_event_id) &
                    tracking_df["game_event_id"].notnull() & (tracking_df["periodGameClockTime"] <= game_clock + 10)
                ].copy()
            subset["team_name"] = subset["game_event"].apply(
                lambda x: x.get("team_name") if isinstance(x, dict) else None)
            subset["possession_event_type"] = subset["possession_event"].apply(
                lambda x: x.get("possession_event_type") if isinstance(x, dict) else None)
            if not subset.empty:
                # filter by team name
                subset = subset[subset["team_name"] == team_name]
                subset = subset.merge(
                game.tracking_data[['frame', 'ball_x', 'ball_y']], 
                    left_on='frameNum', right_on='frame', how='left')
                subset = subset.dropna(subset=['ball_x', 'ball_y'])
                subset = check_attacking_box(subset, game.pitch_dimensions, home_team)
                if subset['attacking_third'].any() and not attacking_third_start:
                    passes_df.loc[idx, "attacking_third_entry"] = True
                if subset['in_box'].any():
                    passes_df.loc[idx, "box_entry"] = True
                
                # if there is a shot or cross in the next 10 seconds
                shot_or_cross = subset[(subset["possession_event_type"] == "SH") | (subset["possession_event_type"] == "CR")]
                if not shot_or_cross.empty:
                    passes_df.loc[idx, "shot_or_cross_after"] = True
    
    return passes_df


