# Architecture

## Delivery boundary

```text
Browser (C) -> FastAPI routes (B) -> Agent Runtime (A, inside backend)
                                      |
                                      v
                               allowlisted Python tools
                                      |
                                      v
                             services/repositories (B)
```

The letters are ownership labels, not network services:

- **A — Agent**: prompt, intent selection, tool contracts, safe response composition and Agent tests.
- **B — backend/data/map**: FastAPI, validation, persistence boundary, pet service, location/map adapters and integration tests.
- **C — frontend/demo**: React UI, API client, loading/error states, demo data flow and presentation.

The Agent is imported and executed by the backend. It never calls the frontend and never sends HTTP requests to B. Its only capabilities are Python callables registered in an allowlist. A tool validates input, calls an injected service in process, and returns a stable `ToolResult`. Routes may also call ordinary services directly for CRUD.

## Priorities

P0 is pet CRUD plus personalized chat. P1 is nearby services. Streaming is deliberately optional/deferred: `POST /api/v1/chat` returns one JSON response, allowing the team to add SSE later without blocking the core demo.

## Runtime flow

1. C sends a validated chat request to B.
2. B attaches a request ID and calls A in process.
3. A selects at most the registered P0 tool (`get_pet_profile`) and validates its input.
4. The tool calls B's `PetService` directly and returns `success`, `not_found`, `invalid_input`, `unavailable`, or `error`.
5. A composes a concise answer. It never invents missing pet data and adds a veterinary disclaimer for medical topics.

## Data and identity

`user_id` is reserved in every relevant contract. Authentication is out of scope, so the only accepted value is the fixed demo user `demo-user`. The starter uses an in-memory repository seeded with one pet; B can replace the repository with SQLite without changing routes, tools or frontend types.

## P1 location boundary

Browser geolocation is WGS-84. Before a China map provider query, B validates the coordinate and converts WGS-84 to GCJ-02 only when it lies inside the mainland-China bounding check. Coordinates outside that boundary remain WGS-84 and must not be silently distorted. Conversion metadata is returned for observability.

If location is denied or unavailable, C sends a manual address. B geocodes it through an adapter; the scaffold uses deterministic mock geocoding and marks the source. A production adapter must return the coordinate system explicitly before nearby search.

## Dependency direction

```text
api -> agent -> tools -> services -> repository/integrations
api -----------------> services -> repository/integrations
```

No dependency points back toward API or frontend code. Secrets remain in backend environment variables.
