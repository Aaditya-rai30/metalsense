# MetalSense Final ML Engine Migration

This bundle splits the supplied `final_ml_seasonal.py` into backend engine modules.

## Engine files
- `data_quality_engine.py` — season-aware date inference + validation
- `standards_registry.py` — country-first standards selection and CSV registry loading
- `pollution_engine.py` — HPI/HEI/Cd calculations
- `anomaly_engine.py` — Isolation Forest anomaly scores
- `explainability_engine.py` — decision factors and report explanations
- `spatial_engine.py` — points, summaries and DBSCAN hotspots
- `temporal_engine.py` — seasonal date inference and temporal series
- `rag_engine.py` — TF-IDF retrieval over rag/standards documents
- `pipeline.py` — unified orchestration

## Important integration note
`services/dataset_service_ml.py` is a safe adapter rather than a blind replacement for the existing MongoDB CRUD/upload service. It is intended to be called after the existing secure upload parser returns a DataFrame.

The route files preserve the current service contracts and security middleware.

Do not overwrite the live `services/dataset_service.py` until its current export-import branch, geocoding, database response contract, and frontend field expectations are reconciled with the new engine output.
