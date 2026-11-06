# European Electricity Price Explorer (`DE_LU`, `FR`, `NO_2`)

An exploratory time-series and market regime analysis of European Day-Ahead wholesale electricity prices across **Germany/Luxembourg (`DE_LU`)**, **France (`FR`)**, and **Southern Norway (`NO_2`)** using the ENTSO-E Transparency Platform REST API.

🔗 **[Interactive Tableau Public Dashboard — Insert Link Here](#)**

---

## 1. Project Context & Market Framing

This project investigates price dynamics across three distinct physical generation archetypes connected by cross-border interconnectors:
* **Germany/Luxembourg (`DE_LU`):** High wind/solar penetration with frequent negative midday prices and gas-driven evening peaks.
* **France (`FR`):** Baseload nuclear fleet sensitive to seasonal heating demand and reactor availability.
* **Southern Norway (`NO_2`):** Dispatchable hydro reservoir zone connected directly to Germany via the 1.4 GW **NordLink** subsea cable.

### Market Regimes Analyzed
To avoid distorting seasonal baselines with exogenous macro shocks, the dataset is segmented into four structural regimes:
1. **Pre-Ukraine Baseline (Jan 2020 – Jun 2021):** Pre-crisis pipeline gas baseline.
2. **Ukraine War & Gas Shock (Jul 2021 – Dec 2022):** Russian pipeline curtailment and French nuclear outages.
3. **Post-Crisis Renewable Normalization (Jan 2023 – Dec 2024):** LNG buildout, German nuclear exit, and rapid PV expansion.
4. **Middle East / LNG Volatility (Jan 2025 – Present):** Global seaborne LNG supply risk and surging negative-price hours.

---

## 2. Executive Summary (Key Findings)

### Consultancy Framing (Market Entry & BESS Storage)
* **Intraday Duck Curve & Solar Cannibalization:** *[Add 1 sentence on summer midday price troughs in DE_LU once you run Day 2 charts]*
* **Negative Price Frequency:** *[Add count/% of negative hours in DE_LU vs. FR and NO_2]*
* **Battery Arbitrage Potential:** *[Add average daily High-Low spread in EUR/MWh for DE_LU]*

### Trading Desk Framing (Cross-Border Spreads & Congestion)
* **`DE_LU – FR` CWE Spread:** *[Add insight on when German and French prices converge vs. decouple]*
* **`DE_LU – NO_2` NordLink Flows:** *[Add insight on how Norwegian hydro absorbs cheap German renewables and exports during German evening peaks]*

---

## 3. Repository Structure

```text
1_Electricity_Price_Explorer/
├── data/
│   ├── raw/                           # Fallback CSV downloads (ignored by Git)
│   └── processed/                     # Cleaned Parquet & Tableau CSV exports
├── figures/                           # Static charts exported from Jupyter
├── notebooks/
│   └── 01_eda_price_explorer.ipynb    # Main exploratory analysis & visual narrative
├── src/
│   └── fetch_and_clean.py             # Automated ENTSO-E API ingestion & cleaning
├── .env                               # Local API credentials (ignored by Git)
├── .gitignore                         # Git exclusion rules
├── requirements.txt                   # Python package dependencies
└── README.md                          # Project documentation & setup guide