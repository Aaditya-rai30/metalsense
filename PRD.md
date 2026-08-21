# MetalSense PRD

Cross-platform Expo app for traceable heavy-metal pollution intelligence in water quality.

## Core requirements

- Authentication, professional signup branching, profile, and genuinely empty first-run dashboard.
- CSV/XLSX import only with blocking validation errors and persisted real datasets.
- Actual coordinate detection, reverse geolocation, standards selection with WHO fallback, deterministic HPI/HEI/Cd.
- Data quality, pollution status, spatial/temporal analysis, analytics, reports, decisions, deletion, and real CSV/XLSX/PDF exports.
- Light-only MetalSense palette and responsive iOS, Android, Expo web UX.

## Design handoff

See /app/design_guidelines.json.

## Implemented (2026-08-18)

- Built cross-platform Expo authentication with professional account-type onboarding, independent-researcher handling, persistence, sign-out, and MetalSense branding.
- Built empty-first dashboard, CSV/XLSX intake, server-side parsing/validation, coordinate range checks, reverse-geocode provenance, MongoDB dataset persistence, and blocking validation feedback.
- Built deterministic heavy-metal ratio analysis with HPI/HEI/Cd, status classification, data-quality scoring, quality/analysis/spatial/report/profile screens, dataset deletion, and real CSV export.
- Added Expo-compatible document picking, responsive desktop sidebar/mobile navigation, accessibility test hooks, light-only palette, and API compatibility fallback for EXPO_BACKEND_URL / EXPO_PUBLIC_BACKEND_URL.

## Prioritized backlog

- P0: Add table-level sample selection, individual sample deletion, select-all/clear, and clear-all confirmation.
- P0: Complete real XLSX and professional PDF exports with metadata and report sections.
- P1: Add a native map view with accessible list fallback and marker drill-down.
- P1: Add temporal trend charts and metal contribution summaries from persisted records.
- P2: Add standards registry with versioned regional rules and mismatch comparison against uploaded location fields.
