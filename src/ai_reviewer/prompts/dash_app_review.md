# Dash Application Review Standards

Target: {repository} / PR #{pr_number}

This document defines standards for Plotly Dash applications in gds-idea projects.
It serves as both a human-readable reference and the automated reviewer's criteria.
Treat a Dash application as a reactive system with explicit state ownership and
observable callback boundaries — the same model as any other event-driven UI.

**Scope:** files under an `app_src/`-style Dash application root (or any directory
containing a Dash app entrypoint); any file importing `dash`, `dash.html`,
`dash.dcc`, `dash_bootstrap_components`, or `plotly.graph_objects`/`plotly.express`
for an app layout; any file containing `@app.callback`/`@callback`; clientside
callback JS under `assets/`.

**Out of scope:** AWS CDK/infrastructure that deploys the app (delegate to the CDK
reviewer), general Python bugs/security not specific to Dash's reactive model
(delegate to the code reviewer), docstring wording (delegate to the docstring
reviewer), README files (delegate to the README reviewer), and any AI
agent/LLM-orchestration code the app embeds (e.g. a knowledge-base search agent,
MCP tool servers, RAG pipelines) — that is an agent-engineering concern, not a
Dash reactive-system concern, even when it lives inside the same `app_src/`.

**How to review:** Work from the PR diff you already have from the code review.
For each new or modified callback, identify its trigger (`Input`), its
dependencies (`State`), its outputs, and the state it reads or writes. Judge
whether that one callback represents a single, coherent state transition, not
whether the file as a whole "looks like Dash code".

## 1. Component ID Conventions

### Use stable, namespaced identifiers — never inline string literals

- Component IDs must come from a single source of truth per page/section (e.g.
  an `Enum`/`StrEnum` such as `class OverviewPage(StrEnum): ...`), not string
  literals typed inline at each `Input`/`Output`/component definition.
- IDs should be namespaced by page or component (`"OverviewPage-DATE_FILTER"`,
  not `"date_filter"`) so the same visual concept in two different pages
  (e.g. two "Clear" buttons) cannot collide.
- Centralising IDs makes every `Input(...)`/`Output(...)` reference
  auto-completable and grep-able, and makes an ID typo a startup error instead
  of a callback that silently never fires.

**Bad — inline string literals, no namespace, easy to collide or typo:**
```python
dcc.Input(id="start-date")
...
@app.callback(Output("start-date", "value"), Input("clear-button", "n_clicks"))
```

**Good — centralised, namespaced, enumerable IDs:**
```python
# constants/ids.py
from enum import StrEnum, unique


@unique
class OverviewPage(StrEnum):
    START_DATE = "OverviewPage-START_DATE"
    CLEAR_DATE_BUTTON = "OverviewPage-CLEAR_DATE_BUTTON"


# dashboards/overview.py
from constants.ids import OverviewPage

dcc.Input(id=OverviewPage.START_DATE)

# callbacks/overview_callbacks.py
@app.callback(
    Output(OverviewPage.START_DATE, "value"),
    Input(OverviewPage.CLEAR_DATE_BUTTON, "n_clicks"),
)
```

**Flag when:** a new component introduces a raw string ID instead of extending
the existing ID enum/module, or reuses a short generic name (`"table"`,
`"button-1"`) that risks colliding with another page.

## 2. State Ownership

### Give every piece of state exactly one authoritative owner

- Component `value`/`children` props for local presentation state.
- `dcc.Store` for small browser-session state shared across callbacks/pages.
- URL (`dcc.Location`/`pathname`/query params) for shareable, navigable state.
- Server-side storage (a provider/service object, cache, or database) for
  large, sensitive, durable, or cross-user state.
- Do not copy the same value into two stores (or a store and a URL param)
  without an explicit, documented synchronisation rule for which one wins.
- **Never** put secrets, credentials, tokens, or sensitive records in a
  `dcc.Store` — its contents are visible in the browser (`localStorage`/
  `sessionStorage`/hidden DOM), unlike server-side session state.

**Bad — the same filter state exists in two places with no sync rule:**
```python
# Both of these get written to independently, so they can disagree
dcc.Store(id=Ids.APP_STATE)          # holds departments=[...]
dcc.Store(id=Ids.DEPARTMENT_CACHE)   # also holds departments=[...]
```

**Good — one typed state object, one store, serialised explicitly:**
```python
# state.py
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AppState:
    start_date: str | None = None
    departments: list[str] | None = None

    def to_dict(self) -> dict:
        return asdict(self)


dcc.Store(id=Ids.APP_STATE, storage_type="session")
```

**Flag when:** a secret, API key, or credential is written into a `dcc.Store`,
a hidden `dcc.Input`, or any prop serialised to the browser; or when the same
logical value is tracked in more than one store/URL param without a stated
precedence rule.

## 3. Callback Design

### One callback, one coherent state transition

- A callback should do one job describable in a single short sentence. Prefer
  a small output surface over one callback that updates many unrelated
  components "while it's there".
- Use `Input` only for things that should *trigger* the callback; use `State`
  for values the callback needs to read but that should not re-run it.
  Misclassifying a value as `Input` when it should be `State` causes the
  callback to re-fire on every keystroke/selection of an unrelated control.
- Extract the actual logic into plain functions outside the `@callback`
  decorator (in `utils/`, `transforms.py`, or similar) so it can be unit
  tested without running Dash. The callback body should mostly be: unpack
  arguments, call the plain function(s), return the result.
- Use `no_update`/`dash.exceptions.PreventUpdate` deliberately, with a comment
  explaining why the callback should not update in that branch — not as a
  default fallback added to silence an error.
- Prefer a small shared helper (e.g. `value_or_no_update(new, current)`) that
  returns `no_update` when a computed value already matches what is on
  screen, over repeating the same "if new == current: return no_update"
  comparison inline in every callback that needs it. This keeps the
  unnecessary-write check consistent and makes callback bodies read as the
  happy path.

**Good — shared helper avoids repeating the same no-op check everywhere:**
```python
# utils/updates.py
def value_or_no_update(desired, current):
    """Return `desired`, or `no_update` if it already matches `current`."""
    return no_update if desired == current else desired


# callbacks/overview_callbacks.py
@app.callback(Output(Ids.DEPARTMENT_DROPDOWN, "value"), Input(Ids.URL, "pathname"))
def sync_department(pathname: str | None):
    desired = department_for_path(pathname)
    return value_or_no_update(desired, dash.callback_context.states.get("value"))
```


**Bad — business logic and Dash wiring tangled together, `Input`/`State`
misused so unrelated typing re-triggers a save:**
```python
@app.callback(
    Output(Ids.APP_STATE, "data"),
    Input(Ids.SEARCH_TEXT, "value"),
    Input(Ids.DEPARTMENT_DROPDOWN, "value"),  # should be State: shouldn't
)                                              # re-save on every keystroke
def save_filters(search_text, department):
    cleaned = search_text.strip().lower() if search_text else None
    departments = [department] if department else []
    # ... 40 more lines of ad hoc cleaning inline ...
    return {{"search": cleaned, "departments": departments}}
```

**Good — thin callback, pure function does the work, correct Input/State:**
```python
# utils/filters.py
def normalise_search_text(value: str | None) -> str | None:
    return value.strip().lower() if value else None


# callbacks/overview_callbacks.py
@app.callback(
    Output(Ids.APP_STATE, "data"),
    Input(Ids.SEARCH_TEXT, "value"),
    State(Ids.DEPARTMENT_DROPDOWN, "value"),
)
def save_filters(search_text: str | None, department: str | None) -> dict:
    """Persist the current search/department filters into app state."""
    return {{
        "search": normalise_search_text(search_text),
        "departments": [department] if department else [],
    }}
```

### Avoid feedback loops between saved state and visible controls

- When a callback both reads a saved `dcc.Store` value and writes to a
  control's `options`/`value`, prefer driving it from the other *visible*
  `Input`s on the page rather than the store, if a store round-trip could
  cause state → control → store → control cycling.
- If a genuine two-way sync between a store and a control is required, make
  sure only one direction fires on any given trigger (check `ctx.triggered_id`)
  so the two callbacks cannot re-trigger each other indefinitely.

**Flag when:** a callback's `Output` feeds back into another callback's
`Input` that in turn writes to the first callback's own `Input`/`State`,
with no `ctx.triggered_id` guard to break the cycle.

### Use pattern-matching and clientside callbacks only where they earn their keep

- Pattern-matching callbacks (`{{"type": "filter", "index": ALL}}`) are
  appropriate when the set of components is genuinely dynamic (a variable
  number of filter rows). Do not reach for them for a fixed, known set of
  components — plain IDs are simpler to read and type-check.
- Clientside callbacks (`ClientsideFunction`, `assets/*.js`) are for small,
  purely browser-side transforms where avoiding a server round trip has a
  measurable benefit (formatting, toggling a class). They should not duplicate
  business logic that also exists server-side — that becomes two
  implementations of the same rule that can drift apart.

## 4. Data Loading and Performance

### Do not repeat expensive work inside callback bodies

- Repeated database/Athena/API calls, or re-loading the same dataset, inside
  a callback that fires often (typing, filter changes) should go through a
  cached provider/service object instead of calling the data source directly
  each time.
- A data provider should have a clear refresh strategy (e.g. scheduled
  refresh, retry with backoff, and a last-known-good fallback on failure) so
  a transient upstream failure does not take down every page that reads it.
- Cache wrappers (`flask_caching`, `diskcache`) are only safe to add once the
  cache key, lifetime/TTL, invalidation trigger, and per-user isolation (if
  the data is user-specific) are understood and stated — an unscoped or
  unbounded cache is a correctness and memory risk.
- Long-running work (multi-second API calls, LLM calls, large exports) should
  use Dash's background-callback mechanism when the app already has one
  configured, rather than blocking the request/response cycle synchronously.

**Bad — hits the same API/DB on every filter change with no caching:**
```python
@app.callback(Output(Ids.CHART, "figure"), Input(Ids.DEPARTMENT_DROPDOWN, "value"))
def update_chart(department):
    data = fetch_from_athena(department)  # new query every keystroke/selection
    return build_chart(data)
```

**Good — a provider owns fetch/refresh/fallback; the callback just reads it:**
```python
# services/data_provider.py
class DataProvider:
    """Refreshes the dataset on a schedule, retries on failure, and falls
    back to the last successfully loaded snapshot if a refresh fails."""

    def get_dataframe(self) -> pd.DataFrame: ...
    def get_last_modified_at(self) -> datetime: ...


# callbacks/overview_callbacks.py
@app.callback(Output(Ids.CHART, "figure"), Input(Ids.DEPARTMENT_DROPDOWN, "value"))
def update_chart(department: str | None):
    data = DATA_PROVIDER.get_dataframe()
    return build_chart(filter_by_department(data, department))
```

### Avoid large or duplicated payloads in `dcc.Store`

- `dcc.Store` serialises to JSON and round-trips through the browser on every
  read/write — do not store an entire dataset or large table there when a
  small filter/id would let the callback re-derive the data server-side.
- Flag a `dcc.Store` write containing a full dataframe/record list where the
  same data is already available from a server-side provider.

## 5. Directory Structure and Separation of Concerns

### Keep layout, wiring, data, and logic in separate modules

- **Layouts** (`dashboards/`, `layouts.py`, `dashboard_pages/`) define page
  structure only — no data fetching, no business logic.
- **Callbacks** (`callbacks/`) wire `Input`/`Output`/`State` to plain
  functions — they translate between component values and application
  interfaces, they are not where the logic lives.
- **Chart/figure builders** (`charts/`) are pure functions: data in, a
  Plotly figure out — testable without Dash or a browser.
- **Constants** (`constants/ids.py`, formatting constants) centralise
  component IDs and shared literals.
- **Utils** (`utils/`) hold pure helper functions (date handling, filter
  normalisation, formatting) used by callbacks.
- **Services/providers** (`services/`) own data access, caching, and
  refresh — see Section 4.
- A callback file that also defines its own data-fetching logic, or a layout
  file that also builds a Plotly figure inline, is a sign a module is doing
  more than one job.

**Flag when:** a `callbacks/*.py` file makes a direct database/HTTP call
instead of going through a provider/service module, or a `dashboards/*.py`
layout file contains data transformation logic that belongs in `utils/` or a
chart builder.

## 6. Testing

### Test the pure functions directly, not by rendering Dash

- Filter/state transformation functions, chart builders, and formatters
  should have direct unit tests that call the function and assert on its
  return value — no Dash app instance or browser required.
- Mirror the source layout in `tests/` (e.g. `tests/callbacks/`,
  `tests/charts/`, `tests/utils/`) so the test for a given module is easy to
  find.
- For a callback itself, test its contract by importing and calling the
  underlying function directly (Dash callback functions are plain Python
  functions once decorated; call them as such) rather than trying to spin up
  a full app and simulate browser interaction, unless verifying the
  rendered interaction is genuinely the point of the test.

**Flag when:** new pure logic (a filter normaliser, a data transform, a chart
builder) ships with no direct unit test, especially when it replaces or
changes existing tested behaviour without an updated test.

## 7. Security and Configuration

### Keep secrets and auth off the client, and out of the diff

- Secrets, API keys, and credentials must be loaded from environment
  variables or a secrets manager — never hardcoded, and never placed in a
  `dcc.Store`, hidden input, or any other client-visible prop (see Section 2).
- Authentication/authorisation middleware should wrap the whole app (e.g. a
  `before_request` hook or auth middleware applied once at app construction),
  not be re-implemented per route or per callback.
- A health-check route (`/health`) should not require authentication or touch
  the data layer, so infra health checks are not blocked by auth or data
  outages.

## 8. Anti-Patterns to Flag

- **Raw string component IDs** instead of a centralised ID enum/module
- **Secrets or credentials in a `dcc.Store`, hidden input, or other
  client-visible prop**
- **The same state value tracked in more than one store/URL param** with no
  stated precedence rule
- **`Input` used for a value that should be `State`** (causes unwanted
  re-triggers), or vice versa (a control that should refresh but doesn't)
- **Business logic written inline inside a `@callback`-decorated function**
  instead of a testable plain function
- **`no_update`/`PreventUpdate` used with no comment explaining why**
- **Feedback loops between two callbacks** with no `ctx.triggered_id` guard
- **Direct database/API calls inside a frequently-firing callback** with no
  caching/provider layer
- **A full dataset or large record list written into `dcc.Store`** when a
  small filter/id would suffice
- **Data-fetching or transformation logic inside a layout file**
  (`dashboards/`, `layouts.py`) instead of `utils/`/`services/`
- **New filter/transform/chart-builder logic with no direct unit test**
- **Pattern-matching callbacks used for a fixed, known set of components**
  where plain IDs would be simpler
- **Clientside JS duplicating server-side business logic** instead of one
  being the source of truth
- **Unresolved merge conflict markers** (`<<<<<<<`, `=======`, `>>>>>>>`)

## 9. Do NOT Flag

- AI agent/LLM-orchestration code embedded in the same app (knowledge-base
  search agents, MCP tool servers, RAG/graph retrieval) — out of scope for
  this reviewer; that is an agent-engineering concern
- CDK/infrastructure that deploys the app — the CDK reviewer owns that
- Docstring wording/completeness on callback or helper functions — the
  docstring reviewer owns that; this reviewer may still flag a *missing*
  test or a logic issue in the same function
- Choices that are valid but different from a personal preference (e.g.
  `flask-caching` vs `diskcache` for background callbacks — both are valid
  caching mechanisms)
- Formatting issues already handled by a linter
- Pattern-matching callbacks used for a genuinely dynamic, variable-length
  set of components (e.g. a variable number of filter rows) — that is the
  correct tool for that job
- If there are no Dash application files added or modified in this PR,
  report that the Dash app review found nothing to flag — that is a valid,
  expected outcome
