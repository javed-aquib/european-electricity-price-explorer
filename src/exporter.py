import pandas as pd
from config import ZONES, PROCESSED_DIR, NEGATIVE_PRICE_THRESHOLD, SPIKE_PRICE_THRESHOLD


def export_all_datasets(df_hourly: pd.DataFrame, df_daily_bess: pd.DataFrame):
    """Saves Wide Parquet for Python, Daily BESS CSV, and Melted Long CSV for Tableau."""
    # 1. Wide Parquet for Python EDA
    parquet_path = PROCESSED_DIR / "prices_wide.parquet"
    df_hourly.to_parquet(parquet_path)
    print(f"[EXPORT 1/3] Wide Parquet saved: {parquet_path.name} ({len(df_hourly):,} rows)")

    # 2. Daily BESS Spreads CSV
    bess_path = PROCESSED_DIR / "daily_spreads.csv"
    df_daily_bess.to_csv(bess_path, index=False)
    print(f"[EXPORT 2/3] Daily Battery Spreads saved: {bess_path.name} ({len(df_daily_bess):,} rows)")

    # 3. Requirement #4: Final Long-Format CSV for Tableau Public
    id_cols = ["date", "year", "month", "hour", "day_of_week", "is_weekend", "season", "market_regime"]
    df_long = df_hourly.reset_index().melt(
        id_vars=["timestamp_cet"] + id_cols,
        value_vars=ZONES,
        var_name="bidding_zone",
        value_name="price_eur_mwh",
    )
    df_long["is_negative"] = df_long["price_eur_mwh"] < NEGATIVE_PRICE_THRESHOLD
    df_long["is_spike_150"] = df_long["price_eur_mwh"] > SPIKE_PRICE_THRESHOLD

    tableau_path = PROCESSED_DIR / "tableau_prices_long.csv"
    df_long.to_csv(tableau_path, index=False)
    print(f"[EXPORT 3/3] Tableau Public CSV saved: {tableau_path.name} ({len(df_long):,} rows)")