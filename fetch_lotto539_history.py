import argparse
import sqlite3
from datetime import date
from html.parser import HTMLParser
from pathlib import Path


BASE_URL = "https://www.taiwanlottery.com/lotto/result/traditional"


def shift_month(day, month_delta):
    month_index = day.year * 12 + day.month - 1 + month_delta
    year = month_index // 12
    month = month_index % 12 + 1
    return f"{year:04d}-{month:02d}"


def build_default_url(today=None):
    today = today or date.today()
    start_month = shift_month(today, -2)
    end_month = shift_month(today, 0)
    return (
        f"{BASE_URL}?game=daily_cash&period="
        f"&start_month={start_month}&end_month={end_month}"
    )


DEFAULT_URL = build_default_url()


class TableTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self._table = None
        self._row = None
        self._cell = None
        self._in_cell = False

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in {"th", "td"} and self._row is not None:
            self._cell = []
            self._in_cell = True

    def handle_data(self, data):
        if self._in_cell and self._cell is not None:
            text = " ".join(data.split())
            if text:
                self._cell.append(text)

    def handle_endtag(self, tag):
        if tag in {"th", "td"} and self._in_cell:
            self._row.append(" ".join(self._cell).strip())
            self._cell = None
            self._in_cell = False
        elif tag == "tr" and self._row is not None:
            if any(self._row):
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            if self._table:
                self.tables.append(self._table)
            self._table = None


def fetch_html(url):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "目前 Python 環境沒有 playwright。請先執行：python -m pip install playwright"
        ) from exc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=60_000)
            return page.content()
        finally:
            browser.close()


def parse_history(html):
    parser = TableTextParser()
    parser.feed(html)

    records = []
    tables = parser.tables
    for index in range(len(tables) - 2):
        info_table = tables[index]
        number_table = tables[index + 1]
        prize_table = tables[index + 2]

        data_row = next(
            (row for row in info_table if row and row[0].isdigit() and len(row[0]) == 9),
            None,
        )
        size_row = next((row for row in number_table if row and row[0] == "大小順序"), None)
        winners_row = next((row for row in prize_table if row and row[0] == "中獎注數"), None)

        if not data_row or not size_row or not winners_row:
            continue

        records.append(
            {
                "期別": data_row[0],
                "開獎日": data_row[1],
                "大小順序": " ".join(size_row[1:6]),
                "頭獎中獎注數": int(winners_row[1].replace(",", "")),
            }
        )

    if not records:
        raise RuntimeError("沒有解析到任何今彩539資料，請確認頁面格式或查詢網址是否改變。")

    return records


def save_history(db_path, records):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS history (
                "期別" TEXT PRIMARY KEY,
                "開獎日" TEXT NOT NULL,
                "大小順序" TEXT NOT NULL,
                "頭獎中獎注數" INTEGER NOT NULL
            )
            """
        )
        before_count = conn.total_changes
        conn.executemany(
            """
            INSERT OR IGNORE INTO history ("期別", "開獎日", "大小順序", "頭獎中獎注數")
            VALUES (:期別, :開獎日, :大小順序, :頭獎中獎注數)
            """,
            records,
        )
        return conn.total_changes - before_count


def main():
    parser = argparse.ArgumentParser(description="抓取台彩今彩539歷史資料並寫入 SQLite。")
    parser.add_argument("--url", default=DEFAULT_URL, help="台彩查詢網址")
    parser.add_argument(
        "--db",
        default="lotto-539.db",
        help="輸出的 SQLite 資料庫路徑，預設為 lotto-539.db",
    )
    args = parser.parse_args()

    html = fetch_html(args.url)
    records = parse_history(html)
    inserted_count = save_history(Path(args.db), records)

    print(f"頁面抓取 {len(records)} 筆資料，新增 {inserted_count} 筆到 {args.db} 的 history 表。")
    print(f"最新期別：{records[0]['期別']}，最早期別：{records[-1]['期別']}")


if __name__ == "__main__":
    main()
