
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from src.live.update_forecasts import fetch_live_snapshot
from src.live.traffic_archive import archive_snapshot

print("Fetching real Canberra traffic observations...")
live = fetch_live_snapshot()

print(f"Received {len(live)} road links")
print(f"Timestamp: {live['timestamp'].max()}")

with TemporaryDirectory() as folder:
    db_path = Path(folder) / "test_traffic.duckdb"

    # Insert twice to test idempotency.
    history = archive_snapshot(live, db_path)
    history_again = archive_snapshot(live, db_path)

    assert len(history) == len(live)
    assert len(history_again) == len(live)

    # Verify the data is unchanged after SQL storage.
    columns = [
        "timestamp",
        "originsiteid",
        "destsiteid",
        "tt",
        "mintt",
        "relative_delay",
    ]

    pd.testing.assert_frame_equal(
        live[columns].sort_values(
            ["originsiteid", "destsiteid"]
        ).reset_index(drop=True),
        history_again[columns].sort_values(
            ["originsiteid", "destsiteid"]
        ).reset_index(drop=True),
        check_dtype=False,
    )

    print("Real-data ingestion: PASSED")
    print("SQL deduplication: PASSED")
    print("Data integrity: PASSED")