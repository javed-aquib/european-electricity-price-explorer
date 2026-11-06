import os
import time
import requests
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from entsoe import EntsoePandasClient

# 1. Load environment variables
load_dotenv()
API_KEY = os.getenv("ENTSOE_API_KEY", "").strip()

# Define zones and 6-year geopolitical lookback window (2020 to 2026)
ZONES = ["DE_LU", "FR", "NO_2"]
START_YEAR = 2020
END_YEAR = 2026
TZ = "Europe/Berlin"

os.makedirs("data/processed", exist_ok=True)


def fetch_via_entsoe(api_key: str) -> pd.DataFrame:
    """Primary ingestion using official ENTSO-E REST API (entsoe-py)."""
    print("Using official ENTSO-E API via entsoe-py...")
    client = EntsoePandasClient(api_key=api_key)
    start = pd.Timestamp(f"{START_YEAR}-01-01 00:00", tz=TZ)
    end = pd.Timestamp(f"{END_YEAR}-11-01 23:00", tz=TZ)

    series_dict = {}
    for zone in ZONES:
        print(f"  -> Fetching {zone} ({START_YEAR}–{END_YEAR})...")
        s = client.query_day_ahead_prices(zone, start=start, end=end)
        # Resample to 1h mean to handle the Oct 2025 15-min MTU transition seamlessly
        series_dict[zone] = s.tz_convert(TZ).resample("1h").mean()
    return pd.DataFrame(series_dict)


def fetch_via_energy_charts_fallback() -> pd.DataFrame:
    """Zero-key fallback using Fraunhofer ISE Energy-Charts API (official ENTSO-E mirror)."""
    print("No active ENTSOE_API_KEY detected. Using public Energy-Charts API fallback...")
    # Energy-Charts uses slightly different string formatting for bidding zones
    ec_zone_map = {"DE_LU": "DE-LU", "FR": "FR", "NO_2": "NO2"}
    series_dict = {}

    for zone_clean, ec_bzn in ec_zone_map.items():
        yearly_chunks = []
        for year in range(START_YEAR, END_YEAR + 1):
            url = (
                f"https://api.energy-charts.info/price"
                f"?bzn={ec_bzn}&start={year}-01-01&end={year}-12-31"
            )
            print(f"  -> Fetching {zone_clean} ({year})...")
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                if "unix_seconds" in data and "price" in data:
                    idx = pd.to_datetime(data["unix_seconds"], unit="s", utc=True).tz_convert(TZ)
                    s = pd.Series(data["price"], index=idx, name=zone_clean, dtype=float)
                    yearly_chunks.append(s)
            time.sleep(0.3)  # Polite rate limit

        combined = pd.concat(yearly_chunks)
        combined = combined[~combined.index.duplicated(keep="first")].sort_index()
        # Resample to hourly mean to standardize 15-min and 60-min intervals
        series_dict[zone_clean] = combined.resample("1h").mean()

    return pd.DataFrame(series_dict)


def clean_and_engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Aligns hourly grid, interpolates DST gaps, and engineers regime/trading features."""
    df.index.name = "timestamp_cet"
    df = df.sort_index()

    # Drop trailing empty rows (future dates in current year)
    df = df.dropna(how="all")

    # Interpolate short gaps (e.g., 1-hour Spring DST transition or isolated missing hours)
    df[["DE_LU", "FR", "NO_2"]] = df[["DE_LU", "FR", "NO_2"]].interpolate(method="time", limit=3)

    # Calendar & Intraday features
    df["date"] = df.index.date
    df["year"] = df.index.year
    df["month"] = df.index.month
    df["hour"] = df.index.hour
    df["day_of_week"] = df.index.day_name()
    df["is_weekend"] = df.index.dayofweek.isin([5, 6])

    df["season"] = df["month"].map({
        12: "Winter", 1: "Winter", 2: "Winter",
        3: "Spring", 4: "Spring", 5: "Spring",
        6: "Summer", 7: "Summer", 8: "Summer",
        9: "Autumn", 10: "Autumn", 11: "Autumn"
    })

    # Geopolitical Market Regimes
    idx_naive = df.index.tz_localize(None)
    conditions = [
        (idx_naive < "2021-07-01"),
        (idx_naive >= "2021-07-01") & (idx_naive < "2023-01-01"),
        (idx_naive >= "2023-01-01") & (idx_naive < "2025-01-01"),
        (idx_naive >= "2025-01-01")
    ]
    choices = [
        "1_Pre_Ukraine_Baseline",
        "2_Ukraine_Gas_Shock",
        "3_Post_Crisis_Normalization",
        "4_US_Iran_LNG_Volatility"
    ]
    df["market_regime"] = np.select(conditions, choices, default="Other")

    # Cross-Border Trading Spreads (EUR/MWh)
    df["spread_DE_FR"] = df["DE_LU"] - df["FR"]
    df["spread_DE_NO2"] = df["DE_LU"] - df["NO_2"]

    # Binary Risk Flags for Germany (DE_LU)
    df["is_negative_DE"] = df["DE_LU"] < 0
    df["is_spike_DE"] = df["DE_LU"] > 150

    return df


def export_datasets(df: pd.DataFrame):
    """Exports wide Parquet for Python EDA and melted long CSV for Tableau Public."""
    parquet_path = "data/processed/prices_wide.parquet"
    df.to_parquet(parquet_path)
    print(f"Saved wide dataset for Python EDA: {parquet_path} ({df.shape[0]:,} hourly rows)")

    # Reshape to Long Format for Tableau Public
    id_cols = ["date", "year", "month", "hour", "day_of_week", "is_weekend", "season", "market_regime"]
    df_reset = df.reset_index()
    df_long = df_reset.melt(
        id_vars=["timestamp_cet"] + id_cols,
        value_vars=["DE_LU", "FR", "NO_2"],
        var_name="bidding_zone",
        value_name="price_eur_mwh"
    )
    df_long["is_negative"] = df_long["price_eur_mwh"] < 0
    df_long["is_spike_150"] = df_long["price_eur_mwh"] > 150

    csv_path = "data/processed/tableau_prices_long.csv"
    df_long.to_csv(csv_path, index=False)
    print(f"Saved long dataset for Tableau Public: {csv_path} ({df_long.shape[0]:,} rows)")


if __name__ == "__main__":
    has_valid_key = (
        len(API_KEY) == 36
        and "paste_your" not in API_KEY
        and "your_actual" not in API_KEY
    )
    if has_valid_key:
        raw_df = fetch_via_entsoe(API_KEY)
    else:
        raw_df = fetch_via_energy_charts_fallback()

    clean_df = clean_and_engineer_features(raw_df)
    export_datasets(clean_df)
    print("Day 1 pipeline complete!")