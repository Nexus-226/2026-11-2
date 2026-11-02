# API contract

Base path: `/api/v1`. The demo reserves `user_id = "demo-user"`; other user IDs return validation or authorization errors until authentication exists.

## Chat — `POST /api/v1/chat`

Synchronous JSON is the P0 contract. Streaming is optional and deferred.

Request:

```json
{
  "user_id": "demo-user",
  "session_id": "optional-existing-session",
  "pet_id": "pet-demo-001",
  "message": "团子最近应该注意什么？"
}
```

Response:

```json
{
  "request_id": "req_...",
  "session_id": "session_...",
  "reply": "团子是……",
  "used_pet_id": "pet-demo-001",
  "tool_results": [
    {
      "tool": "get_pet_profile",
      "status": "success",
      "data": {"id": "pet-demo-001", "name": "团子"},
      "message": null
    }
  ]
}
```

Tool result statuses:

| Status | Meaning |
|---|---|
| `success` | Valid result returned. |
| `not_found` | Requested entity does not exist for the demo user. |
| `invalid_input` | Tool arguments failed validation. |
| `unavailable` | A dependency timed out or is temporarily unavailable. |
| `error` | Unexpected, non-sensitive failure. |

## Pets (P0)

- `GET /api/v1/pets?user_id=demo-user`
- `POST /api/v1/pets`
- `GET /api/v1/pets/{pet_id}?user_id=demo-user`
- `PATCH /api/v1/pets/{pet_id}`
- `DELETE /api/v1/pets/{pet_id}?user_id=demo-user`

Create example:

```json
{
  "user_id": "demo-user",
  "name": "团子",
  "species": "cat",
  "breed": "British Shorthair",
  "age_years": 3,
  "health_notes": "控制体重"
}
```

## Nearby services (P1 scaffold)

`GET /api/v1/nearby?user_id=demo-user&lat=31.2304&lng=121.4737&category=pet_hospital`

Or manual fallback:

`GET /api/v1/nearby?user_id=demo-user&address=上海市人民广场&category=pet_hospital`

Categories are `pet_hospital`, `pet_grooming`, and `pet_store`. Input browser coordinates are declared as WGS-84. The response includes normalized places plus `input_crs`, `provider_crs`, `coordinate_converted`, and `location_source`. The mock adapter is for development only.

## Errors

```json
{
  "error": {
    "code": "PET_NOT_FOUND",
    "message": "Pet was not found",
    "request_id": "req_...",
    "retryable": false
  }
}
```

FastAPI's standard `detail` response may still appear for request-schema validation in this starter; B owns convergence on the unified envelope during Day 2.
