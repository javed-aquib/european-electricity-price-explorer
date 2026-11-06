import time
import logging
import requests
import pandas as pd
from entsoe import EntsoePandasClient
from config import API_KEY, START_YEAR, END_YEAR, TZ, RAW_DIR

# Configure clean console logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def is_valid_entsoe_key(key: str) -> bool:
    """Checks if the .env file contains a real 36-character ENTSO-E UUID token."""
    return (
        isinstance(key, str)
        and len(key) == 36
        and "paste_your" not in key
        and "your_actual" not in key
    )


def _fetch_single_year_entsoe(zone: str, year: int) -> pd.Series:
    """Queries 1 calendar year for 1 bidding zone via the official ENTSO-E REST API."""
    client = EntsoePandasClient(api_key=API_KEY)
    start = pd.Timestamp(f"{year}-01-01 00:00", tz=TZ)

    # Cap the end timestamp at the current hour if querying the active calendar year
    now = pd.Timestamp.now(tz=TZ).floor("h")
    end = min(pd.Timestamp(f"{year}-12-31 23:00", tz=TZ), now)

    logger.info(f"[ENTSO-E API] Downloading {zone} for {year}...")
    s = client.query_day_ahead_prices(zone, start=start, end=end)
    s = s.tz_convert(TZ)
    s = s[~s.index.duplicated(keep="first")].sort_index()

    # Resample to 1h mean to standardize 60-min and 15-min MTU periods
    return s.resample("1h").mean().rename(zone)


def _fetch_single_year_fallback(zone: str, year: int) -> pd.Series:
    """Queries 1 calendar year for 1 bidding zone via public Energy-Charts API (no key required)."""
    ec_map = {"DE_LU": "DE-LU", "FR": "FR", "NO_2": "NO2"}
    if zone not in ec_map:
        raise ValueError(f"Zone '{zone}' is not mapped in the Energy-Charts fallback dictionary.")

    ec_bzn = ec_map[zone]
    url = (
        f"https://api.energy-charts.info/price"
        f"?bzn={ec_bzn}&start={year}-01-01&end={year}-12-31"
    )

    logger.info(f"[Energy-Charts API] Downloading {zone} for {year}...")
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    if "unix_seconds" not in payload or "price" not in payload:
        raise ValueError(f"Empty price payload returned for {zone} in {year}.")

    idx = pd.to_datetime(payload["unix_seconds"], unit="s", utc=True).tz_convert(TZ)
    s = pd.Series(payload["price"], index=idx, dtype=float, name=zone)
    s = s[~s.index.duplicated(keep="first")].sort_index()

    # Resample to 1h mean to standardize 60-min and 15-min MTU periods
    return s.resample("1h").mean().rename(zone)


def get_zone_year_prices(zone: str, year: int, force_refresh: bool = False) -> pd.Series:
    """
    Checks if data/raw/{zone}/{zone}_{year}.csv exists locally before hitting the API.
    - Historical years (year < current_year) are immutable and loaded directly from CSV.
    - Current year (e.g., 2026) auto-refreshes if the cached CSV is older than 24 hours.
    """
    zone_dir = RAW_DIR / zone
    zone_dir.mkdir(parents=True, exist_ok=True)
    yearly_csv_path = zone_dir / f"{zone}_{year}.csv"

    current_year = pd.Timestamp.now(tz=TZ).year
    is_stale_current_year = (
        year == current_year
        and yearly_csv_path.exists()
        and (time.time() - yearly_csv_path.stat().st_mtime) > 86400  # 24 hours in seconds
    )

    if yearly_csv_path.exists() and not force_refresh and not is_stale_current_year:
        logger.info(f"[CACHE HIT]  Loaded {zone}/{yearly_csv_path.name} from local disk")
        df_year = pd.read_csv(yearly_csv_path, index_col=0)
        df_year.index = pd.to_datetime(df_year.index, utc=True).tz_convert(TZ)
        return df_year[zone].rename(zone)

    if is_stale_current_year:
        logger.info(f"[CACHE STALE] {zone}/{yearly_csv_path.name} is >24h old. Refreshing current year...")
    else:
        logger.info(f"[CACHE MISS] {zone}/{yearly_csv_path.name} not found on disk.")

    # Fetch from primary ENTSO-E API if valid key exists; otherwise use fallback
    if is_valid_entsoe_key(API_KEY):
        try:
            series = _fetch_single_year_entsoe(zone, year)
        except Exception as exc:
            logger.warning(f"ENTSO-E API failed for {zone} {year} ({exc}). Trying fallback...")
            series = _fetch_single_year_fallback(zone, year)
    else:
        series = _fetch_single_year_fallback(zone, year)

    series.index.name = "timestamp_cet"
    series.to_csv(yearly_csv_path, header=True)
    logger.info(f"[SAVED CSV]  {zone}/{yearly_csv_path.name} ({len(series):,} hourly rows)")

    time.sleep(0.3)  # Polite pause between API calls
    return series


def get_zone_prices(zone: str, force_refresh: bool = False) -> pd.Series:
    """Loops through START_YEAR..END_YEAR for a zone and stitches them into a single Series."""
    logger.info(f"--- Processing Bidding Zone: {zone} ({START_YEAR}–{END_YEAR}) ---")
    yearly_series_list = []

    for year in range(START_YEAR, END_YEAR + 1):
        try:
            s_year = get_zone_year_prices(zone, year, force_refresh=force_refresh)
            yearly_series_list.append(s_year)
        except Exception as exc:
            logger.error(f"Could not load {zone} for {year}: {exc}")

    if not yearly_series_list:
        raise RuntimeError(f"No data could be loaded or fetched for bidding zone: {zone}")

    combined = pd.concat(yearly_series_list)
    combined = combined[~combined.index.duplicated(keep="first")].sort_index()
    return combined.rename(zone)