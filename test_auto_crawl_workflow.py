from pathlib import Path


WORKFLOW_PATH = Path(".github/workflows/auto_crawl.yml")


def test_auto_crawl_workflow_runs_daily_and_can_be_started_manually():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "schedule:" in workflow
    assert "30 14 * * *" in workflow
    assert "workflow_dispatch:" in workflow


def test_auto_crawl_workflow_fetches_history_and_commits_database_changes():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "python fetch_lotto539_history.py --db lotto-539.db" in workflow
    assert "python -m playwright install --with-deps chromium" in workflow
    assert "git add lotto-539.db" in workflow
    assert "git commit -m \"chore: auto update lotto 539 database\"" in workflow
    assert "git push" in workflow
