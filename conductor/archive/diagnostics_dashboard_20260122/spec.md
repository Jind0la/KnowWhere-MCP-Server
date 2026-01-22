# Specification: Diagnostics Dashboard

## Context
Users need to know if the KnowWhere Memory system is fully operational. A "black box" failure of the vector database or LLM provider can lead to silent failures in memory retrieval. This feature provides transparency into the system's health.

## Goals
- Provide a real-time view of all critical system components.
- Enable quick troubleshooting of connectivity issues (DB, Redis, External APIs).
- Visualize system latency.

## Requirements

### Backend
- **Endpoint:** `GET /health/full`
- **Checks:**
    - **PostgreSQL:** Connection status.
    - **Redis:** Connection status.
    - **Vector Search:** Latency check (ms).
    - **LLM Provider:** Availability check (API reachable).
- **Response Format:** JSON containing status (UP/DOWN/DEGRADED), latency, and optional error messages for each service.

### Frontend
- **Route:** `/dashboard/diagnostics`
- **UI Elements:**
    - Status grid showing cards for each service.
    - Visual indicators (Green dot = Healthy, Red dot = Error).
    - "Last Updated" timestamp.
    - Manual refresh button.
    - Auto-refresh every 30 seconds.
