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
Dash reactive-system concern, even when it lives inside the same `app_src/`. Also
out of scope: front-end accessibility audits, colour/design-system/typography
audits, cross-device/cross-browser compatibility, and dependency/framework
version freshness — see Section 10 for why and where each of those belongs.

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
  arguments, call the plain function(s), return the result. A callback is
  connective tissue between the front end and the back end, not the place
  business logic lives.
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
@app.callback(
    Output(Ids.DEPARTMENT_DROPDOWN, "value"),
    Input(Ids.URL, "pathname"),
    State(Ids.DEPARTMENT_DROPDOWN, "value"),
)
def sync_department(pathname: str | None, current_value: str | None):
    desired = department_for_path(pathname)
    return value_or_no_update(desired, current_value)
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

### Name callbacks for the state transition they perform, not the trigger

- Callback function names should describe *what changes*, using a
  consistent verb prefix — `update_`, `sync_`, `toggle_`, `display_` — not
  the triggering event (`on_click`, `handle_change`) and not a generic
  `callback_1`/`cb`.
- A consistent naming scheme makes it possible to grep for "everything that
  writes to X" or "everything that syncs filter state" across the codebase.

**Bad — names describe the trigger, not the effect, and give no clue what
they touch:**
```python
@app.callback(Output(Ids.DEPARTMENT_DROPDOWN, "options"), Input(Ids.URL, "pathname"))
def on_page_load(pathname): ...

@app.callback(Output(Ids.CHART, "figure"), Input(Ids.DEPARTMENT_DROPDOWN, "value"))
def callback_2(department): ...
```

**Good — verb-first names that describe the state transition:**
```python
@app.callback(Output(Ids.DEPARTMENT_DROPDOWN, "options"), Input(Ids.URL, "pathname"))
def update_department_options(pathname): ...

@app.callback(Output(Ids.CHART, "figure"), Input(Ids.DEPARTMENT_DROPDOWN, "value"))
def update_department_chart(department): ...
```

**Flag when:** a callback is named generically (`callback`, `cb1`, `on_change`)
with no indication of what state it updates.

### One callback per `Output` — avoid duplicate-output races

- Prefer a single callback per `Output` wherever the triggers can reasonably
  be combined. Dash rejects a second callback writing to the same `Output`
  unless it is given `allow_duplicate=True` — and that flag doesn't remove
  the underlying risk, it only silences the error.
- If two different user actions can both end up writing to the same
  `Output`, whichever callback's Dash resolves last "wins", and if both can
  fire from the same interaction, the result is a race: which value ends up
  on screen depends on execution order, not on user intent.
- When multiple triggers genuinely need to produce the same `Output`,
  combine them into one callback with multiple `Input`s and branch on
  `ctx.triggered_id`, rather than writing two callbacks with
  `allow_duplicate=True`.

**Bad — two callbacks racing to write the same `Output`:**
```python
@app.callback(Output(Ids.STATUS, "children"), Input(Ids.SAVE_BUTTON, "n_clicks"))
def show_saved(n_clicks):
    return "Saved"


@app.callback(
    Output(Ids.STATUS, "children", allow_duplicate=True),
    Input(Ids.REFRESH_BUTTON, "n_clicks"),
    prevent_initial_call=True,
)
def show_refreshed(n_clicks):
    return "Refreshed"
```

**Good — one callback, one `Output`, branching on what triggered it:**
```python
@app.callback(
    Output(Ids.STATUS, "children"),
    Input(Ids.SAVE_BUTTON, "n_clicks"),
    Input(Ids.REFRESH_BUTTON, "n_clicks"),
)
def update_status(save_clicks, refresh_clicks):
    triggered_id = ctx.triggered_id
    if triggered_id == Ids.SAVE_BUTTON:
        return "Saved"
    if triggered_id == Ids.REFRESH_BUTTON:
        return "Refreshed"
    return no_update
```

**Flag when:** two or more callbacks target the same `Output` (with or
without `allow_duplicate=True`) and there is no stated reason a single
combined callback isn't possible.

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
  single provider/service object instead of calling the data source directly
  each time — see "One function per resource" below.
- A data provider should have a clear refresh strategy (e.g. scheduled
  refresh, retry with backoff, and a last-known-good fallback on failure) so
  a transient upstream failure does not take down every page that reads it.
  If a provider has never successfully loaded at all (e.g. first deploy, or
  the upstream source is fully unavailable with no last-known-good snapshot
  yet), callbacks reading it must handle that explicitly — an empty state or
  a clear on-page message — rather than letting an unhandled exception crash
  the callback and take the page down (see Section 8).
- Long-running work (multi-second API calls, LLM calls, large exports) should
  use Dash's background-callback mechanism when the app already has one
  configured, rather than blocking the request/response cycle synchronously.

### One function per resource, not a repeated fetch function per dataset

- If several callbacks read the same underlying resource (a table, an API),
  they should all go through the same function/provider, parameterised by
  what varies (which dataset, which filter) — not a near-identical
  `get_x_data()`, `get_y_data()`, `get_z_data()` copy-pasted per dataset.
- A single provider that knows how to load *any* of the app's datasets by
  name (a small registry keyed by dataset name) is easier to reason about
  and test than one bespoke loader function per dataset, and gives you one
  place to add retry/fallback/refresh behaviour that every dataset gets for
  free.

**Bad — a near-identical loader duplicated per dataset:**
```python
def get_cases_data(): ...   # fetch, clean, cache — copy-pasted three times
def get_spend_data(): ...   # with the dataset name as the only real difference
def get_assurance_data(): ...
```

**Good — one provider, parameterised by dataset (construction does no I/O —
see "Do not eagerly load data on import" below; datasets are only fetched
when a callback actually asks for one):**
```python
class DatasetRegistry:
    """Loads and holds the app's datasets, keyed by name."""

    def get_dataframe(self, dataset: str) -> pd.DataFrame: ...


DATASETS = DatasetRegistry()  # safe to import — no dataset is fetched yet


# callbacks/overview_callbacks.py
@app.callback(Output(Ids.CHART, "figure"), Input(Ids.DEPARTMENT_DROPDOWN, "value"))
def update_chart(department: str | None):
    cases = DATASETS.get_dataframe("cases")
    return build_chart(filter_by_department(cases, department))
```

### Caching is not the default — add it only with evidence it earns its cost

- Do not reach for a cache as a first response to "this might be slow".
  Add caching only once you can point to a specific, repeated cost it
  removes (e.g. the same query firing on every keystroke of a debounced
  search) — and remove it again if it turns out not to be hit, or not to
  save anything meaningful. A cache that adds indirection but delivers no
  measurable benefit is worse than the calls it was meant to avoid: it is
  extra code, an extra failure mode, and an extra thing to explain.
- If the app does use caching, standardise on **one** mechanism app-wide
  (e.g. `flask_caching` everywhere, not `flask_caching` in one callback and
  a hand-rolled module-level dict in another) so invalidation logic lives in
  one place and isn't reinvented per callback.
- Whichever mechanism is used, the cache key, lifetime/TTL, invalidation
  trigger, and per-user isolation (if the data is user-specific) must be
  understood and stated — an unscoped or unbounded cache is a correctness
  and memory risk, not just a performance one.

**Bad — hits the same API/DB on every filter change with no caching:**
```python
@app.callback(Output(Ids.CHART, "figure"), Input(Ids.DEPARTMENT_DROPDOWN, "value"))
def update_chart(department):
    data = fetch_from_athena(department)  # new query every keystroke/selection
    return build_chart(data)
```

**Bad — a cache was added but nothing shows it is actually reducing calls:**
```python
@cache.memoize()
def get_department_options(now: float):  # keyed on current time -> never a hit
    return fetch_department_options()
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

### Do not eagerly load data on import

- A data provider's construction (`__init__`, or code that runs at module
  import time) must not perform I/O — no network call, database query, or
  file read should happen just because the module was imported. The actual
  load belongs behind a method call, triggered lazily on first use (or by an
  explicit `.load()`/scheduled refresh), never as a side effect of `import`.
- This is what makes the provider testable: a test that imports the module
  (or a callback that uses it) should not need real network/S3/DB access
  just to run, and should be able to patch the load method or substitute a
  fake provider instead.

**Bad — the read happens the moment this module is imported:**
```python
# services/data_provider.py
DATA = pd.read_csv("s3://bucket/data.csv")  # runs at import time; every test
                                             # that imports this module needs
                                             # real S3 access to even start
```

**Good — construction does no I/O; the load is deferred and patchable:**
```python
# services/data_provider.py
class DataProvider:
    def __init__(self):
        self._data: pd.DataFrame | None = None  # nothing loaded yet

    def get_dataframe(self) -> pd.DataFrame:
        if self._data is None:
            self._data = self._load()
        return self._data

    def _load(self) -> pd.DataFrame:
        return pd.read_csv("s3://bucket/data.csv")


DATA_PROVIDER = DataProvider()  # safe to import anywhere — no I/O yet
```
```python
# tests/services/test_data_provider.py — patch the load, not the network
def test_get_dataframe_returns_loaded_data(monkeypatch):
    provider = DataProvider()
    monkeypatch.setattr(provider, "_load", lambda: pd.DataFrame({{"a": [1]}}))
    assert list(provider.get_dataframe()["a"]) == [1]
```

**Flag when:** a module-level statement performs network/file/database I/O
directly (not behind a function/method), or a provider's `__init__` calls
its own load method eagerly instead of deferring it to first use.

### Avoid large or duplicated payloads in `dcc.Store`

- `dcc.Store` serialises to JSON and round-trips through the browser on every
  read/write — do not store an entire dataset or large table there when a
  small filter/id would let the callback re-derive the data server-side.
- Flag a `dcc.Store` write containing a full dataframe/record list where the
  same data is already available from a server-side provider. Datasets are
  server-side, immutable-once-loaded state (see the registry pattern above)
  — they do not belong in browser-visible state at all, not even a small
  slice of them "for convenience".

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
- **Config** (`config.py`) centralises environment variables and other
  configurable values — see Section 7.
- **Utils** (`utils/`) hold pure helper functions (date handling, filter
  normalisation, formatting) used by callbacks.
- **Services/providers** (`services/`) own data access, caching, and
  refresh — see Section 4.
- A callback file that also defines its own data-fetching logic, or a layout
  file that also builds a Plotly figure inline, is a sign a module is doing
  more than one job.

**Good — a standardised layout for the whole app:**
```
app_src/
  config.py         # env vars + config values — the only place that reads os.environ
  state.py          # AppState dataclass — the shape of the one dcc.Store
  dash_app.py       # entry point, routing, auth wiring
  dashboards/       # layout only, one file per page
    overview.py
  callbacks/        # wiring only, one file per page
    overview_callbacks.py
  charts/           # pure chart-builder functions
  constants/
    ids.py          # centralised, namespaced component IDs
  services/         # data providers/registry — lazy-loaded, patchable
  utils/            # pure helper functions
  tests/            # mirrors the structure above; run separately from
                    # any CDK/infra tests — see Section 6
```

**Flag when:** a `callbacks/*.py` file makes a direct database/HTTP call
instead of going through a provider/service module, or a `dashboards/*.py`
layout file contains data transformation logic that belongs in `utils/` or a
chart builder.

### Extract repeated layout into named helper functions

- If the same visual pattern (a KPI card, a filter row, a table wrapper)
  appears more than once, build it with a function that takes the varying
  parts as parameters, rather than copy-pasting the component tree each time.
- Deeply nested inline layouts are hard to read at a glance: each extra level
  of nesting makes it harder to see the overall shape of the page. Break
  nesting into named local variables or small functions — one per logical
  section — so the top-level layout reads like a table of contents rather
  than a wall of nested calls.

**Bad — the same card structure copy-pasted three times, deeply nested:**
```python
layout = html.Div([
    html.Div([html.H4("Cases"), html.P(str(case_count)), html.Small("vs last month")], className="kpi-card"),
    html.Div([html.H4("Assured"), html.P(str(assured_count)), html.Small("vs last month")], className="kpi-card"),
    html.Div([html.H4("Spend"), html.P(str(spend)), html.Small("vs last month")], className="kpi-card"),
])
```

**Good — one function, reused, and the top-level layout is easy to scan:**
```python
def build_kpi_card(title: str, value: str, comparison: str) -> html.Div:
    return html.Div(
        [html.H4(title), html.P(value), html.Small(comparison)],
        className="kpi-card",
    )


layout = html.Div([
    build_kpi_card("Cases", str(case_count), "vs last month"),
    build_kpi_card("Assured", str(assured_count), "vs last month"),
    build_kpi_card("Spend", str(spend), "vs last month"),
])
```

**Flag when:** a near-identical component tree (three or more properties in
common) is repeated inline more than once instead of being extracted into a
function.

### Flag long files as candidates for splitting

- A single `callbacks/*.py` or `dashboards/*.py` file that has grown past
  roughly 300 lines is a candidate for splitting — typically by page or by
  logical section within a page, mirroring how `cdk_review.md` treats an
  oversized stack file.
- A long file makes it harder to find the one callback you need to change,
  and increases the chance of two unrelated changes colliding in the same
  file for no functional reason.

**Bad — every page's callbacks piling up in one ever-growing file:**
```
callbacks/callbacks.py   # 900 lines: overview + case analysis + assessments
```

**Good — split by page, one file per logical section:**
```
callbacks/
  overview_callbacks.py
  case_analysis_callbacks.py
  service_assessment_callbacks.py
```

**Flag when:** a `callbacks/*.py` or `dashboards/*.py` file exceeds roughly
300 lines and visibly mixes callbacks/layout for more than one page or
unrelated section.

## 6. Testing

### Test the pure functions directly, not by rendering Dash

- Filter/state transformation functions, chart builders, formatters, and the
  data model/loading layer should have direct unit tests that call the
  function and assert on its return value — no Dash app instance or browser
  required for any of it.
- Mirror the source layout in `tests/` (e.g. `tests/callbacks/`,
  `tests/charts/`, `tests/utils/`, `tests/services/`) so the test for a
  given module is easy to find.
- For a callback itself, test its contract by importing and calling the
  underlying function directly (Dash callback functions are plain Python
  functions once decorated; call them as such) rather than trying to spin up
  a full app and simulate browser interaction, unless verifying the
  rendered interaction is genuinely the point of the test.

**Flag when:** new pure logic (a filter normaliser, a data transform, a chart
builder, a loading/filtering function on the data model) ships with no
direct unit test, especially when it replaces or changes existing tested
behaviour without an updated test.

### Keep app tests separate from CDK/infrastructure tests

- If the repo also has CDK/infrastructure tests (typically a root `tests/`
  directory), the Dash app's own tests should live in their own directory
  (e.g. `app_src/tests/`), ideally with their own pytest configuration, not
  interleaved with infra tests that need AWS mocking/`aws_cdk.assertions`.
  They test different things at different speeds, and mixing them makes the
  whole suite slower and noisier for whichever half you are not currently
  working on.

**Flag when:** an app test file imports `aws_cdk`/`aws_cdk.assertions`, or an
infrastructure test imports Dash app internals — a sign the boundary between
the two test suites has blurred.

## 7. Security and Configuration

### Keep secrets and auth off the client, and out of the diff

- Secrets, API keys, and credentials must be loaded from environment
  variables or a secrets manager — never hardcoded, and never placed in a
  `dcc.Store`, hidden input, or any other client-visible prop (see Section 2).
- Authentication/authorisation middleware should wrap the whole app (e.g. a
  `before_request` hook or auth middleware applied once at app construction),
  not be re-implemented per route or per callback.
- Role-based access checks (RBAC) should be centralised the same way — a
  single `require_role()`/decorator or middleware layer that every protected
  route or callback goes through, not an inline `if user.role == "admin"`
  check repeated ad hoc wherever it happens to be needed. A scattered check
  is easy to forget when a new protected page is added.
- A health-check route (`/health`) should not require authentication or touch
  the data layer, so infra health checks are not blocked by auth or data
  outages.

### Centralise environment variables and configuration in one module

- All `os.getenv()`/`os.environ[...]` reads, and any other hardcoded
  configuration values (default ports, timeouts, feature flags), should go
  through a single `config.py` (or equivalent) rather than being read inline
  and scattered across callbacks, services, and layouts.
- A single config module makes every configurable value discoverable in one
  place, gives you one spot to add validation or a documented default, and
  means a missing required env var fails fast and obviously at startup
  rather than surfacing as an unexplained `None` three layers into a
  callback.

**Bad — the same env var read differently in two different files:**
```python
# callbacks/overview_callbacks.py
api_key = os.getenv("EXAMPLE_API_KEY")

# services/example_client.py
api_key = os.environ["EXAMPLE_API_KEY"]  # a typo here silently diverges
```

**Good — one module owns every env var and hardcoded default:**
```python
# config.py
import os

EXAMPLE_API_KEY = os.environ["EXAMPLE_API_KEY"]
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300"))
```
```python
# callbacks/overview_callbacks.py
from config import EXAMPLE_API_KEY
```

**Flag when:** `os.getenv()`/`os.environ[...]` is called outside `config.py`
(or the repo's equivalent single config module).

## 8. Logging, Error Handling and Resilience

### Use structured logging, and make failures diagnosable

- Callback and service code should use Python's `logging` module, not
  `print()` — the same standard already applied to Lambda handlers by the
  CDK reviewer.
- Log enough at the point of failure to diagnose it later: what was being
  attempted, with what key inputs (never secrets), and what the actual
  exception was — not just "an error occurred". A meaningful error message
  names what failed and, where possible, why.
- Do not swallow exceptions with a bare `except:`/`except Exception: pass`
  inside a callback. Dash already turns an uncaught exception into a
  generic client-side error with no detail; logging the real exception
  server-side is the only way anyone can diagnose it afterwards.

**Bad — the failure disappears with no trace of what went wrong:**
```python
@app.callback(Output(Ids.CHART, "figure"), Input(Ids.DEPARTMENT_DROPDOWN, "value"))
def update_chart(department):
    try:
        data = DATA_PROVIDER.get_dataframe()
    except Exception:
        return {{}}
```

**Good — logged with context, and the user sees a clear message:**
```python
logger = logging.getLogger(__name__)


@app.callback(Output(Ids.CHART, "figure"), Input(Ids.DEPARTMENT_DROPDOWN, "value"))
def update_chart(department: str | None):
    try:
        data = DATA_PROVIDER.get_dataframe()
    except DataUnavailableError:
        logger.exception("No data available for department=%s", department)
        return empty_chart_with_message("Data is temporarily unavailable")
    return build_chart(filter_by_department(data, department))
```

### The app must not crash if data fails to load

- This follows directly from Section 4's provider fallback strategy: if a
  provider has no data at all yet (first deploy, upstream fully down, no
  last-known-good snapshot), the callbacks reading it must render an
  explicit empty/error state, not let an unhandled exception take the whole
  page down.

**Flag when:** a callback calls something that can fail (network, database,
file access) with no exception handling and no logging on the failure path.

## 9. Anti-Patterns to Flag

- **Raw string component IDs** instead of a centralised ID enum/module
- **Secrets or credentials in a `dcc.Store`, hidden input, or other
  client-visible prop**
- **The same state value tracked in more than one store/URL param** with no
  stated precedence rule
- **`Input` used for a value that should be `State`** (causes unwanted
  re-triggers), or vice versa (a control that should refresh but doesn't)
- **Business logic written inline inside a `@callback`-decorated function**
  instead of a testable plain function
- **Callbacks named generically** (`callback`, `cb1`, `on_change`) with no
  indication of the state transition they perform
- **Two or more callbacks writing to the same `Output`** (with or without
  `allow_duplicate=True`) with no stated reason a single callback isn't possible
- **`no_update`/`PreventUpdate` used with no comment explaining why**
- **Feedback loops between two callbacks** with no `ctx.triggered_id` guard
- **Direct database/API calls inside a frequently-firing callback** with no
  shared provider
- **A near-identical fetch/loader function duplicated per dataset** instead
  of one function/provider parameterised by dataset
- **A cache added with no stated evidence of the repeated cost it removes**,
  or a cache key/TTL that makes it structurally unable to ever hit
  (see Section 4)
- **Two different caching mechanisms mixed in the same app**
- **Data loaded eagerly at import time** (a module-level `pd.read_csv(...)`,
  a provider that fetches inside `__init__`) instead of deferred to first use
- **A full dataset or large record list written into `dcc.Store`** when a
  small filter/id would suffice
- **Data-fetching or transformation logic inside a layout file**
  (`dashboards/`, `layouts.py`) instead of `utils/`/`services/`
- **A near-identical layout component tree repeated inline** instead of a
  helper function
- **A `callbacks/*.py`/`dashboards/*.py` file that has grown past ~300 lines**
  with no split
- **New filter/transform/chart-builder/data-model logic with no direct unit test**
- **App tests mixed with CDK/infrastructure tests** (importing `aws_cdk` in
  an app test, or Dash internals in an infra test)
- **`os.getenv()`/`os.environ[...]` called outside a single config module**
- **RBAC/role checks implemented ad hoc per callback** instead of a shared,
  centralised check
- **`print()` used instead of `logging`**, or an exception swallowed with a
  bare `except`/`except Exception: pass` and no logging
- **A callback that can fail (network/DB/file) with no handling for the
  failure path**, risking an unhandled exception crashing the page
- **Pattern-matching callbacks used for a fixed, known set of components**
  where plain IDs would be simpler
- **Clientside JS duplicating server-side business logic** instead of one
  being the source of truth
- **Unresolved merge conflict markers** (`<<<<<<<`, `=======`, `>>>>>>>`)

## 10. Do NOT Flag

- AI agent/LLM-orchestration code embedded in the same app (knowledge-base
  search agents, MCP tool servers, RAG/graph retrieval) — out of scope for
  this reviewer; that is an agent-engineering concern
- CDK/infrastructure that deploys the app — the CDK reviewer owns that
- Docstring wording/completeness on callback or helper functions — the
  docstring reviewer owns that; this reviewer may still flag a *missing*
  test or a logic issue in the same function
- Front-end accessibility (contrast ratios, screen-reader/keyboard-nav
  behaviour) — this cannot be verified from a code diff; it needs a
  rendering-based tool (axe-core/pa11y/Lighthouse CI) as a dedicated CI job,
  tracked separately
- Colour palette, font sizes, or data-table visual/design-system audits —
  a visual-QA concern, not diff-reviewable without an established shared
  design-tokens module to check against; tracked separately
- Cross-device/cross-browser compatibility — needs real or emulated
  browsers/devices (e.g. Playwright/BrowserStack), which this reviewer has
  no way to exercise from a diff; tracked separately
- Whether the Dash version, `gds-idea-app-kit` pin, or other dependencies are
  "up to date" — verifying the current latest release needs a registry
  lookup this reviewer cannot reliably perform; this is Dependabot's job, not
  this reviewer's
- Backend data-cleaning/deduplication/transformation correctness that is not
  specific to Dash's reactive model (the same logic could equally sit in a
  non-Dash Lambda) — the general code reviewer's remit
- Choices that are valid but different from a personal preference (e.g.
  `flask-caching` vs `diskcache` as the app's single chosen mechanism — pick
  one, either is fine)
- Formatting issues already handled by a linter
- Pattern-matching callbacks used for a genuinely dynamic, variable-length
  set of components (e.g. a variable number of filter rows) — that is the
  correct tool for that job
- If there are no Dash application files added or modified in this PR,
  report that the Dash app review found nothing to flag — that is a valid,
  expected outcome
