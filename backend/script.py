"""
fetch_metal_water_data.py

Pulls real heavy-metal-in-water measurements (mg/L) from the Water Quality
Portal (https://www.waterqualitydata.us), a free, no-key-required API
jointly run by USGS and the EPA aggregating data from 400+ agencies.

Usage:
    pip install requests pandas matplotlib
    python fetch_metal_water_data.py

Output:
    metal_water_data.csv   -> raw combined results
    metal_summary.csv      -> per-metal stats (count, mean, min, max)
    metal_summary.png      -> bar chart of mean concentration per metal
"""

import requests
import pandas as pd
import io

# ---- Config ----------------------------------------------------------

# Metals to pull. Names must match WQP "characteristicName" values.
METALS = [
    "Lead",
    "Arsenic",
    "Mercury",
    "Cadmium",
    "Chromium",
    "Copper",
    "Zinc",
    "Nickel",
    "Iron",
    "Manganese",
]

# Narrow the pull so it doesn't take forever / return millions of rows.
# Options: restrict by state, sample media, date range, etc.
PARAMS_BASE = {
    "mimeType": "csv",
    "zip": "no",
    "sampleMedia": "Water",
    "startDateLo": "01-01-2018",   # last ~7 years of data
    "startDateHi": "12-31-2025",
    # "statecode": "US:36",       # uncomment + set to restrict to one state (36 = NY)
}

WQP_URL = "https://www.waterqualitydata.us/data/Result/search"


# ---- Fetch -------------------------------------------------------------

def fetch_metal(metal: str) -> pd.DataFrame:
    """Fetch results for a single metal characteristic from WQP."""
    params = dict(PARAMS_BASE)
    params["characteristicName"] = metal

    print(f"Fetching {metal}...")
    resp = requests.get(WQP_URL, params=params, timeout=120)
    resp.raise_for_status()

    df = pd.read_csv(io.StringIO(resp.text), low_memory=False)
    print(f"  -> {len(df)} rows")
    return df


def main():
    all_dfs = []
    for metal in METALS:
        try:
            df = fetch_metal(metal)
            if not df.empty:
                all_dfs.append(df)
        except Exception as e:
            print(f"  ! Failed to fetch {metal}: {e}")

    if not all_dfs:
        print("No data fetched. Check your internet connection / API status.")
        return

    combined = pd.concat(all_dfs, ignore_index=True)

    # Keep only the columns most relevant for a lab report
    keep_cols = [
        "CharacteristicName",
        "ResultMeasureValue",
        "ResultMeasure/MeasureUnitCode",
        "ActivityStartDate",
        "MonitoringLocationIdentifier",
        "OrganizationFormalName",
        "ResultStatusIdentifier",
    ]
    keep_cols = [c for c in keep_cols if c in combined.columns]
    combined = combined[keep_cols]

    # Filter to mg/L only (WQP mixes units: mg/L, ug/L, etc.)
    unit_col = "ResultMeasure/MeasureUnitCode"
    mgl = combined[combined[unit_col] == "mg/L"].copy()
    mgl["ResultMeasureValue"] = pd.to_numeric(
        mgl["ResultMeasureValue"], errors="coerce"
    )
    mgl = mgl.dropna(subset=["ResultMeasureValue"])

    mgl.to_csv("metal_water_data.csv", index=False)
    print(f"\nSaved {len(mgl)} mg/L records -> metal_water_data.csv")

    # ---- Summary stats ----
    summary = (
        mgl.groupby("CharacteristicName")["ResultMeasureValue"]
        .agg(["count", "mean", "min", "max", "std"])
        .sort_values("count", ascending=False)
    )
    summary.to_csv("metal_summary.csv")
    print("\nSummary (mg/L):")
    print(summary)

    # ---- Quick chart ----
    try:
        import matplotlib.pyplot as plt

        ax = summary["mean"].plot(kind="bar", figsize=(9, 5), color="#4C72B0")
        ax.set_ylabel("Mean concentration (mg/L)")
        ax.set_title("Mean heavy metal concentration in water samples")
        plt.tight_layout()
        plt.savefig("metal_summary.png", dpi=150)
        print("Saved chart -> metal_summary.png")
    except ImportError:
        print("matplotlib not installed, skipping chart.")


if __name__ == "__main__":
    main()