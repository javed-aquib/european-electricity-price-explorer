import logging
import numpy as np
import pandas as pd
from config import ZONES, TZ, NEGATIVE_PRICE_THRESHOLD, SPIKE_PRICE_THRESHOLD

logger = logging.getLogger(__name__)


def audit_and_interpolate_gaps(df: pd.DataFrame) -> pd.DataFrame:
    """
    Reindexes to a strict continuous hourly grid, logs raw missing hours per zone
    (Data Quality Audit), and interpolates short DST/API gaps up to 3 hours.
    """
    # 1. Enforce a continuous 1-hour DatetimeIndex from start to end
    full_hourly_idx = pd.date_range(
        start=df.index.min(),
        end=df.index.max(),
        freq="1h",
        tz=TZ,
        name="timestamp_cet",
    )
    df = df.reindex(full_hourly_idx)

    # 2. Data Quality Audit BEFORE interpolation
    total_hours = len(df)
    raw_missing = df[ZONES].isna().sum()
    for zone in ZONES:
        n_miss = int(raw_missing[zone])
        pct_miss = (n_miss / total_hours) * 100 if total_hours > 0 else 0.0
        logger.info(
            f"[DATA AUDIT] {zone:<5} | Raw Missing Hours: {n_miss:>4} / {total_hours:,} ({pct_miss:.3f}%)"
        )

    # 3. Linear time interpolation for short gaps (e.g., 1-hr Spring DST transition)
    df[ZONES] = df[ZONES].interpolate(method="time", limit=3)

    # 4. Data Quality Audit AFTER interpolation (flags any prolonged outages > 3 hours)
    remaining_missing = df[ZONES].isna().sum().to_dict()
    logger.info(f"[DATA AUDIT] Post-Interpolation Remaining NaNs (>3h gaps): {remaining_missing}")

    return df


def build_master_dataframe(zone_series_dict: dict) -> pd.DataFrame:
    """
    Merges individual zone series, performs the Data Quality Audit + DST interpolation,
    and engineers calendar, geopolitical regime, and trading spread features.
    """
    df = pd.DataFrame(zone_series_dict)
    df.index.name = "timestamp_cet"
    df = df.sort_index().dropna(how="all")

    # Step 1: Audit raw completeness & interpolate short DST gaps
    df = audit_and_interpolate_gaps(df)

    # Step 2: Calendar & Intraday Seasonality Features
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
        9: "Autumn", 10: "Autumn", 11: "Autumn",
    })

    # Step 3: Geopolitical Market Regimes
    idx_naive = df.index.tz_localize(None)
    df["market_regime"] = np.select(
        [
            idx_naive < "2021-07-01",
            (idx_naive >= "2021-07-01") & (idx_naive < "2023-01-01"),
            (idx_naive >= "2023-01-01") & (idx_naive < "2025-01-01"),
            idx_naive >= "2025-01-01",
        ],
        [
            "1_Pre_Ukraine_Baseline",
            "2_Ukraine_Gas_Shock",
            "3_Post_Crisis_Normalization",
            "4_US_Iran_LNG_Volatility",
        ],
        default="Other",
    )

    # Step 4: Trading Desk Framing — Cross-Border Spreads & Market Coupling
    df["spread_DE_FR"] = df["DE_LU"] - df["FR"]
    df["spread_DE_NO2"] = df["DE_LU"] - df["NO_2"]

    # Price convergence flag: when |spread| < 0.10 EUR/MWh, interconnector is uncongested
    df["coupled_DE_FR"] = df["spread_DE_FR"].abs() < 0.10
    df["coupled_DE_NO2"] = df["spread_DE_NO2"].abs() < 0.10

    # 30-Day (720-hour) Rolling Price Correlations with Germany (DE_LU)
    df["rolling_corr_DE_FR_30d"] = (
        df["DE_LU"].rolling(window=720, min_periods=168).corr(df["FR"])
    )
    df["rolling_corr_DE_NO2_30d"] = (
        df["DE_LU"].rolling(window=720, min_periods=168).corr(df["NO_2"])
    )

    # Step 5: Consultancy Framing — Negative Price & Scarcity Spike Flags
    df["is_negative_DE"] = df["DE_LU"] < NEGATIVE_PRICE_THRESHOLD
    df["is_spike_DE"] = df["DE_LU"] > SPIKE_PRICE_THRESHOLD

    logger.info(
        f"[FEATURES] Master DataFrame built: {len(df):,} hourly rows x {df.shape[1]} columns"
    )
    return df


def compute_daily_bess_spreads(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates daily Max-Min spread per zone (proxy for 1-hr Utility Battery Storage arbitrage)
    alongside daily mean and intraday standard deviation.
    """
    daily = (
        df.groupby(["date", "year", "month", "season", "market_regime"], observed=True)[ZONES]
        .agg(["min", "max", "mean", "std"])
    )

    records = pd.DataFrame(index=daily.index)
    for zone in ZONES:
        records[f"{zone}_min"] = daily[(zone, "min")]
        records[f"{zone}_max"] = daily[(zone, "max")]
        records[f"{zone}_mean"] = daily[(zone, "mean")]
        records[f"{zone}_volatility_std"] = daily[(zone, "std")]
        records[f"{zone}_bess_spread"] = daily[(zone, "max")] - daily[(zone, "min")]

    df_bess = records.reset_index()
    logger.info(f"[FEATURES] Daily BESS Arbitrage table built: {len(df_bess):,} daily rows")
    return df_bess