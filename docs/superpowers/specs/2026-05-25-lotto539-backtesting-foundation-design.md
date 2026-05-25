# Lotto 539 Backtesting Foundation Design

## Goal

Upgrade the project from a working Lotto 539 crawler into a small, testable analysis foundation. The first phase focuses on reliable data access, deterministic statistics, and a baseline backtesting system. It deliberately avoids machine learning until the project can measure whether a strategy beats simple baselines.

## Current Context

The repository currently contains:

- `fetch_lotto539_history.py`, which fetches Taiwan Lottery Lotto 539 history and stores records in SQLite.
- `lotto-539.db`, with a `history` table containing draw id, draw date, ordered numbers, and jackpot winner count.
- `.github/workflows/auto_crawl.yml`, which runs daily at 22:30 Asia/Taipei and commits database updates.
- Pytest coverage for URL generation, duplicate-safe inserts, and workflow contents.

The database currently has a primary key index on `期別`, but no explicit index on `開獎日`.

## Scope

This phase will implement:

- A reusable analysis module for loading draw records and computing features.
- A date index in SQLite for faster chronological queries.
- A command-line backtesting tool.
- Baseline strategies that can be compared against future machine learning models.
- Focused pytest coverage for the new behavior.

This phase will not implement:

- LSTM, XGBoost, or scikit-learn models.
- Claims that any strategy predicts lottery outcomes reliably.
- A web UI or dashboard.
- Exact official prize calculation, because jackpot payouts vary by draw. ROI will use a documented configurable payout table.

## Architecture

### `fetch_lotto539_history.py`

Keep the existing crawler and parser structure. Extend `save_history()` so schema initialization also creates an index:

```sql
CREATE INDEX IF NOT EXISTS idx_history_draw_date ON history ("開獎日")
```

This keeps the change low-risk and improves future chronological reads.

### `lotto_analysis.py`

Add a pure Python module for deterministic data and feature handling.

Core responsibilities:

- Convert Taiwan ROC date strings such as `115/05/23` to `datetime.date(2026, 5, 23)`.
- Parse `"大小順序"` strings into sorted integer tuples.
- Load draws from SQLite in chronological order.
- Compute simple draw features:
  - Sum of the five numbers.
  - Odd count and even count.
  - Tail digits.
  - Number frequency over an input draw collection.

Suggested public API:

```python
Draw = dataclass(frozen=True)

parse_roc_date(value: str) -> date
parse_numbers(value: str) -> tuple[int, ...]
load_draws(db_path: Path) -> list[Draw]
summarize_draw(draw: Draw) -> dict[str, object]
count_number_frequency(draws: Iterable[Draw]) -> dict[int, int]
```

The module should avoid side effects outside of database reads.

### `backtest.py`

Add a CLI for backtesting simple strategies.

Example:

```bash
python backtest.py --db lotto-539.db --train-before 2025-01-01 --test-from 2025-01-01
```

Supported strategies:

- `random`: Choose five unique numbers from 1 to 39. Accept a seed for reproducible runs.
- `frequency`: Use the training window and pick the five most frequent numbers.
- `recent-frequency`: For each tested draw, use the most recent N prior draws and pick the five most frequent numbers.

Backtest behavior:

- Split loaded draws by Gregorian dates.
- Train or derive predictions only from data earlier than the target draw.
- Compare each predicted set with the actual draw.
- Report hit distribution for 0 through 5 matched numbers.
- Report average hit count.
- Report total cost, estimated payout, and estimated ROI.

Default assumptions:

- One ticket per tested draw.
- Ticket cost defaults to 50.
- Payout table is configurable and defaults to conservative placeholder values.
- The output must label ROI as estimated, not official.

## Data Flow

1. GitHub Actions updates `lotto-539.db` through the crawler.
2. `lotto_analysis.load_draws()` reads normalized `Draw` objects from SQLite.
3. `backtest.py` filters and orders those draws by Gregorian date.
4. A selected strategy generates five-number predictions.
5. The backtest engine compares predictions with actual numbers and aggregates metrics.

## Error Handling

- Invalid ROC dates should raise `ValueError` with the offending value.
- Invalid number strings should raise `ValueError` if they do not contain exactly five unique integers from 1 to 39.
- `backtest.py` should fail clearly if the database has no usable draws or if the test window is empty.
- CLI output should remain readable in plain text.

## Testing

Add or extend pytest coverage for:

- ROC date parsing, including normal dates and invalid strings.
- Number parsing, including duplicate, missing, and out-of-range values.
- Feature summaries for known draws.
- Frequency counting and deterministic tie-breaking.
- `save_history()` creating the draw-date index.
- Backtest metrics for a small in-memory or temporary SQLite dataset.
- Reproducible random strategy behavior with a fixed seed.

Tests should use small temporary databases and pure functions where possible.

## Future Extension

After this foundation is complete, machine learning can be added behind the same strategy interface. A future `ml-frequency`, `random-forest`, or `lstm` strategy should be required to beat the included random and frequency baselines before being considered useful.
