# Three-day task checklist

## Priority order

1. **P0 contract freeze**: pet schemas, synchronous chat contract, tool statuses and fixed demo user.
2. **P0 vertical slice**: pet CRUD → select pet → personalized chat → readable failure state.
3. **P0 hardening**: medical disclaimer, missing-data behavior, tests and two full rehearsals.
4. **P1 only after P0 passes**: nearby list/map, coordinate conversion and manual-address fallback.

## Day 1 — independent slices

- [ ] A: finalize system prompt, `ToolResult`, allowlist and mock Agent tests.
- [ ] B: run `/health`, pet CRUD and seeded demo repository; publish OpenAPI.
- [ ] C: run Vite UI, pet form and chat states against mock/API client.
- [ ] Team: freeze P0 fields before end of day; no unreviewed contract changes.

## Day 2 — integration

- [ ] A: wire `get_pet_profile` in process; cover missing pet and medical wording.
- [ ] B: stabilize validation/errors and swap in persistence only if the slice remains green.
- [ ] C: connect pet CRUD and chat; cover loading, empty and failure states.
- [ ] Team: pass “save pet → ask question → personalized answer” without manual DB edits.

## Day 3 — demo first, P1 second

- [ ] A: tune concise answers; register nearby tool only if the P1 service is stable.
- [ ] B: validate WGS-84/GCJ-02 handling, mock/geocoding fallback and nearby sorting.
- [ ] C: rehearse P0; then add location permission, manual address and nearby list/map.
- [ ] Team: rehearse P0 twice, check no secrets, then decide whether P1 is demo-ready.

## Definition of done

- [ ] Fixed account `demo-user` works from a clean start.
- [ ] Pet create/read/update/delete works and failures are readable.
- [ ] Agent uses only registered in-process tools and does not fabricate missing data.
- [ ] Medical topics contain a professional-care warning.
- [ ] README startup/test/demo steps are current.
- [ ] At least one teammate reviews each responsibility boundary before merge.
