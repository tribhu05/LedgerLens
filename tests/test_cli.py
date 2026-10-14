"""
Tests for Typer & Rich CLI commands.
"""

from pathlib import Path
from typer.testing import CliRunner
from ledgerlens.cli import app, storage

runner = CliRunner()


def setup_function():
    storage.clear()


def teardown_function():
    storage.clear()


def test_cli_health():
    result = runner.invoke(app, ["health"])
    assert result.exit_code == 0
    assert "Checking local AI engine status" in result.output


def test_cli_scan_text():
    result = runner.invoke(app, ["scan", "Vercel Pro Plan $20.00 on 2026-10-01", "--force-heuristic"])
    assert result.exit_code == 0
    assert "Vercel" in result.output
    assert "Saved to local ledger" in result.output


def test_cli_list():
    # First scan
    runner.invoke(app, ["scan", "Figma $15.00 on 2026-10-01", "--force-heuristic"])
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "Figma" in result.output


def test_cli_summary():
    runner.invoke(app, ["scan", "Figma $15.00 on 2026-10-01", "--force-heuristic"])
    result = runner.invoke(app, ["summary"])
    assert result.exit_code == 0
    assert "Schedule C Tax Savings Summary" in result.output


def test_cli_export(tmp_path: Path):
    runner.invoke(app, ["scan", "Figma $15.00 on 2026-10-01", "--force-heuristic"])
    export_file = tmp_path / "test_out.csv"
    result = runner.invoke(app, ["export", "--output", str(export_file)])
    assert result.exit_code == 0
    assert export_file.exists()
    content = export_file.read_text(encoding="utf-8")
    assert "Figma" in content


def test_cli_clear():
    runner.invoke(app, ["scan", "Figma $15.00 on 2026-10-01", "--force-heuristic"])
    result = runner.invoke(app, ["clear", "--yes"])
    assert result.exit_code == 0
    assert "All expenses cleared" in result.output
