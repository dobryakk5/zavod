# Frontend Testing Strategy

## Current State

- Backend has a documented testing strategy and coverage gate in `/backend/tests/README.md` and `/backend/pytest.ini`.
- Frontend previously had no local test runner config, no test scripts, and no documented test strategy in `frontend/`.

## Goals (Frontend)

1. Cover reusable logic and shared UI first.
2. Add integration tests for high-risk flows (auth, forms, scheduling, publishing dialogs).
3. Add end-to-end tests only for core user journeys after unit/integration basics are stable.

## Priority Order

1. `frontend/lib/*` pure functions (date/timezone transforms, parsing, formatting, guards).
2. `frontend/components/ui/*` primitives used across many screens.
3. Stateful feature components with business impact:
   - auth/connect flows
   - posting/scheduling dialogs
   - payment/trial-limit handling
   - settings forms
4. Page-level integration tests for critical routes.

## Test Types

- Unit tests (`Vitest`): pure functions, formatters, reducers, small hooks.
- Component tests (`Vitest` + `@testing-library/react`): rendering, interaction, props/state behavior.
- E2E (later): cross-page flows and backend integration boundaries.

## Rules

- Mock network/API calls at module boundary (`frontend/lib/api/*`).
- Keep tests deterministic (fixed dates/timezones, no real timers unless required).
- Prefer assertions on behavior and accessible output over implementation details.

## Commands

```bash
npm test
npm run test:coverage
```
