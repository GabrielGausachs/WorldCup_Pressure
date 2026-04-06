import json

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

    return passes, tracking_passes

def get_pass_frame(tracking_passes_df):
    tracking_passes_df["possession_start_frame"] = tracking_passes_df["possession_event"].apply(
        lambda x: x.get("start_frame") if isinstance(x, dict) else None)
    return tracking_passes_df

def pressure_on_receiver(passes_df, tracking_passes_df, dict_games):
    tracking_passes_df = get_pass_frame(tracking_passes_df)
    passes_df["pressure_on_receiver"] = np.nan  # Initialize the pressure column with NaN values
    for idx, row in tracking_passes_df.iterrows():

        # Get the start frame of the possession event for this pass
        possession_start_frame = row.get("possession_start_frame")
        game_id = row.get("game_id")
        if game_id not in dict_games:
            print(f"Game ID {game_id} not found in dict_games. Skipping this pass.")
            continue
        game = dict_games[game_id]
        game_tracking_frame = game.tracking_data[game.tracking_data["frame"] == possession_start_frame].iloc[0]
        
        # Get the receiver's name from the event data using the possession_event_id
        possession_event_id = row["possession_event_id"]
        if isinstance(possession_event_id, float):
            target_player_name = passes_df[(passes_df['possessionEventId'] == possession_event_id) & passes_df['gameId'] == game_id]['possessionEvents.targetPlayerName'].iloc[0]
            home_team = passes_df[(passes_df['possessionEventId'] == possession_event_id) & passes_df['gameId'] == game_id]['gameEvents.homeTeam'].iloc[0]
            if not isinstance(target_player_name, str):
                print(f"Target player name is not a string for possession event ID: {possession_event_id}")
            
            # Find the player shirt_num
            if home_team:
                player_info = game.home_players[game.home_players["full_name"] == target_player_name]
                if player_info.empty:
                    print(f"Player {target_player_name} not found in home team for possession event ID: {possession_event_id}")
            else:
                player_info = game.away_players[game.away_players["full_name"] == target_player_name]
                if player_info.empty:
                    print(f"Player {target_player_name} not found in away team for possession event ID: {possession_event_id}")
            player_id = player_info["id"].iloc[0]

            # Get the pressure on the target player at the start frame
            idx = game.tracking_data[game.tracking_data["frame"] == int(possession_start_frame)].index[0]
            pressure = game.tracking_data.get_pressure_on_player(index=idx, column_id=game.player_id_to_column_id(player_id), pitch_size=game.pitch_dimensions)

            # Add pressure in the passes_df for the corresponding possession_event_id
            passes_df.loc[(passes_df['possessionEventId'] == possession_event_id) & (passes_df['gameId'] == game_id), 'pressure_on_receiver'] = pressure / 100  # Convert to percentage
    return passes_df

def player_position_mapping(rosters_file, passes_df):
    with open(rosters_file, 'r') as f:
        rosters_data = json.load(f)
    nickname_to_position = {p['player']['nickname']: p['positionGroupType'] for p in rosters_data}
    passes_df['positionGroupType'] = passes_df['possessionEvents.targetPlayerName'].map(nickname_to_position)
    return passes_df