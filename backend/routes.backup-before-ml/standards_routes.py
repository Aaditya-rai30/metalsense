from typing import Optional

from fastapi import APIRouter, Query

from services.standards_service import (
    available_authorities,
    get_standards,
)


router = APIRouter()


@router.get("/")
async def list_standards(
    country: Optional[str] = Query(
        None,
        description="Country name",
    ),
    authority: Optional[str] = Query(
        None,
        description="Authority such as BIS, CPCB, or WHO",
    ),
):
    # --------------------------------------------------------
    # If no country is supplied, return a compact registry
    # grouped by country/authority.
    # --------------------------------------------------------

    if not country:
        import pandas as pd
        from services.standards_service import load_standards

        df = load_standards()

        return [
            {
                "country": str(row["Country"]),
                "authority": str(row["Authority"]),
                "standard": str(row["Standard"]),
                "context": (
                    str(row["Context"])
                    if "Context" in df.columns
                    and pd.notna(row["Context"])
                    else None
                ),
                "metal": str(row["Symbol"]),
                "permissible_limit": float(
                    row["PermissibleLimit"]
                ),
                "unit": str(row["Unit"]),
            }
            for _, row in df.iterrows()
        ]

    standards = get_standards(
        country=country,
        authority=authority,
    )

    context = None

    if "Context" in standards.columns:
        context = str(
            standards["Context"].iloc[0]
        )

    return [
        {
            "country":
                str(row["Country"]),

            "authority":
                str(row["Authority"]),

            "standard":
                str(row["Standard"]),

            "context":
                context,

            "metal":
                str(row["Symbol"]),

            "permissible_limit":
                float(row["PermissibleLimit"]),

            "unit":
                str(row["Unit"]),
        }
        for _, row in standards.iterrows()
    ]


@router.get("/authorities")
async def list_authorities(
    country: str = Query(
        ...,
        description="Country name",
    ),
):
    return {
        "country": country,
        "authorities":
            available_authorities(country),
    }
