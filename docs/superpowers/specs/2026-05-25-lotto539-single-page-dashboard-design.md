# Lotto 539 Single-Page Dashboard Design

## Goal

Add a local single-page dashboard that lets the user operate the existing Lotto 539 project from one browser page. The page should surface database status, latest draw information, number frequency, backtest controls, backtest results, and a manual crawl action without replacing the existing CLI tools.

## Current Context

The project currently has:

- `fetch_lotto539_history.py` for crawling Taiwan Lottery history into `lotto-539.db`.
- `lotto_analysis.py` for normalized draw loading, date parsing, number parsing, feature summaries, and frequency counts.
- `backtest.py` for baseline strategies and estimated ROI backtesting.
- Pytest coverage for crawler storage, analysis helpers, backtest behavior, and GitHub Actions workflow checks.

There is no frontend framework, web server, or build step. The smallest professional integration is a standard-library local server that serves one HTML page and JSON APIs.

## Scope

This phase will implement:

- A local web server entry point, `app.py`.
- A single browser page served by the local server.
- JSON APIs for summary, backtest, and manual crawl.
- Frontend controls for selecting strategy and running backtests.
- Focused tests for API response data and request validation.

This phase will not implement:

- User login or deployment hosting.
- A database migration framework.
- Realtime updates or background job queues.
- A JavaScript framework or bundler.
- Official prize payout calculation.

## Architecture

### `app.py`

Use Python standard-library HTTP server classes to avoid adding framework dependencies. The server should run with:

```bash
python app.py
```

Default behavior:

- Bind to `127.0.0.1`.
- Use port `8000`, with a CLI option to override.
- Read `lotto-539.db` by default, with a CLI option to override.

Routes:

- `GET /`: returns the single HTML page.
- `GET /api/summary`: returns database and draw summary JSON.
- `POST /api/backtest`: runs a backtest and returns JSON.
- `POST /api/crawl`: fetches current lottery history and stores new rows.

Keep route handlers thin. Put reusable logic in functions that tests can call without starting a real server:

```python
build_summary(db_path: Path) -> dict[str, object]
build_backtest_response(db_path: Path, payload: dict[str, object]) -> dict[str, object]
run_crawl(db_path: Path) -> dict[str, object]
```

### Single Page UI

The page should be a dense, operational dashboard rather than a marketing page.

Sections:

- Header band with project name, database file, and refresh/crawl buttons.
- Status strip with total draws, latest issue, latest draw date, and latest numbers.
- Backtest panel with strategy selector, test start date, training cutoff date, recent window, seed, and ticket cost.
- Results panel with test draw count, average hits, estimated payout, estimated ROI, and hit distribution.
- Frequency panel showing numbers ranked by historical frequency.
- Latest draws table showing recent records.

The page should avoid instructions-heavy copy. Labels and controls should be self-explanatory.

### API Shapes

`GET /api/summary` returns:

```json
{
  "database": "lotto-539.db",
  "total_draws": 73,
  "latest_draw": {
    "issue": "115000126",
    "draw_date": "2026-05-23",
    "numbers": [6, 15, 16, 24, 38],
    "jackpot_winners": 1
  },
  "recent_draws": [],
  "frequency": [{"number": 1, "count": 10}]
}
```

`POST /api/backtest` accepts:

```json
{
  "strategy": "frequency",
  "test_from": "2026-05-01",
  "train_before": null,
  "recent_window": 20,
  "seed": 539,
  "ticket_cost": 50
}
```

It returns:

```json
{
  "strategy": "frequency",
  "total_draws": 20,
  "average_hits": 0.6,
  "hit_distribution": {"0": 8, "1": 12, "2": 0, "3": 0, "4": 0, "5": 0},
  "total_cost": 1000,
  "estimated_payout": 0,
  "estimated_roi": -1.0,
  "predictions": []
}
```

`POST /api/crawl` returns:

```json
{
  "fetched": 73,
  "inserted": 0,
  "latest_issue": "115000126",
  "earliest_issue": "115000054"
}
```

## Data Flow

1. The browser loads `/`.
2. The page calls `/api/summary` and renders database status.
3. The user changes backtest inputs and submits the form.
4. The page posts JSON to `/api/backtest`.
5. `app.py` calls `load_draws()` and `run_backtest()`.
6. The page renders metrics and distribution.
7. If the user triggers crawl, `app.py` calls the existing crawler functions, writes new rows, then the page refreshes summary data.

## Error Handling

- Missing database or empty draw data should return a JSON error with HTTP 500 for API routes and a visible page error state.
- Invalid dates should return HTTP 400 with a useful error message.
- Invalid strategy values should return HTTP 400.
- Crawl failures should return HTTP 500 with a short message.
- The frontend should show API error messages in a compact status area.

## Testing

Add pytest coverage for:

- `build_summary()` with a temporary SQLite database.
- `build_backtest_response()` with valid payloads.
- Backtest validation rejecting invalid strategies and malformed dates.
- `run_crawl()` through a dependency-injected fetch function or small helper so tests do not hit the network.
- Existing CLI tests continue to pass.

Manual verification:

- Run `python app.py`.
- Open `http://127.0.0.1:8000`.
- Confirm summary renders.
- Run a frequency backtest from the page.
- Confirm crawl button returns either success or a clear error if Playwright/browser setup is missing.

## Future Extension

This page can later add a model selector for scikit-learn or LSTM strategies once those models exist behind the same backtest API. It can also become a deployed dashboard later, but this phase should remain a local-first tool.
