import ast
import os
import json
import pandas as pd
from Utils.config import BASE_PATH
from kloppy import pff
from databallpy import get_game_from_kloppy
from Utils.logger import get_logger

logger = get_logger()

def load_events_from_json(file_path):
    with open(file_path, 'r') as f:
        data = json.load(f)
    return pd.json_normalize(data)

def load_files(event_path, tracking_path):
    event_df = load_events_from_json(event_path )
    logger.info("-" * 50)
    logger.info(f"Loaded {event_path}: {event_df.shape[0]} events")
    tracking_df = pd.read_parquet(tracking_path)
    logger.info(f"Loaded {tracking_path}: {tracking_df.shape[0]} rows")
    return event_df, tracking_df

def load_game_from_pff(base_path, game_id):
    dataset = pff.load_tracking(
        meta_data= os.path.join(base_path,"metadata",f"{game_id}.json"),
        roster_meta_data= os.path.join(base_path,"rosters",f"{game_id}.json"),
        raw_data= os.path.join(base_path,"trackingdata_clean",f"{game_id}_clean.jsonl.bz2"),
        coordinates="pff",
        only_alive=False
    )
    dataset.metadata.frame_rate = int(dataset.metadata.frame_rate)
    game = get_game_from_kloppy(tracking_dataset=dataset)
    game.tracking_data.filter_tracking_data(column_ids="ball", filter_type="savitzky_golay", window_length=25, polyorder=2)
    game.tracking_data.add_velocity(game.get_column_ids() + ["ball"], allow_overwrite=True)
    game.tracking_data.add_acceleration(game.get_column_ids() + ["ball"], allow_overwrite=True)
    logger.info(f"Loaded tracking data for game {game_id}")
    return game

def load_passes(base_path):
    # Load passes and tracking_passes data
    passes_files = [f for f in os.listdir(os.path.join(base_path, "dataset_wc_passes")) if f.endswith('.csv') and "tracking" not in f]
    tracking_passes_files = [f for f in os.listdir(os.path.join(base_path, "dataset_wc_passes")) if f.endswith('.csv') and "tracking" in f]
    print(f"Found {len(passes_files)} passes files and {len(tracking_passes_files)} tracking passes files.")

    # concatenate all passes and tracking_passes data into single DataFrames
    passes_df = pd.concat([pd.read_csv(os.path.join(base_path, "dataset_wc_passes", f)) for f in passes_files], ignore_index=True)
    tracking_passes_df = pd.concat([pd.read_csv(os.path.join(base_path, "dataset_wc_passes", f)) for f in tracking_passes_files], ignore_index=True)
    print(f"Combined passes DataFrame shape: {passes_df.shape}")
    print(f"Combined tracking passes DataFrame shape: {tracking_passes_df.shape}")

    # Extract game_id from the game_event column in tracking_passes_df
    tracking_passes_df["game_event_dict"] = tracking_passes_df["game_event"].apply(
        lambda x: ast.literal_eval(x) if isinstance(x, str) else None
    )
    tracking_passes_df["game_id"] = tracking_passes_df["game_event_dict"].apply(
        lambda x: x.get("game_id") if isinstance(x, dict) else None
    )
    # Drop the game_event_dict column as it is no longer needed
    tracking_passes_df.drop(columns=["game_event_dict"], inplace=True)

    return passes_df, tracking_passes_df