import argparse
from config import ZONES
from ingestion import get_zone_prices
from features import build_master_dataframe, compute_daily_bess_spreads
from exporter import export_all_datasets


def run_pipeline(force_refresh: bool = False):
    print("=" * 60)
    print("Starting European Electricity Price Explorer Data Pipeline")
    print("=" * 60)

    # Step 1: Load from per-zone CSV or fetch from API
    zone_series = {
        zone: get_zone_prices(zone, force_refresh=force_refresh)
        for zone in ZONES
    }

    # Step 2: Engineer time-series, geopolitical regimes, and trading spreads
    df_hourly = build_master_dataframe(zone_series)
    df_daily_bess = compute_daily_bess_spreads(df_hourly)

    # Step 3: Export final files for Python and Tableau
    export_all_datasets(df_hourly, df_daily_bess)
    print("=" * 60)
    print("Pipeline finished successfully!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run ENTSO-E Price Pipeline")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force re-download from API even if raw zone CSVs exist",
    )
    args = parser.parse_args()
    run_pipeline(force_refresh=args.refresh)