# Decisions, assumptions and limitations

## Stack

| Choice | Why |
|---|---|
| Django 5.2 LTS + DRF | Mature ORM with real migrations, transactional DDL on PostgreSQL, strong validation primitives, drf-spectacular for OpenAPI. |
| PostgreSQL 16 | Required. Uses CHECK/UNIQUE/FK constraints, partial indexes, `pg_trgm` GIN indexes, views, `DISTINCT ON`, `FILTER` aggregates and JSONB for staged rows. |
| React 19 + Vite + TypeScript | Typed API contracts, fast dev server with an `/api` proxy (single origin). |
| TanStack Query | Server-state cache, request de-duplication, `keepPreviousData` for smooth pagination. |
| Recharts | Accessible enough for a donut chart; paired with a data table as the text alternative. |

## Data model

- **Natural keys as primary keys** (`C0001`, `A00001`, `T0000001`, ...). They are what users
  search for and what the source system uses. Surrogate keys would add a join everywhere for no
  benefit at this scale.
- **Prices are a separate table** (`instrument_price`) even though `instruments.csv` carries one
  price per instrument. Daily price loads can then append rather than update the security
  master, and the views always pick the latest price per instrument.
- **Holdings snapshots keep the snapshot date**; valuation uses each account's latest snapshot.
- **Amounts are non-negative magnitudes**; direction comes from `transaction_type`. A CHECK
  constraint also ties the row shape to the type (BUY/SELL need quantity and price > 0;
  DIVIDEND/FEE need both = 0).
- Goal ids for new goals come from a PostgreSQL sequence (`goal_number_seq`) that the goal
  import moves past the highest imported id.

## Data-quality findings and handling

Every input row is written to `import_staged_row` with its raw values, outcome and reasons, so
nothing disappears silently. Final tables only ever receive validated rows.

| Finding in the supplied data | Rows | Handling | Why |
|---|---|---|---|
| `transactions.csv`: `T0000026` appears twice with identical values | 1 | **Skipped as DUPLICATE** (first copy loaded) | Re-sent identical rows are a transport artefact, not new business events. Loading both would double-count a SELL. |
| `transactions.csv`: `T0004551` references instrument `I9999` | 1 | **Rejected** (quarantined) | Invalid FK; there is no safe way to guess the intended instrument. |
| `transactions.csv`: `T0004552` FEE with amount `-75` | 1 | **Rejected** | Amounts are magnitudes. Silently flipping the sign could hide a refund that should be a separate event type. |
| `transactions.csv`: `T0004553` dated `2027-01-05` | 1 | **Rejected** | A trade date in the future (relative to the import date) is not a valid booked trade, even when PENDING. |
| `holdings_snapshot.csv`: three positions repeated at the end of the file (`A00145/I0036`, `A00146/I0010`, `A00147/I0049`) | 3 | **Skipped as DUPLICATE**; a unique constraint on (account, snapshot_date, instrument) makes double counting impossible | Identical copies. Conflicting copies of the same key would be rejected instead. |
| 1,069 transactions dated before their account's `opened_at` | 1,069 | **Loaded with a warning** recorded on the staged row | Too widespread to be a deliberate defect, and likely a data-generation or back-dating artefact (transfers in). Rejecting a quarter of the ledger would make portfolios unusable; flagging keeps them visible for reconciliation (`docs/sql/reviewer_queries.sql` query 6). |
| Instruments with a blank `sector` | 48 | Stored as NULL | The dictionary marks sector nullable for non-equity instruments. |
| Goal names that do not match their `goal_type` (e.g. "Primary Retirement" with type EDUCATION) | many | Loaded as-is | Free-text name versus category; not a validation failure. |

Other rules enforced for every row: required fields, ID formats, enumerations, ISO dates,
decimal precision and range, FK existence, `amount = quantity × price` (±0.01) for trades,
`date_of_birth < onboarded_at`, risk score 0–100 (with a warning when the level does not match
the score band), and no future snapshot/assessment/price dates.

### Duplicate policy (never a silent overwrite)

1. The same file (SHA-256) can be applied once per dataset; a second upload returns `409`.
2. A row whose key already exists with **identical** values is skipped (idempotent overlap).
3. A row whose key already exists with **different** values is **rejected**. Corrections need
   an explicit workflow, not a re-import.
4. Within one file the first occurrence wins; later identical copies are skipped, later
   conflicting copies are rejected.

Valid rows of a batch are merged in **one database transaction** together with the staged rows.
If PostgreSQL rejects anything (a constraint validation missed), the whole batch rolls back and
is marked FAILED; the batch record itself is committed first so the failure stays auditable.

## Goals

- `funded_pct = current_funded_amount / target_amount` is computed server-side.
- Flags: **OVERDUE** (target date passed, not fully funded) and **OVERFUNDED** (funded > target).
  None of the supplied goals trigger them today, but imported goals with these properties are
  loaded with warnings and highlighted in the UI.
- Writes are stricter than imports: create/edit requires a positive target, non-negative funded
  amount not above the target, and a target date today or later (an existing past date may be
  kept when editing other fields). PATCH validates the merged result, not just changed fields.

## Authentication

- JWT access token (15 min) returned in the response body and kept **only in memory** in the
  SPA. Refresh token (8 h, rotated on each refresh) in an **httpOnly, SameSite=Strict cookie**
  scoped to `/api/v1/auth/`. XSS cannot read the refresh token; SameSite=Strict blocks CSRF on
  it; the access token never touches `localStorage`.
- A page reload calls `/auth/refresh` to restore the session.
- Roles: `VIEWER` (default, least privilege) and `ADMIN` (imports). Enforced by DRF permission
  classes on the API; the UI hides admin navigation but does not rely on that.
- Login is rate-limited (10/min per IP, counted per API worker because the throttle uses the
  in-process cache; a shared Redis cache would make it global) and nginx rate-limits `/api`
  (20 r/s, burst 40).

## Deliberate omissions

- **Server-side refresh-token revocation** (blacklist table). Logout clears the cookie; a stolen
  refresh token stays valid until expiry. Next step: enable simplejwt's blacklist app.
- **Object-level authorisation** (advisor ↔ customer assignment). Every signed-in user can see
  every customer, as in an internal service desk. Would be the first change for production.
- **Asynchronous imports.** Imports run in the request (the 4,554-row transactions file takes one to two seconds locally). A
  production version would hand larger files to a worker queue and poll batch status.
- **Holdings recomputation from transactions.** The snapshot is treated as the system of record
  for positions; transactions are a ledger for display and flows, not reconciled to positions.
- **Multi-currency.** All supplied data is INR; currency columns exist and are validated, but no
  FX conversion is implemented.
- **Edit/delete of transactions and other master data** through the UI.
- **TLS on localhost.** Plain HTTP as allowed; the report describes production TLS.

## Known limitations

- `goal_name` uniqueness is not enforced (the supplied data reuses names per customer).
- Customer search uses `ILIKE '%term%'` backed by trigram indexes; it is not ranked fuzzy search.
- The positions page sorts the (small) list of positions in the browser; all aggregation and
  totals come from SQL.
- Django creates `varchar_pattern_ops` (`*_like`) indexes for string primary keys; they are unused
  by current queries and could be dropped with a custom migration.
- Container images are built in CI but not pushed to a registry.
