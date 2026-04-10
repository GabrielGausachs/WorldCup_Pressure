import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
from kloppy import pff
from databallpy import get_game_from_kloppy
from Utils.config import BASE_PATH
from Utils import logger
from Utils.loading import load_files, load_game_from_pff
from Utils.helpers import clean_tracking_data, bz2_to_parquet
from Utils.feature_extraction import get_passes, pressure_on_receiver, player_position_mapping, retain_lose_after_pass, what_leads

if __name__ == "__main__":

    # Initialize logger
    logger.initialize_logger()
    logger = logger.get_logger()

    # Clean the data
    clean_tracking_data(BASE_PATH)
    bz2_to_parquet(BASE_PATH)

    # Get list of game IDs from eventdata directory
    game_ids = [g.split(".")[0] for g in os.listdir(os.path.join(BASE_PATH, "eventdata")) if g.endswith(".json")]

    for game_id in game_ids:
        logger.info("-" * 50)
        logger.info(f"Processing game {game_id}...")

        # Load the events and tracking
        event_path = os.path.join(BASE_PATH, "eventdata", f"{game_id}.json")
        tracking_path = os.path.join(BASE_PATH, "trackingdata_parquet", f"{game_id}.parquet")
        event_df, tracking_df = load_files(event_path, tracking_path)
        try:
            game = load_game_from_pff(BASE_PATH, game_id)
        except Exception as e:
            logger.error(f"Error loading game {game_id}: {e}")
            continue

        # Extract passes
        passes_df, tracking_passes_df = get_passes(event_df, tracking_df)
        logger.info(f"Number of passes in event_df: {passes_df.shape[0]}")
        logger.info(f"Number of passes in tracking_df: {tracking_passes_df.shape[0]}")

        # Get pressure on receiver
        passes_df = pressure_on_receiver(passes_df, tracking_passes_df, game)

        # Retain or lose ball after pass
        passes_df = retain_lose_after_pass(passes_df, tracking_passes_df, tracking_df)

        # What leads after a successfull retained pass
        passes_df = what_leads(passes_df, tracking_passes_df, tracking_df, game)

        # Save the processed DataFrames for the current game
        os.makedirs(os.path.join(BASE_PATH, "dataset_wc_passes"), exist_ok=True)
        passes_df.to_csv(os.path.join(BASE_PATH, "dataset_wc_passes", f"{game_id}_passes.csv"), index=False)
        tracking_passes_df.to_csv(os.path.join(BASE_PATH, "dataset_wc_passes", f"{game_id}_tracking_passes.csv"), index=False)
        logger.info(f"Processed game {game_id}")
    logger.info("Processing complete for all games.")
