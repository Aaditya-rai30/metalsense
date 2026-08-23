from __future__ import annotations

from typing import Any

import pandas as pd

from engine.pipeline import MetalSenseMLEngine


_engine = MetalSenseMLEngine()


def run_ml_dataframe(
    df: pd.DataFrame,
    dataset_id: str = "",
) -> dict[str, Any]:
    """Engine-facing adapter for services/dataset_service.py.

    Keep MongoDB CRUD/upload security in the existing dataset service; call this
    function after the secure upload parser produces a DataFrame.
    """
    return _engine.run_dataframe(df, dataset_id=dataset_id)
