from __future__ import annotations

import json
import logging
import os
import re
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
import pandas as pd
import requests

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURATION
# ============================================================

NOMINATIM_URL = (
    "https://nominatim.openstreetmap.org/search"
)

USER_AGENT = (
    "MetalSense/1.0 "
    "(environmental-water-quality-analysis)"
)

CACHE_FILE = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "location_cache.json"
)

# Nominatim public-service friendly settings.
MIN_REQUEST_INTERVAL = 1.1
REQUEST_TIMEOUT = 5

# IMPORTANT:
# Never allow one PDF import to make hundreds of
# external geocoding requests.
# ============================================================
# GEOCODING SAFETY LIMIT
# ============================================================

# Never blindly send hundreds of locations to an external
# geocoder during one PDF import.
MAX_GEOCODING_LOCATIONS = 25

# ============================================================
# GEOAPIFY BATCH GEOCODING
# ============================================================

GEOAPIFY_API_KEY = os.getenv(
    "GEOAPIFY_API_KEY",
    "",
).strip()

GEOAPIFY_BATCH_URL = (
    "https://api.geoapify.com/v1/batch/geocode/search"
)

GEOAPIFY_POLL_INTERVAL = 10
GEOAPIFY_MAX_POLL_ATTEMPTS = 18
GEOAPIFY_BATCH_SIZE = 1000

_CACHE: dict[str, Any] = {}
_LAST_REQUEST = 0.0


# ============================================================
# NORMALIZATION
# ============================================================

def _norm(value: Any) -> str:
    if value is None:
        return ""

    return " ".join(
        str(value)
        .strip()
        .lower()
        .split()
    )


def _key(
    location,
    country=None,
    region=None,
):
    return "|".join(
        (
            _norm(location),
            _norm(country),
            _norm(region),
        )
    )


def _missing(value):
    if value is None:
        return True

    try:
        import pandas as pd

        return bool(pd.isna(value))

    except Exception:
        return False


# ============================================================
# CACHE
# ============================================================

def _load():
    global _CACHE

    if _CACHE:
        return

    try:
        CACHE_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if CACHE_FILE.exists():
            data = json.loads(
                CACHE_FILE.read_text(
                    encoding="utf-8"
                )
            )

            _CACHE = (
                data
                if isinstance(data, dict)
                else {}
            )

    except Exception as exc:
        logger.warning(
            "Could not load location cache: %s",
            exc,
        )

        _CACHE = {}


def _save():
    try:
        CACHE_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        tmp = CACHE_FILE.with_suffix(
            ".tmp"
        )

        tmp.write_text(
            json.dumps(
                _CACHE,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        tmp.replace(CACHE_FILE)

    except Exception as exc:
        logger.warning(
            "Could not save location cache: %s",
            exc,
        )


# ============================================================
# SINGLE LOCATION RESOLUTION
# ============================================================

def normalize_pdf_location(value):
    """
    Clean common PDF extraction artefacts from sampling locations.

    Examples:
        Someshw ar -> Someshwar
        Ulhasnaga r -> Ulhasnagar
        Chinchw ad -> Chinchwad
        Gandhis agar -> Gandhisagar
    """

    if value is None:
        return ""

    text = str(value).strip()

    if not text:
        return ""

    # Normalize whitespace first.
    text = re.sub(r"\s+", " ", text)

    # Common PDF line/table extraction splits.
    replacements = {
        "Someshw ar": "Someshwar",
        "Ulhasnaga r": "Ulhasnagar",
        "Chinchw ad": "Chinchwad",
        "Gandhis agar": "Gandhisagar",
        "Gandhisag ar": "Gandhisagar",
        "Panchaganga": "Panchganga",
        "Panchganga": "Panchganga",
        "Koyana": "Koyna",
        "Krushna": "Krishna",
        "Arebian Sea": "Arabian Sea",
        "Chandrabhaga": "Chandrabhaga",
        "Chandrabha ga": "Chandrabhaga",
        "Bogeshwa ri": "Bogeshwari",
        "Kankalesh war": "Kankaleshwar",
        "Siddheshwa r": "Siddheshwar",
        "Sidheshwa r": "Siddheshwar",
        "Ghanewadi": "Ghanewadi",
        "Mundhawa": "Mundhwa",
        "Aundhgaon": "Aundh",
        "Vithalwadi": "Vithalwadi",
        "Jaysingp ur": "Jaysingpur",
        "Sindhudur g": "Sindhudurg",
        "Sonega on": "Sonegaon",
        "Sakkard ara": "Sakkardara",
        "Motibag": "Motibag",
        "Pawana": "Pavana",
    }

    for broken, corrected in replacements.items():
        text = text.replace(
            broken,
            corrected,
        )

    # Remove duplicated punctuation/spaces.
    text = re.sub(
        r"\s*,\s*",
        ", ",
        text,
    )

    text = re.sub(
        r"\s*\.\s*",
        ". ",
        text,
    )

    text = re.sub(
        r",\s*,+",
        ", ",
        text,
    )

    return text.strip(" ,.-")


def build_location_queries(
    location,
    country=None,
    region=None,
):
    """
    Build increasingly broader but still location-specific
    geocoding queries.

    We deliberately DO NOT use only the state/country as a
    sampling coordinate fallback.
    """

    location = normalize_pdf_location(
        location
    )

    country = normalize_pdf_location(
        country
    )

    region = normalize_pdf_location(
        region
    )

    if not location:
        return []

    queries = []

    def add(parts):
        query = ", ".join(
            str(part).strip()
            for part in parts
            if part and str(part).strip()
        )

        if (
            query
            and query not in queries
        ):
            queries.append(query)

    # --------------------------------------------------------
    # Full sampling location
    # --------------------------------------------------------

    add([
        location,
        region,
        country,
    ])

    # --------------------------------------------------------
    # Remove sampling-detail noise
    # --------------------------------------------------------

    simplified = re.sub(
        r"\b("
        r"Tal|Taluka|Tq|Dist|District"
        r")\.?\s*[-:]?",
        "",
        location,
        flags=re.IGNORECASE,
    )

    simplified = re.sub(
        r"\s+",
        " ",
        simplified,
    ).strip(" ,.-")

    add([
        simplified,
        region,
        country,
    ])

    # --------------------------------------------------------
    # River / lake / creek / dam extraction
    # --------------------------------------------------------

    water_match = re.search(
        r"(.+?\b"
        r"(?:river|lake|creek|dam|reservoir|"
        r"khadi|talav|talao|nalla|canal)"
        r"\b)",
        simplified,
        flags=re.IGNORECASE,
    )

    if water_match:

        water_body = water_match.group(
            1
        ).strip(" ,.-")

        add([
            water_body,
            region,
            country,
        ])

    # --------------------------------------------------------
    # Keep district/city information
    # --------------------------------------------------------

    locality_match = re.search(
        r"(?:near|at|village|"
        r"city|town|road|bridge)\s+"
        r"(.+)",
        simplified,
        flags=re.IGNORECASE,
    )

    if locality_match:

        locality = locality_match.group(
            1
        ).strip(" ,.-")

        add([
            locality,
            region,
            country,
        ])

    return queries


def resolve_location_smart(
    location,
    country=None,
    region=None,
):
    """
    Resolve a sampling location using multiple increasingly
    broader queries.

    A broad state/country result is NEVER accepted as the
    sampling coordinate.
    """

    queries = build_location_queries(
        location=location,
        country=country,
        region=region,
    )

    for query in queries:

        logger.info(
            "Smart location query: %s",
            query,
        )

        result = resolve_location(
            query,
        )

        if not result:
            continue

        latitude = result.get(
            "latitude"
        )

        longitude = result.get(
            "longitude"
        )

        try:

            latitude = float(
                latitude
            )

            longitude = float(
                longitude
            )

        except (
            TypeError,
            ValueError,
        ):

            continue

        if not (
            -90 <= latitude <= 90
            and
            -180 <= longitude <= 180
        ):
            continue

        result = dict(result)

        result[
            "resolution"
        ] = "location_geocoded"

        result[
            "resolved_query"
        ] = query

        result[
            "confidence"
        ] = result.get(
            "confidence",
            "medium",
        )

        return result

    return None


def resolve_location(
    location: Any,
    country: Any = None,
    region: Any = None,
):
    """
    Resolve one textual sampling location.

    Examples:

        Ganga
        Yamuna
        Godavari, Maharashtra, India
        Mumbai, Maharashtra, India

    Returns a normalized location result or None.
    """

    location = str(
        location or ""
    ).strip()

    if not location:
        return None

    key = _key(
        location,
        country,
        region,
    )

    _load()

    # --------------------------------------------------------
    # CACHE
    # --------------------------------------------------------

    cached = _CACHE.get(key)

    if cached:
        if cached.get("status") == "resolved":
            return cached.get("result")

        # Do not reuse stale "not_found" cache entries.
        # Retry with the current normalization/query strategy.

    # --------------------------------------------------------
    # QUERY
    # --------------------------------------------------------

    query_parts = [
        str(value).strip()
        for value in (
            location,
            region,
            country,
        )
        if value and not _missing(value)
    ]

    query = ", ".join(
        query_parts
    )

    # --------------------------------------------------------
    # RATE LIMIT
    # --------------------------------------------------------

    global _LAST_REQUEST

    wait = (
        MIN_REQUEST_INTERVAL
        - (
            time.monotonic()
            - _LAST_REQUEST
        )
    )

    if wait > 0:
        time.sleep(wait)

    _LAST_REQUEST = time.monotonic()

    # --------------------------------------------------------
    # NOMINATIM
    # --------------------------------------------------------

    try:

        response = requests.get(
            NOMINATIM_URL,
            params={
                "q": query,
                "format": "jsonv2",
                "limit": 5,
                "addressdetails": 1,
                "accept-language": "en",
            },
            headers={
                "User-Agent": USER_AGENT,
            },
            timeout=REQUEST_TIMEOUT,
        )

        response.raise_for_status()

        results = response.json()

    except Exception as exc:

        logger.warning(
            "Location geocoding failed for %s: %s",
            query,
            exc,
        )

        # DO NOT cache network failures.
        #
        # If Nominatim temporarily fails, we want the
        # next import to be able to retry.

        return None

    if not isinstance(
        results,
        list,
    ):
        results = []

    # --------------------------------------------------------
    # NORMALIZE RESULTS
    # --------------------------------------------------------

    normalized = []

    for item in results:

        try:

            address = (
                item.get("address")
                or {}
            )

            latitude = float(
                item["lat"]
            )

            longitude = float(
                item["lon"]
            )

        except (
            KeyError,
            TypeError,
            ValueError,
        ):
            continue

        feature_class = (
            item.get("class")
            or ""
        )

        feature_type = (
            item.get("type")
            or ""
        )

        is_waterway = (
            feature_class == "waterway"
            or feature_type
            in {
                "river",
                "stream",
                "canal",
                "waterway",
            }
        )

        if is_waterway:
            confidence = "high"
        else:
            confidence = "medium"

        normalized.append(
            {
                "latitude":
                    latitude,

                "longitude":
                    longitude,

                "display_name":
                    (
                        item.get(
                            "display_name"
                        )
                        or query
                    ),

                "country":
                    address.get(
                        "country"
                    ),

                "region":
                    (
                        address.get("state")
                        or address.get("region")
                        or address.get("province")
                    ),

                "area":
                    (
                        address.get("city")
                        or address.get("town")
                        or address.get("village")
                        or address.get("municipality")
                    ),

                "source":
                    "OpenStreetMap Nominatim",

                "resolution":
                    "location_geocoded",

                "confidence":
                    confidence,

                "feature_class":
                    feature_class,

                "feature_type":
                    feature_type,
            }
        )

    # --------------------------------------------------------
    # PREFER WATER FEATURES
    # --------------------------------------------------------

    water_results = [
        result
        for result in normalized
        if (
            result["feature_class"]
            == "waterway"
            or result["feature_type"]
            in {
                "river",
                "stream",
                "canal",
                "waterway",
            }
        )
    ]

    best = (
        water_results[0]
        if water_results
        else (
            normalized[0]
            if normalized
            else None
        )
    )

    # --------------------------------------------------------
    # CACHE RESULT
    # --------------------------------------------------------

    _CACHE[key] = {
        "status":
            (
                "resolved"
                if best
                else "not_found"
            ),

        "query":
            query,

        "result":
            best,
    }

    _save()

    return best


# ============================================================
# LOCATION NORMALIZATION
# ============================================================

def normalize_location_name(value):
    """
    Normalize messy PDF-extracted location names.

    This does NOT change the scientific meaning of the
    location. It only removes obvious PDF extraction noise.
    """

    if value is None:
        return ""

    text = str(value)

    text = unicodedata.normalize(
        "NFKC",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    replacements = {
        "Artificia l": "Artificial",
        "Ambernat h": "Ambernath",
        "Pandarpur": "Pandharpur",
        "Ichalkara nji": "Ichalkaranji",
        "Gandhigra m": "Gandhigram",
        "Gawal Ali": "Gawal Ali",
        "Kolha pur": "Kolhapur",
        "Kalyan": "Kalyan",
        "Nashik": "Nashik",
        "Chiplun": "Chiplun",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"\s*,\s*", ", ", text)
    text = re.sub(r"\s*-\s*", "-", text)

    return text.strip()


# ============================================================
# GEOCODING QUERY BUILDER
# ============================================================

def build_geocoding_query(
    location,
    country=None,
    region=None,
):
    """
    Build a more precise geocoding query from the information
    already present in the PDF.
    """

    parts = []

    location = normalize_location_name(location)

    if location:
        parts.append(location)

    if region:
        region = normalize_location_name(region)

        if region and region.lower() not in {
            location.lower(),
        }:
            parts.append(region)

    if country:
        country = normalize_location_name(country)

        if country and country.lower() not in {
            location.lower(),
        }:
            parts.append(country)

    return ", ".join(
        part
        for part in parts
        if part
    )


# ============================================================
# DATAFRAME LOCATION RESOLUTION
# ============================================================

def resolve_location_with_fallbacks(
    location,
    country=None,
    region=None,
):
    """
    Resolve a sampling location using progressively
    broader geographic queries.

    Example:

        Pawana River at Pimpri, Tal-Haveli, Pune
            ↓
        Pawana River at Pimpri, Pune, Maharashtra
            ↓
        Pawana River, Pune, Maharashtra
            ↓
        Pune, Maharashtra
    """

    location = str(location or "").strip()

    if not location:
        return None

    queries = []

    # --------------------------------------------------------
    # 1. Full location
    # --------------------------------------------------------

    full_parts = [
        location,
        region,
        country,
    ]

    full_query = ", ".join(
        str(value).strip()
        for value in full_parts
        if value and str(value).strip()
    )

    if full_query:
        queries.append(full_query)

    # --------------------------------------------------------
    # 2. Clean common sampling-detail noise
    # --------------------------------------------------------

    cleaned = re.sub(
        r"\b(Tal|Taluka|Tq|Dist|District)\.?\s*[-:]?",
        "",
        location,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"\s+",
        " ",
        cleaned,
    ).strip()

    cleaned_parts = [
        cleaned,
        region,
        country,
    ]

    cleaned_query = ", ".join(
        str(value).strip()
        for value in cleaned_parts
        if value and str(value).strip()
    )

    if (
        cleaned_query
        and cleaned_query not in queries
    ):
        queries.append(cleaned_query)

    # --------------------------------------------------------
    # 3. Try river/location name + region
    # --------------------------------------------------------

    simplified = re.sub(
        r"\b("
        r"near|at|village|vill\.?|tal|taluka|"
        r"tq|dist|district|road|bridge|"
        r"highway|naka|area|water sample|"
        r"water sample collected"
        r")\b.*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip(" ,.-")

    simplified_parts = [
        simplified,
        region,
        country,
    ]

    simplified_query = ", ".join(
        str(value).strip()
        for value in simplified_parts
        if value and str(value).strip()
    )

    if (
        simplified_query
        and simplified_query not in queries
    ):
        queries.append(simplified_query)

    # --------------------------------------------------------
    # 4. Final regional fallback
    # --------------------------------------------------------

    if region:
        regional_query = ", ".join(
            str(value).strip()
            for value in [
                region,
                country,
            ]
            if value and str(value).strip()
        )

        if (
            regional_query
            and regional_query not in queries
        ):
            queries.append(regional_query)

    # --------------------------------------------------------
    # Execute queries
    # --------------------------------------------------------

    for query in queries:

        logger.info(
            "Location fallback query: %s",
            query,
        )

        result = resolve_location(
            query,
            country,
            region,
        )

        if result:
            result = dict(result)

            result["resolution"] = (
                result.get(
                    "resolution",
                    "location_geocoded",
                )
            )

            return result

    return None





def build_geoapify_retry_query(
    location,
    country=None,
    region=None,
):
    """
    Build a focused second-pass query for locations that the
    first Geoapify query could not resolve.

    The first pass keeps the full PDF sampling description.
    The second pass removes sampling boilerplate while keeping
    the actual locality, district and state/country context.
    """

    text = normalize_location_name(
        location
    )

    # Remove common laboratory/PDF boilerplate.
    text = re.sub(
        r"\b("
        r"water\s+sample|water\s+sample\s+collected|"
        r"ganesh\s+festival[- ]?water\s+sample|"
        r"ganesh[- ]festival[- ]water\s+sample|"
        r"sample\s+collected|"
        r"well\s+water\s+sample|"
        r"water\s+quality\s+sample"
        r")\b",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # Remove administrative labels but retain their values.
    text = re.sub(
        r"\b(Tal|Taluka|Tq|Dist|District)\.?\s*[-:]?",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # Normalize punctuation left behind by the cleanup.
    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    text = re.sub(
        r",\s*,+",
        ", ",
        text,
    )

    text = text.strip(
        " ,.-"
    )

    # Prefer a water-body + locality style query.
    water_match = re.search(
        r"(.+?\b"
        r"(?:river|lake|creek|dam|reservoir|"
        r"khadi|talav|talao|nalla|canal|"
        r"pond|stream)"
        r"\b)",
        text,
        flags=re.IGNORECASE,
    )

    if water_match:
        water_body = water_match.group(
            1
        ).strip(" ,.-")

        # Keep the remaining locality if it exists.
        remainder = text[
            water_match.end():
        ].strip(" ,.-")

        if remainder:
            text = (
                f"{water_body}, {remainder}"
            )
        else:
            text = water_body

    return build_geocoding_query(
        location=text,
        country=country,
        region=region,
    )



def _submit_geoapify_batch_queries(
    batch_locations,
    queries,
    batch_label="primary",
):
    """
    Submit one Geoapify batch and wait for its result.
    """

    if not batch_locations:
        return {}, {}

    logger.info(
        "Geoapify %s batch: submitting %s locations",
        batch_label,
        len(batch_locations),
    )

    try:
        response = requests.post(
            GEOAPIFY_BATCH_URL,
            params={
                "apiKey": GEOAPIFY_API_KEY,
                "lang": "en",
            },
            json=queries,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=REQUEST_TIMEOUT,
        )

        response.raise_for_status()
        job = response.json()

    except Exception as exc:
        logger.exception(
            "Geoapify %s batch submission failed: %s",
            batch_label,
            exc,
        )
        return {}, {
            location: {
                "location": location,
                "country": country,
                "region": region,
                "suggested_query": query,
                "reason": (
                    "Geoapify batch submission failed."
                ),
            }
            for (
                (key, location, country, region),
                query,
            ) in zip(
                batch_locations,
                queries,
            )
        }

    job_id = job.get(
        "id"
    )

    if not job_id:
        logger.error(
            "Geoapify %s batch did not return a job id: %s",
            batch_label,
            job,
        )
        return {}, {}

    logger.info(
        "Geoapify %s batch job created: %s",
        batch_label,
        job_id,
    )

    result_url = job.get(
        "url"
    )

    # Geoapify's returned URL already contains authentication.
    if not result_url:
        result_url = GEOAPIFY_BATCH_URL

    results = None

    for attempt in range(
        1,
        GEOAPIFY_MAX_POLL_ATTEMPTS + 1,
    ):

        try:

            if attempt > 1:
                time.sleep(
                    GEOAPIFY_POLL_INTERVAL
                )

            poll_params = {
                "format": "json",
            }

            # Only add authentication if Geoapify did not
            # provide a fully-qualified result URL.
            if not job.get(
                "url"
            ):
                poll_params.update({
                    "id": job_id,
                    "apiKey": GEOAPIFY_API_KEY,
                })

            poll = requests.get(
                result_url,
                params=poll_params,
                headers={
                    "Accept": "application/json",
                },
                timeout=REQUEST_TIMEOUT,
            )

            poll.raise_for_status()
            payload = poll.json()

        except Exception as exc:
            logger.warning(
                "Geoapify %s batch poll %s/%s failed: %s",
                batch_label,
                attempt,
                GEOAPIFY_MAX_POLL_ATTEMPTS,
                exc,
            )
            continue

        if isinstance(
            payload,
            list,
        ):
            results = payload
            break

        if isinstance(
            payload,
            dict,
        ):

            status = payload.get(
                "status",
                "",
            )

            if status in {
                "pending",
                "processing",
                "running",
            }:
                logger.info(
                    "Geoapify %s batch job %s still processing (%s/%s)",
                    batch_label,
                    job_id,
                    attempt,
                    GEOAPIFY_MAX_POLL_ATTEMPTS,
                )

            if payload.get(
                "results"
            ) is not None:
                results = payload.get(
                    "results"
                )
                break

            if status in {
                "failed",
                "error",
                "cancelled",
            }:
                logger.error(
                    "Geoapify %s batch job %s failed: %s",
                    batch_label,
                    job_id,
                    payload,
                )
                break

    if results is None:
        return {}, {
            location: {
                "location": location,
                "country": country,
                "region": region,
                "suggested_query": query,
                "reason": (
                    "Geoapify batch job timed out."
                ),
            }
            for (
                (key, location, country, region),
                query,
            ) in zip(
                batch_locations,
                queries,
            )
        }

    resolved = {}
    unresolved = {}

    for position, item in enumerate(
        results
    ):

        if position >= len(
            batch_locations
        ):
            break

        (
            key,
            location,
            country,
            region,
        ) = batch_locations[position]

        if not isinstance(
            item,
            dict,
        ):
            item = {}

        try:
            latitude = float(
                item.get("lat")
            )
            longitude = float(
                item.get("lon")
            )
        except (
            TypeError,
            ValueError,
        ):
            latitude = None
            longitude = None

        if (
            latitude is not None
            and longitude is not None
            and -90 <= latitude <= 90
            and -180 <= longitude <= 180
        ):

            rank = item.get(
                "rank"
            ) or {}

            resolved[key] = {
                "latitude": latitude,
                "longitude": longitude,
                "resolution": "location_geocoded",
                "resolved_query": queries[
                    position
                ],
                "confidence": rank.get(
                    "confidence",
                    "medium",
                ),
                "provider": "geoapify",
                "formatted": item.get(
                    "formatted"
                ),
                "result_type": item.get(
                    "result_type"
                ),
                # Geoapify batch results return country/state at the
                # top level (not nested under "address" like Nominatim).
                # These were previously never captured, so
                # resolve_dataframe_locations() had nothing to
                # backfill into the country/region columns even for
                # rows that resolved successfully.
                "country": item.get(
                    "country"
                ),
                "region": (
                    item.get("state")
                    or item.get("county")
                ),
                "area": (
                    item.get("city")
                    or item.get("district")
                    or item.get("suburb")
                ),
            }

        else:

            unresolved[location] = {
                "location": location,
                "country": country,
                "region": region,
                "suggested_query": queries[
                    position
                ],
                "reason": (
                    "Geoapify could not resolve "
                    "reliable coordinates."
                ),
            }

    # Defensive handling for missing result entries.
    for position in range(
        len(results),
        len(batch_locations),
    ):

        (
            key,
            location,
            country,
            region,
        ) = batch_locations[position]

        unresolved[location] = {
            "location": location,
            "country": country,
            "region": region,
            "suggested_query": queries[
                position
            ],
            "reason": (
                "Geoapify returned no result."
            ),
        }

    logger.info(
        "Geoapify %s batch complete: resolved=%s unresolved=%s",
        batch_label,
        len(resolved),
        len(unresolved),
    )

    return resolved, unresolved


def resolve_locations_with_geoapify_retry(
    unresolved_locations,
):
    """
    Retry only locations that failed the first Geoapify batch.

    This deliberately performs ONE additional batch instead of
    falling back to hundreds of individual Nominatim calls.
    """

    if not unresolved_locations:
        return {}, {}

    retry_locations = []

    for item in unresolved_locations:

        if not isinstance(item, dict):
            continue

        location = normalize_location_name(
            item.get("location")
        )

        if not location:
            continue

        country = normalize_location_name(
            item.get("country")
        )

        region = normalize_location_name(
            item.get("region")
        )

        key = _key(
            location,
            country,
            region,
        )

        retry_locations.append(
            (
                key,
                location,
                country,
                region,
            )
        )

    if not retry_locations:
        return {}, {}

    logger.info(
        "Geoapify second-pass retry: %s unresolved locations",
        len(retry_locations),
    )

    # Build focused queries instead of the original noisy PDF text.
    queries = [
        build_geoapify_retry_query(
            location=location,
            country=country,
            region=region,
        )
        for (
            key,
            location,
            country,
            region,
        ) in retry_locations
    ]

    return _submit_geoapify_batch_queries(
        retry_locations,
        queries,
        batch_label="retry",
    )



def resolve_locations_with_geoapify_batch(
    locations,
):
    """
    First-pass Geoapify batch.
    """

    if not locations:
        return {}, {}

    if not GEOAPIFY_API_KEY:
        return None, None

    batch_locations = locations[
        :GEOAPIFY_BATCH_SIZE
    ]

    queries = [
        build_geocoding_query(
            location=location,
            country=country,
            region=region,
        )
        for (
            key,
            location,
            country,
            region,
        ) in batch_locations
    ]

    return _submit_geoapify_batch_queries(
        batch_locations,
        queries,
        batch_label="primary",
    )



def resolve_dataframe_locations(
    df,
    location_col,
    country_col=None,
    region_col=None,
    max_requests=50,
):
    """
    Resolve textual locations in a dataframe.

    IMPORTANT:

    - Existing coordinates are never overwritten.
    - Duplicate locations are resolved only once.
    - Cached locations do not trigger network requests.
    - Geoapify batch geocoding handles uncached locations.
    - Remaining unresolved locations are returned for frontend review.
    """

    df = df.copy()

    if not location_col:
        return df, []

    # --------------------------------------------------------
    # Ensure coordinate columns exist
    # --------------------------------------------------------

    if "latitude" not in df.columns:
        df["latitude"] = float("nan")
    else:
        df["latitude"] = pd.to_numeric(
            df["latitude"],
            errors="coerce",
        )

    if "longitude" not in df.columns:
        df["longitude"] = float("nan")
    else:
        df["longitude"] = pd.to_numeric(
            df["longitude"],
            errors="coerce",
        )

    # --------------------------------------------------------
    # Collect unique locations
    # --------------------------------------------------------

    unique_locations = []
    seen = set()

    for index, row in df.iterrows():

        raw_location = row.get(
            location_col,
            "",
        )

        # Missing / NaN
        if raw_location is None:
            continue

        try:
            if pd.isna(raw_location):
                continue
        except (
            TypeError,
            ValueError,
        ):
            pass

        location = normalize_location_name(
            raw_location
        )

        # Empty
        if not location:
            continue

        # Null-like values
        if location.lower() in {
            "nan",
            "none",
            "null",
            "n/a",
            "na",
            "-",
            "--",
        }:
            continue

        # PDF-generated placeholders
        if re.fullmatch(
            r"row\s+\d+",
            location,
            flags=re.IGNORECASE,
        ):
            continue

        # ----------------------------------------------------
        # Existing valid coordinates
        # ----------------------------------------------------

        try:

            latitude = float(
                row.get("latitude")
            )

            longitude = float(
                row.get("longitude")
            )

            if (
                -90 <= latitude <= 90
                and -180 <= longitude <= 180
            ):
                continue

        except (
            TypeError,
            ValueError,
        ):
            pass

        country = (
            normalize_location_name(
                row.get(country_col)
            )
            if country_col
            else ""
        )

        if country.lower() in {
            "nan",
            "none",
            "null",
        }:
            country = ""

        region = (
            normalize_location_name(
                row.get(region_col)
            )
            if region_col
            else ""
        )

        if region.lower() in {
            "nan",
            "none",
            "null",
        }:
            region = ""

        key = _key(
            location,
            country,
            region,
        )

        # ----------------------------------------------------
        # Deduplicate
        # ----------------------------------------------------

        if key in seen:
            continue

        seen.add(key)

        unique_locations.append(
            (
                key,
                location,
                country,
                region,
            )
        )

    logger.info(
        "Location resolution: %s unique valid locations found",
        len(unique_locations),
    )

    # --------------------------------------------------------
    # Resolve locations
    # --------------------------------------------------------

    resolved = {}
    unresolved = {}
    external_requests = 0

    # --------------------------------------------------------
    # Resolve cached locations first.
    # --------------------------------------------------------

    locations_to_geocode = []

    for (
        key,
        location,
        country,
        region,
    ) in unique_locations:

        _load()

        cached = _CACHE.get(key)

        if cached:
            cached_status = cached.get(
                "status"
            )

            if cached_status == "resolved":
                cached_result = cached.get(
                    "result"
                )

                if cached_result:
                    resolved[key] = (
                        cached_result
                    )
                    continue

        locations_to_geocode.append(
            (
                key,
                location,
                country,
                region,
            )
        )

    # --------------------------------------------------------
    # Geoapify batch geocoding.
    #
    # One PDF with ~183 unique locations fits in one
    # Geoapify batch because the API accepts up to 1000
    # addresses per batch.
    # --------------------------------------------------------

    if locations_to_geocode:

        geo_resolved, geo_unresolved = (
            resolve_locations_with_geoapify_batch(
                locations_to_geocode
            )
        )

        # If no Geoapify key is configured, preserve the
        # existing resolver as a development fallback.
        if (
            geo_resolved is None
            and geo_unresolved is None
        ):

            for (
                key,
                location,
                country,
                region,
            ) in locations_to_geocode:

                if (
                    external_requests
                    >= MAX_GEOCODING_LOCATIONS
                ):
                    unresolved[location] = {
                        "location": location,
                        "country": country,
                        "region": region,
                        "suggested_query":
                            build_geocoding_query(
                                location=location,
                                country=country,
                                region=region,
                            ),
                        "reason": (
                            "Geoapify API key is not configured "
                            "and the fallback geocoding limit "
                            "was reached."
                        ),
                    }
                    continue

                external_requests += 1

                query = build_geocoding_query(
                    location=location,
                    country=country,
                    region=region,
                )

                result = resolve_location(
                    query,
                    country,
                    region,
                )

                if result:
                    resolved[key] = result
                else:
                    unresolved[location] = {
                        "location": location,
                        "country": country,
                        "region": region,
                        "suggested_query": query,
                        "reason": (
                            "Could not resolve coordinates "
                            "automatically."
                        ),
                    }

        else:

            if geo_resolved:
                resolved.update(
                    geo_resolved
                )

            if geo_unresolved:
                # ------------------------------------------------
                # Second-pass smart retry.
                # ------------------------------------------------
                retry_resolved, retry_unresolved = (
                    resolve_locations_with_geoapify_retry(
                        list(
                            geo_unresolved.values()
                        )
                    )
                )

                if retry_resolved:
                    geo_resolved.update(
                        retry_resolved
                    )

                if retry_unresolved:
                    unresolved.update(
                        retry_unresolved
                    )

            # Merge primary + retry results.
            if geo_resolved:
                resolved.update(
                    geo_resolved
                )

            # Cache all successful Geoapify results so
            # future imports do not geocode the same location.
            for (
                key,
                location,
                country,
                region,
            ) in locations_to_geocode:

                if key in resolved:

                    _CACHE[key] = {
                        "status": "resolved",
                        "query":
                            resolved[key].get(
                                "resolved_query"
                            ),
                        "result":
                            resolved[key],
                    }

            _save()

    logger.info(
        "Location resolution complete: "
        "resolved=%s unresolved=%s external_requests=%s",
        len(resolved),
        len(unresolved),
        external_requests,
    )

    # --------------------------------------------------------
    # Apply resolved coordinates
    # --------------------------------------------------------

    for index, row in df.iterrows():

        raw_location = row.get(
            location_col,
            "",
        )

        # IMPORTANT:
        # Empty PDF rows are simply ignored.
        #
        # DO NOT add "Row N" to unresolved.
        if raw_location is None:
            continue

        try:
            if pd.isna(raw_location):
                continue
        except (
            TypeError,
            ValueError,
        ):
            pass

        location = normalize_location_name(
            raw_location
        )

        if not location:
            continue

        # Ignore PDF placeholders.
        if re.fullmatch(
            r"row\s+\d+",
            location,
            flags=re.IGNORECASE,
        ):
            continue

        # Ignore null-like values.
        if location.lower() in {
            "nan",
            "none",
            "null",
            "n/a",
            "na",
            "-",
            "--",
        }:
            continue

        country = (
            normalize_location_name(
                row.get(country_col)
            )
            if country_col
            else ""
        )

        if country.lower() in {
            "nan",
            "none",
            "null",
        }:
            country = ""

        region = (
            normalize_location_name(
                row.get(region_col)
            )
            if region_col
            else ""
        )

        if region.lower() in {
            "nan",
            "none",
            "null",
        }:
            region = ""

        key = _key(
            location,
            country,
            region,
        )

        result = resolved.get(key)

        # ----------------------------------------------------
        # Existing coordinates
        # ----------------------------------------------------

        try:

            latitude = float(
                row.get("latitude")
            )

            longitude = float(
                row.get("longitude")
            )

            if (
                -90 <= latitude <= 90
                and -180 <= longitude <= 180
            ):
                continue

        except (
            TypeError,
            ValueError,
        ):
            pass

        # ----------------------------------------------------
        # No resolution
        # ----------------------------------------------------

        if not result:
            continue

        # ----------------------------------------------------
        # Apply coordinates
        # ----------------------------------------------------

        df.at[
            index,
            "latitude",
        ] = result["latitude"]

        df.at[
            index,
            "longitude",
        ] = result["longitude"]

        df.at[
            index,
            "location_resolution",
        ] = result.get(
            "resolution",
            "location_geocoded",
        )

        df.at[
            index,
            "location_confidence",
        ] = result.get(
            "confidence",
            "medium",
        )

        df.at[
            index,
            "location_source",
        ] = result.get(
            "source",
            "OpenStreetMap Nominatim",
        )

        # ----------------------------------------------------
        # Fill missing geography
        # ----------------------------------------------------

        if (
            country_col
            and result.get("country")
            and _missing(
                row.get(country_col)
            )
        ):

            df.at[
                index,
                country_col,
            ] = result["country"]

        if (
            region_col
            and result.get("region")
            and _missing(
                row.get(region_col)
            )
        ):

            df.at[
                index,
                region_col,
            ] = result["region"]

    logger.info(
        "Location resolution complete: "
        "resolved=%s unresolved=%s external_requests=%s",
        len(resolved),
        len(unresolved),
        external_requests,
    )

    return (
        df,
        list(unresolved.values()),
    )