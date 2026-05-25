import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path

from backtest import BacktestConfig, run_backtest
from fetch_lotto539_history import build_default_url, fetch_html, parse_history, save_history
from lotto_analysis import count_number_frequency, load_draws


class BadRequestError(ValueError):
    pass


def serialize_draw(draw):
    return {
        "issue": draw.issue,
        "draw_date": draw.draw_date.isoformat(),
        "numbers": list(draw.numbers),
        "jackpot_winners": draw.jackpot_winners,
    }


def build_summary(db_path: Path) -> dict[str, object]:
    draws = load_draws(db_path)
    if not draws:
        raise RuntimeError("No Lotto 539 draws found")

    frequency = [
        {"number": number, "count": count}
        for number, count in count_number_frequency(draws).items()
    ]
    recent_draws = [serialize_draw(draw) for draw in reversed(draws[-10:])]

    return {
        "database": str(db_path),
        "total_draws": len(draws),
        "latest_draw": serialize_draw(draws[-1]),
        "recent_draws": recent_draws,
        "frequency": frequency,
    }


def build_backtest_response(db_path: Path, payload: dict[str, object]) -> dict[str, object]:
    strategy = payload.get("strategy", "frequency")
    if strategy not in {"random", "frequency", "filtered-frequency", "recent-frequency"}:
        raise BadRequestError(f"Invalid strategy: {strategy}")

    recent_window = parse_int_with_default(payload.get("recent_window"), 20)
    if recent_window < 1:
        raise BadRequestError("recent_window must be greater than 0")

    ticket_cost = parse_int_with_default(payload.get("ticket_cost"), 50)
    if ticket_cost < 1:
        raise BadRequestError("ticket_cost must be greater than 0")

    config = BacktestConfig(
        strategy=strategy,
        train_before=parse_optional_iso_date(payload.get("train_before")),
        test_from=parse_optional_iso_date(payload.get("test_from")),
        recent_window=recent_window,
        seed=parse_optional_int(payload.get("seed")),
        ticket_cost=ticket_cost,
    )
    result = run_backtest(load_draws(db_path), config)

    return {
        "strategy": strategy,
        "total_draws": result.total_draws,
        "average_hits": result.average_hits,
        "hit_distribution": {
            str(hits): count for hits, count in result.hit_distribution.items()
        },
        "total_cost": result.total_cost,
        "estimated_payout": result.estimated_payout,
        "estimated_roi": result.estimated_roi,
        "predictions": [
            {
                "issue": prediction.draw.issue,
                "draw_date": prediction.draw.draw_date.isoformat(),
                "actual_numbers": list(prediction.draw.numbers),
                "predicted_numbers": list(prediction.predicted_numbers),
                "hit_count": prediction.hit_count,
            }
            for prediction in result.predictions
        ],
    }


def parse_optional_iso_date(value):
    if value in {None, ""}:
        return None
    try:
        from datetime import date

        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise BadRequestError(f"Invalid date: {value}") from exc


def parse_optional_int(value):
    if value in {None, ""}:
        return None
    return int(value)


def parse_int_with_default(value, default):
    if value in {None, ""}:
        return default
    return int(value)


def run_crawl(db_path: Path, fetcher=None) -> dict[str, object]:
    if fetcher is None:
        fetcher = fetch_latest_records

    records = fetcher()
    inserted = save_history(db_path, records)

    return {
        "fetched": len(records),
        "inserted": inserted,
        "latest_issue": records[0]["期別"] if records else None,
        "earliest_issue": records[-1]["期別"] if records else None,
    }


def fetch_latest_records():
    return parse_history(fetch_html(build_default_url()))


DASHBOARD_HTML = r"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Lotto 539 Console</title>
  <style>
    :root {
      --ink: #202124;
      --muted: #667085;
      --line: #d9dee7;
      --paper: #f7f4ee;
      --panel: #fffdf8;
      --accent: #0f766e;
      --accent-2: #b42318;
      --gold: #c58b20;
      --shadow: 0 18px 45px rgba(32, 33, 36, .10);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      background:
        linear-gradient(90deg, rgba(15, 118, 110, .08) 1px, transparent 1px),
        linear-gradient(rgba(15, 118, 110, .06) 1px, transparent 1px),
        var(--paper);
      background-size: 28px 28px;
      font-family: "Segoe UI", "Noto Sans TC", sans-serif;
      letter-spacing: 0;
    }
    button, input, select { font: inherit; }
    .shell { max-width: 1380px; margin: 0 auto; padding: 24px; }
    header {
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 20px;
      padding-bottom: 18px;
      border-bottom: 2px solid var(--ink);
    }
    h1 { margin: 0; font-size: 28px; line-height: 1.1; }
    .subtitle { color: var(--muted); margin-top: 6px; font-size: 14px; }
    .actions { display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }
    .btn {
      border: 1px solid var(--ink);
      background: var(--ink);
      color: #fff;
      min-height: 38px;
      padding: 8px 13px;
      border-radius: 6px;
      cursor: pointer;
      box-shadow: 3px 3px 0 rgba(32, 33, 36, .18);
    }
    .btn.secondary { background: var(--panel); color: var(--ink); }
    .btn:disabled { opacity: .55; cursor: wait; }
    .status {
      margin: 14px 0 0;
      min-height: 22px;
      color: var(--muted);
      font-size: 14px;
    }
    .status.error { color: var(--accent-2); }
    .grid {
      display: grid;
      grid-template-columns: 1.05fr .95fr;
      gap: 18px;
      margin-top: 18px;
    }
    .metrics {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-top: 18px;
    }
    .metric, .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }
    .metric { padding: 14px; min-height: 96px; }
    .metric span { display: block; color: var(--muted); font-size: 12px; text-transform: uppercase; }
    .metric strong { display: block; margin-top: 10px; font-size: 24px; line-height: 1.1; }
    .panel { padding: 16px; }
    .panel h2 { margin: 0 0 14px; font-size: 18px; }
    form {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }
    label { display: grid; gap: 6px; color: var(--muted); font-size: 13px; }
    input, select {
      width: 100%;
      min-height: 38px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      padding: 7px 9px;
    }
    .form-actions { align-self: end; }
    .numbers { display: flex; gap: 6px; flex-wrap: wrap; }
    .ball {
      display: inline-grid;
      place-items: center;
      width: 34px;
      height: 34px;
      border-radius: 50%;
      background: #f8e7bd;
      border: 1px solid #9b6b12;
      color: #4b3200;
      font-weight: 700;
    }
    .result-line {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 14px;
    }
    .result-line div { border-top: 2px solid var(--ink); padding-top: 8px; }
    .result-line span { display: block; color: var(--muted); font-size: 12px; }
    .result-line strong { font-size: 20px; }
    .distribution { display: grid; gap: 8px; }
    .bar { display: grid; grid-template-columns: 46px 1fr 40px; gap: 8px; align-items: center; }
    .track { height: 12px; background: #e9edf2; border-radius: 999px; overflow: hidden; }
    .fill { height: 100%; background: var(--accent); width: 0; }
    .freq-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 8px; }
    .freq-item { border: 1px solid var(--line); border-radius: 6px; padding: 8px; background: #fff; }
    .freq-item strong { color: var(--accent); }
    table { width: 100%; border-collapse: collapse; font-size: 14px; }
    th, td { padding: 10px 8px; border-bottom: 1px solid var(--line); text-align: left; }
    th { color: var(--muted); font-weight: 600; }
    .wide { grid-column: 1 / -1; }
    @media (max-width: 900px) {
      .grid, .metrics, form, .result-line { grid-template-columns: 1fr; }
      header { align-items: start; flex-direction: column; }
      .actions { justify-content: flex-start; }
      .freq-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header>
      <div>
        <h1>Lotto 539 Console</h1>
        <div class="subtitle" id="database">Loading database...</div>
      </div>
      <div class="actions">
        <button class="btn secondary" id="refreshBtn" type="button">Refresh</button>
        <button class="btn" id="crawlBtn" type="button">Crawl Latest</button>
      </div>
    </header>
    <div class="status" id="status"></div>

    <section class="metrics">
      <div class="metric"><span>Total Draws</span><strong id="totalDraws">-</strong></div>
      <div class="metric"><span>Latest Issue</span><strong id="latestIssue">-</strong></div>
      <div class="metric"><span>Latest Date</span><strong id="latestDate">-</strong></div>
      <div class="metric"><span>Latest Numbers</span><div class="numbers" id="latestNumbers"></div></div>
    </section>

    <section class="grid">
      <div class="panel">
        <h2>Backtest</h2>
        <form id="backtestForm">
          <label>Strategy
            <select name="strategy">
              <option value="frequency">Frequency</option>
              <option value="filtered-frequency">Filtered Frequency (AC / Tail / Consecutive)</option>
              <option value="recent-frequency">Recent Frequency</option>
              <option value="random">Random</option>
            </select>
          </label>
          <label>Test From
            <input name="test_from" type="date" value="2026-05-01">
          </label>
          <label>Train Before
            <input name="train_before" type="date">
          </label>
          <label>Recent Window
            <input name="recent_window" type="number" min="1" value="20">
          </label>
          <label>Seed
            <input name="seed" type="number" value="539">
          </label>
          <label>Ticket Cost
            <input name="ticket_cost" type="number" min="1" value="50">
          </label>
          <div class="form-actions">
            <button class="btn" type="submit">Run Backtest</button>
          </div>
        </form>
      </div>

      <div class="panel">
        <h2>Results</h2>
        <div class="result-line">
          <div><span>Strategy</span><strong id="resultStrategy">-</strong></div>
          <div><span>Draws</span><strong id="resultDraws">-</strong></div>
          <div><span>Avg Hits</span><strong id="resultAvg">-</strong></div>
          <div><span>Payout</span><strong id="resultPayout">-</strong></div>
          <div><span>ROI</span><strong id="resultRoi">-</strong></div>
        </div>
        <div class="distribution" id="distribution"></div>
      </div>

      <div class="panel">
        <h2>Frequency</h2>
        <div class="freq-grid" id="frequency"></div>
      </div>

      <div class="panel">
        <h2>Recent Draws</h2>
        <table>
          <thead><tr><th>Issue</th><th>Date</th><th>Numbers</th><th>Winners</th></tr></thead>
          <tbody id="recentDraws"></tbody>
        </table>
      </div>
    </section>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);

    function setStatus(message, isError = false) {
      $("status").textContent = message;
      $("status").className = isError ? "status error" : "status";
    }

    async function requestJson(url, options = {}) {
      const response = await fetch(url, options);
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Request failed");
      return data;
    }

    function balls(numbers) {
      return numbers.map((number) => `<span class="ball">${String(number).padStart(2, "0")}</span>`).join("");
    }

    async function loadSummary() {
      setStatus("Refreshing...");
      const summary = await requestJson("/api/summary");
      $("database").textContent = summary.database;
      $("totalDraws").textContent = summary.total_draws;
      $("latestIssue").textContent = summary.latest_draw.issue;
      $("latestDate").textContent = summary.latest_draw.draw_date;
      $("latestNumbers").innerHTML = balls(summary.latest_draw.numbers);
      $("frequency").innerHTML = summary.frequency.slice(0, 20).map((item) =>
        `<div class="freq-item"><strong>${String(item.number).padStart(2, "0")}</strong><br>${item.count} hits</div>`
      ).join("");
      $("recentDraws").innerHTML = summary.recent_draws.map((draw) =>
        `<tr><td>${draw.issue}</td><td>${draw.draw_date}</td><td><div class="numbers">${balls(draw.numbers)}</div></td><td>${draw.jackpot_winners}</td></tr>`
      ).join("");
      setStatus("Ready");
    }

    function renderBacktest(result) {
      $("resultStrategy").textContent = result.strategy;
      $("resultDraws").textContent = result.total_draws;
      $("resultAvg").textContent = result.average_hits.toFixed(3);
      $("resultPayout").textContent = result.estimated_payout;
      $("resultRoi").textContent = result.estimated_roi.toFixed(3);
      const max = Math.max(...Object.values(result.hit_distribution), 1);
      $("distribution").innerHTML = Object.entries(result.hit_distribution).map(([hits, count]) =>
        `<div class="bar"><span>${hits} hits</span><div class="track"><div class="fill" style="width:${(count / max) * 100}%"></div></div><strong>${count}</strong></div>`
      ).join("");
    }

    $("backtestForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      const payload = Object.fromEntries(form.entries());
      try {
        setStatus("Running backtest...");
        renderBacktest(await requestJson("/api/backtest", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(payload)
        }));
        setStatus("Backtest complete");
      } catch (error) {
        setStatus(error.message, true);
      }
    });

    $("refreshBtn").addEventListener("click", () => loadSummary().catch((error) => setStatus(error.message, true)));
    $("crawlBtn").addEventListener("click", async () => {
      try {
        $("crawlBtn").disabled = true;
        setStatus("Crawling latest draws...");
        const result = await requestJson("/api/crawl", {method: "POST"});
        setStatus(`Fetched ${result.fetched}, inserted ${result.inserted}`);
        await loadSummary();
      } catch (error) {
        setStatus(error.message, true);
      } finally {
        $("crawlBtn").disabled = false;
      }
    });

    loadSummary()
      .then(() => $("backtestForm").dispatchEvent(new Event("submit", {cancelable: true})))
      .catch((error) => setStatus(error.message, true));
  </script>
</body>
</html>"""


def create_handler(db_path: Path):
    class DashboardRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                self.send_html(DASHBOARD_HTML)
            elif self.path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
            elif self.path == "/api/summary":
                self.send_json(build_summary(db_path))
            else:
                self.send_error(404)

        def do_POST(self):
            try:
                if self.path == "/api/backtest":
                    self.send_json(build_backtest_response(db_path, self.read_json()))
                elif self.path == "/api/crawl":
                    self.send_json(run_crawl(db_path))
                else:
                    self.send_error(404)
            except BadRequestError as exc:
                self.send_json({"error": str(exc)}, status=400)
            except Exception as exc:
                self.send_json({"error": str(exc)}, status=500)

        def read_json(self):
            length = int(self.headers.get("Content-Length", "0"))
            if length == 0:
                return {}
            try:
                return json.loads(self.rfile.read(length).decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise BadRequestError("Invalid JSON payload") from exc

        def send_json(self, payload, status=200):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def send_html(self, html):
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            return

    return DashboardRequestHandler


def main():
    parser = argparse.ArgumentParser(description="Run the Lotto 539 local dashboard.")
    parser.add_argument("--db", default="lotto-539.db", help="SQLite database path")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8000, help="Bind port")
    args = parser.parse_args()

    db_path = Path(args.db)
    server = ThreadingHTTPServer((args.host, args.port), create_handler(db_path))
    print(f"Lotto 539 dashboard running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
