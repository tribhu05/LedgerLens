"""
Interactive Typer & Rich CLI for LedgerLens.
Provides an elegant terminal UI with tables, spinners, and deduction reports.
"""

import csv
import sys
from pathlib import Path
from typing import Optional
import typer
import uvicorn
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ledgerlens.engine import LedgerEngine
from ledgerlens.models import AuditRisk, TaxCategory
from ledgerlens.storage import LedgerStorage

app = typer.Typer(
    name="ledgerlens",
    help="LedgerLens: Privacy-First Local AI Bookkeeper & Tax Deduction Engine for Freelancers",
    add_completion=False,
)
console = Console()
storage = LedgerStorage()


@app.command()
def scan(
    source: str = typer.Argument(..., help="Path to receipt text file or raw transaction text string"),
    force_heuristic: bool = typer.Option(False, "--force-heuristic", "-h", help="Force deterministic heuristic parser"),
    auto_save: bool = typer.Option(True, "--save/--dry-run", help="Save parsed expense to local ledger database"),
):
    """Scan and parse a receipt, invoice, or bank transaction snippet."""
    # Check if source is a file path
    path = Path(source)
    if path.is_file():
        try:
            raw_text = path.read_text(encoding="utf-8")
        except Exception as e:
            console.print(f"[bold red]Error reading file {source}:[/bold red] {e}")
            raise typer.Exit(1)
    else:
        raw_text = source

    if not raw_text.strip():
        console.print("[bold red]Receipt text is empty.[/bold red]")
        raise typer.Exit(1)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="Extracting financial entities via local AI...", total=None)
        expense = LedgerEngine.create_expense_from_text(raw_text, force_heuristic=force_heuristic)

    # Render result panel
    risk_color = "green" if expense.audit_risk == AuditRisk.LOW else "yellow" if expense.audit_risk == AuditRisk.MEDIUM else "red"
    engine_badge = f"[cyan]{expense.parsed_by}[/cyan]"

    details = (
        f"[bold]ID:[/bold] {expense.id}\n"
        f"[bold]Merchant:[/bold] {expense.merchant}\n"
        f"[bold]Date:[/bold] {expense.date}\n"
        f"[bold]Gross Amount:[/bold] ${expense.amount:.2f} {expense.currency}\n"
        f"[bold]Category:[/bold] [magenta]{expense.category.value}[/magenta]\n"
        f"[bold]Deductible Rate:[/bold] {int(expense.deductible_percentage * 100)}%\n"
        f"[bold]Deductible Amount:[/bold] [bold green]${expense.deductible_amount:.2f}[/bold green]\n"
        f"[bold]Audit Risk:[/bold] [{risk_color}]{expense.audit_risk.value}[/{risk_color}]\n"
        f"[bold]Engine:[/bold] {engine_badge}"
    )

    if expense.audit_flag_reason:
        details += f"\n[bold yellow]Audit Notice:[/bold yellow] {expense.audit_flag_reason}"

    console.print(Panel(details, title="[LedgerLens] Scanned Receipt & Tax Classification", border_style="green"))

    if auto_save:
        storage.add_expense(expense)
        console.print(f"[bold green][OK] Saved to local ledger![/bold green] (Storage: ~/.ledgerlens/expenses.json)")


@app.command(name="list")
def list_all(
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter by tax category name"),
):
    """List all recorded business expenses in a formatted table."""
    cat_filter = None
    if category:
        for c in TaxCategory:
            if category.lower() in c.value.lower() or category.lower() in c.name.lower():
                cat_filter = c
                break

    expenses = storage.list_expenses(category=cat_filter)
    if not expenses:
        console.print("[yellow]No expenses recorded yet. Use `ledgerlens scan` to add receipts.[/yellow]")
        return

    table = Table(title="Recorded Business Expenses", show_header=True, header_style="bold cyan")
    table.add_column("ID", style="dim", width=8)
    table.add_column("Date", width=10)
    table.add_column("Merchant", width=20)
    table.add_column("Category", width=24)
    table.add_column("Gross", justify="right", width=10)
    table.add_column("Deductible", justify="right", width=12)
    table.add_column("Risk", width=8)
    table.add_column("Engine", style="dim", width=16)

    for e in expenses:
        risk_style = "green" if e.audit_risk == AuditRisk.LOW else "yellow" if e.audit_risk == AuditRisk.MEDIUM else "red"
        table.add_row(
            e.id,
            e.date,
            e.merchant,
            e.category.value,
            f"${e.amount:.2f}",
            f"[green]${e.deductible_amount:.2f}[/green]",
            f"[{risk_style}]{e.audit_risk.value}[/{risk_style}]",
            e.parsed_by,
        )

    console.print(table)


@app.command()
def summary():
    """Display real-time tax deduction analytics and estimated tax savings."""
    sum_data = storage.compute_tax_summary()

    if sum_data.total_expenses_count == 0:
        console.print("[yellow]No expenses found. Add expenses using `ledgerlens scan`.[/yellow]")
        return

    headline = (
        f"[bold]Total Expenses Logged:[/bold] {sum_data.total_expenses_count}\n"
        f"[bold]Gross Business Spend:[/bold] ${sum_data.total_gross_amount:.2f}\n"
        f"[bold]Total Tax Deductions:[/bold] [bold green]${sum_data.total_deductible_amount:.2f}[/bold green]\n"
        f"[bold]Estimated Tax Savings (25% Bracket):[/bold] [bold cyan]${sum_data.estimated_tax_savings_25pct:.2f}[/bold cyan]"
    )
    console.print(Panel(headline, title="Schedule C Tax Savings Summary", border_style="cyan"))

    table = Table(title="Deductions by Category", show_header=True, header_style="bold magenta")
    table.add_column("Category", width=28)
    table.add_column("Items", justify="center", width=8)
    table.add_column("Gross Total", justify="right", width=12)
    table.add_column("Deductible %", justify="center", width=12)
    table.add_column("Deductible Total", justify="right", width=14)

    for cat in sum_data.categories:
        table.add_row(
            cat.category_name,
            str(cat.count),
            f"${cat.gross_total:.2f}",
            f"{int(cat.deductible_percentage * 100)}%",
            f"[green]${cat.deductible_total:.2f}[/green]",
        )
    console.print(table)

    if sum_data.audit_risk_alerts:
        console.print("\n[bold red][!] Audit Flags & Compliance Notices:[/bold red]")
        for alert in sum_data.audit_risk_alerts:
            console.print(f"  * {alert}")


@app.command()
def health():
    """Check connectivity to local Google Gemma 2B model via Ollama."""
    console.print("[bold]Checking local AI engine status...[/bold]")
    status = LedgerEngine.check_health()
    if status.ollama_running and status.model_available:
        console.print(f"[bold green][OK] Ollama is running with {status.model_name} active![/bold green] (Latency: {status.latency_ms}ms)")
    elif status.ollama_running:
        console.print(f"[bold yellow][!] Ollama is running, but {status.model_name} was not found.[/bold yellow]")
        console.print("  Run: [cyan]ollama pull gemma2:2b[/cyan]")
    else:
        console.print(f"[bold blue][i] Local Ollama is offline.[/bold blue]")
        console.print("  Running with LedgerLens's 100% offline deterministic heuristic engine.")


@app.command()
def export(
    output: Path = typer.Option(Path("expenses_export.csv"), "--output", "-o", help="Output file path (CSV)"),
):
    """Export all expenses to an audit-ready CSV file."""
    expenses = storage.list_expenses()
    if not expenses:
        console.print("[yellow]No expenses to export.[/yellow]")
        return

    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "Date", "Merchant", "Category", "Amount", "Currency", "Deductible_Pct", "Deductible_Amount", "Audit_Risk", "Engine", "Description"])
        for e in expenses:
            writer.writerow([
                e.id,
                e.date,
                e.merchant,
                e.category.value,
                f"{e.amount:.2f}",
                e.currency,
                f"{e.deductible_percentage:.2f}",
                f"{e.deductible_amount:.2f}",
                e.audit_risk.value,
                e.parsed_by,
                e.description,
            ])

    console.print(f"[bold green][OK] Successfully exported {len(expenses)} expenses to {output}![/bold green]")


@app.command()
def clear(
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Clear all stored expenses."""
    if not confirm and not typer.confirm("Are you sure you want to delete all stored expenses?"):
        console.print("Aborted.")
        raise typer.Exit()
    storage.clear()
    console.print("[bold green][OK] All expenses cleared.[/bold green]")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Host interface to bind"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to listen on"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload for development"),
):
    """Start the LedgerLens FastAPI REST backend server."""
    console.print(f"[bold green]Launching LedgerLens API at http://{host}:{port}[/bold green]")
    console.print(f"[cyan]Swagger API Docs available at http://{host}:{port}/docs[/cyan]")
    uvicorn.run("ledgerlens.api:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
