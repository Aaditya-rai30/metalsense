from pathlib import Path

import pandas as pd

from config import STANDARD_FILE


# ============================================================
# HELPERS
# ============================================================

def normalize(value) -> str:
    if value is None:
        return ""

    return (
        str(value)
        .strip()
        .lower()
        .replace("_", " ")
        .replace("-", " ")
    )


# ============================================================
# LOAD STANDARD REGISTRY
# ============================================================

def load_standards() -> pd.DataFrame:

    path = Path(STANDARD_FILE)

    if not path.exists():
        raise RuntimeError(
            f"standard.csv not found: {path}"
        )

    try:
        df = pd.read_csv(path)
    except Exception as exc:
        raise RuntimeError(
            f"Could not read standard.csv: {exc}"
        )

    if df.empty:
        raise RuntimeError(
            "standard.csv is empty"
        )

    required = {
        "Country",
        "Authority",
        "Standard",
        "Symbol",
        "PermissibleLimit",
        "Unit",
    }

    missing = required - set(df.columns)

    if missing:
        raise RuntimeError(
            "standard.csv is missing required columns: "
            + ", ".join(sorted(missing))
        )

    df["Country"] = (
        df["Country"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df["Authority"] = (
        df["Authority"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df["Standard"] = (
        df["Standard"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df["Symbol"] = (
        df["Symbol"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df["Unit"] = (
        df["Unit"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df["PermissibleLimit"] = pd.to_numeric(
        df["PermissibleLimit"],
        errors="coerce",
    )

    # Keep only rows with a usable positive limit.
    # This intentionally removes things such as WHO Iron
    # where no guideline value is supplied.
    df = df[
        df["PermissibleLimit"].notna()
        & (df["PermissibleLimit"] > 0)
    ].copy()

    return df


# ============================================================
# GET STANDARDS FOR COUNTRY
# ============================================================

def get_standards(
    country: str,
    authority: str | None = None,
) -> pd.DataFrame:

    df = load_standards()

    country_key = normalize(country)

    # --------------------------------------------------------
    # Explicit authority requested
    # --------------------------------------------------------

    if authority:

        authority_key = normalize(authority)

        # India / BIS, India / CPCB, etc.
        country_df = df[
            df["Country"].map(normalize)
            == country_key
        ]

        if not country_df.empty:

            authority_df = country_df[
                country_df["Authority"].map(normalize)
                == authority_key
            ]

            if not authority_df.empty:
                return authority_df

            # Also permit matching the Standard field.
            standard_df = country_df[
                country_df["Standard"].map(normalize)
                == authority_key
            ]

            if not standard_df.empty:
                return standard_df

        # Explicit WHO request should use WHO fallback.
        if authority_key in {
            "who",
            "who guidelines",
            "who default",
            "who guidelines for drinking water quality",
            "who guidelines for drinking-water quality",
        }:

            who_df = df[
                df["Country"].map(normalize)
                == "who default"
            ]

            if not who_df.empty:
                return who_df

        raise ValueError(
            f"No {authority} standard found for country: {country}"
        )

    # --------------------------------------------------------
    # INDIA DEFAULT → BIS
    # --------------------------------------------------------

    if country_key == "india":

        bis_df = df[
            (df["Country"].map(normalize) == "india")
            & (df["Authority"].map(normalize) == "bis")
        ]

        if not bis_df.empty:
            return bis_df

    # --------------------------------------------------------
    # NON-INDIA DEFAULT → WHO
    # --------------------------------------------------------

    who_df = df[
        df["Country"].map(normalize)
        == "who default"
    ]

    if not who_df.empty:
        return who_df

    raise ValueError(
        f"No WHO fallback standard is configured for country: {country}"
    )


# ============================================================
# STANDARD METADATA
# ============================================================

def standard_metadata(
    standards: pd.DataFrame,
) -> dict:

    if standards.empty:
        raise ValueError(
            "No standard rows available"
        )

    return {
        "country":
            str(standards["Country"].iloc[0]),

        "authority":
            str(standards["Authority"].iloc[0]),

        "standard":
            str(standards["Standard"].iloc[0]),
    }


# ============================================================
# AVAILABLE AUTHORITIES
# ============================================================

def available_authorities(
    country: str,
) -> list[str]:

    df = load_standards()

    country_key = normalize(country)

    india_df = df[
        df["Country"].map(normalize)
        == country_key
    ]

    if not india_df.empty:

        return sorted(
            india_df["Authority"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

    # Non-India gets WHO fallback.
    who_df = df[
        df["Country"].map(normalize)
        == "who default"
    ]

    if not who_df.empty:
        return ["WHO"]

    return []
