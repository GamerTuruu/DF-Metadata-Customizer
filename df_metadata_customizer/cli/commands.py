"""Command-Line Interface using Click."""

import sys
import logging
import json
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

import click
from rich.logging import RichHandler
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from df_metadata_customizer.core import (
    FileManager,
    SettingsManager,
    PresetService,
    song_utils,
)
from df_metadata_customizer.core.metadata import MetadataFields

# Setup logging
logging_handler = RichHandler(
    show_time=True,
    show_level=True,
    show_path=False,
    markup=False,
    rich_tracebacks=True,
)
logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[logging_handler])

logger = logging.getLogger(__name__)
console = Console()


@click.group()
@click.version_option(version="2.0.0")
def cli() -> None:
    """Database Formatter - MP3 Metadata Customizer CLI.
    
    Powerful tool for managing MP3 metadata and applying presets to cover song collections.
    """
    pass


@cli.command()
@click.argument("folder", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option("--limit", "-l", default=None, type=int, help="Limit number of files to scan")
def scan(folder: str, limit: Optional[int] = None) -> None:
    """Scan a folder for MP3 files and display statistics."""
    try:
        console.print(f"\n📁 Scanning folder: [bold]{folder}[/bold]")
        
        file_manager = FileManager()
        file_manager.load_folder(folder)
        
        files = file_manager.get_all_files()
        
        if limit:
            files = files[:limit]
            console.print(f"(Showing first {limit} of {file_manager.df.height} files)")
        
        if not files:
            console.print("[yellow]No MP3 files found[/yellow]\n")
            return
        
        # Create table
        table = Table(title=f"Found {len(files)} MP3 Files")
        table.add_column("Title", style="cyan")
        table.add_column("Artist", style="magenta")
        table.add_column("Version", style="yellow")
        table.add_column("Date", style="green")
        
        for file_data in files:
            title = file_data.get(MetadataFields.TITLE, "")[:30]
            artist = file_data.get(MetadataFields.ARTIST, "")[:20]
            version = str(file_data.get(MetadataFields.VERSION, ""))[:10]
            date = file_data.get(MetadataFields.DATE, "")[:10]
            
            table.add_row(title, artist, version, date)
        
        console.print(table)
        console.print(f"\n✅ Total files: {file_manager.df.height}\n")
        
    except Exception as e:
        console.print(f"[red]Error scanning folder: {e}[/red]\n")
        sys.exit(1)


@cli.command()
@click.argument("folder", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.argument("preset_name")
@click.option("--dry-run", is_flag=True, help="Show what would be done without making changes")
@click.option("--filter", "-f", default=None, help="Filter files (search query)")
def apply(folder: str, preset_name: str, dry_run: bool = False, filter: Optional[str] = None) -> None:
    """Apply a preset to files in a folder."""
    try:
        SettingsManager.initialize()
        preset_service = PresetService(SettingsManager.get_presets_folder())
        
        # Load preset
        console.print(f"\n📋 Loading preset: [bold]{preset_name}[/bold]")
        preset = preset_service.load_preset(preset_name)
        
        if not preset:
            console.print(f"[red]Preset not found: {preset_name}[/red]\n")
            sys.exit(1)
        
        console.print(f"✅ Preset loaded with {len(preset.rules)} rules")
        
        # Load files
        console.print(f"📁 Loading files from: [bold]{folder}[/bold]")
        file_manager = FileManager()
        file_manager.load_folder(folder)
        
        files = file_manager.get_all_files()
        console.print(f"✅ Found {len(files)} files")
        
        # Filter if needed
        if filter:
            console.print(f"🔍 Filtering with: {filter}")
            # TODO: Implement filtering
        
        # Apply preset
        applied_count = 0
        failed_count = 0
        
        with console.status("[bold green]Applying preset...") as status:
            for i, file_data in enumerate(files):
                file_path = file_data.get("path", "")
                
                try:
                    # Get current metadata
                    json_data = song_utils.extract_json_from_song(file_path) or {}
                    
                    # Apply preset
                    result = preset_service.apply_preset(preset, json_data)
                    
                    if not dry_run:
                        # Write back
                        success = song_utils.write_json_to_song(file_path, result)
                        if success:
                            applied_count += 1
                        else:
                            failed_count += 1
                    else:
                        applied_count += 1
                    
                    status.update(f"[bold green]Processing: {i+1}/{len(files)}")
                    
                except Exception as e:
                    logger.warning(f"Failed to process {file_path}: {e}")
                    failed_count += 1
        
        mode = "[yellow](DRY RUN)[/yellow] " if dry_run else ""
        console.print(f"\n{mode}✅ Applied to {applied_count} files")
        if failed_count > 0:
            console.print(f"[red]❌ Failed for {failed_count} files[/red]")
        console.print()
        
    except Exception as e:
        console.print(f"[red]Error applying preset: {e}[/red]\n")
        sys.exit(1)


@cli.command()
def list_presets() -> None:
    """List all available presets."""
    try:
        SettingsManager.initialize()
        preset_service = PresetService(SettingsManager.get_presets_folder())
        
        presets = preset_service.list_presets()
        
        if not presets:
            console.print("\n[yellow]No presets found[/yellow]\n")
            return
        
        console.print("\n📋 Available Presets:\n")
        
        for i, preset_name in enumerate(presets, 1):
            preset = preset_service.load_preset(preset_name)
            if preset:
                rule_count = len(preset.rules)
                desc = f": {preset.description}" if preset.description else ""
                console.print(f"  {i}. [bold]{preset_name}[/bold] ({rule_count} rules){desc}")
        
        console.print()
        
    except Exception as e:
        console.print(f"[red]Error listing presets: {e}[/red]\n")
        sys.exit(1)


@cli.command()
@click.argument("preset_name")
@click.option("--name", "-n", prompt="Condition field name", help="Field to check")
@click.option("--operator", "-o", prompt="Operator", type=click.Choice([
    "is", "contains", "starts with", "ends with", "is empty", "is not empty"
]), help="Condition operator")
@click.option("--value", "-v", prompt="Condition value", help="Condition value")
@click.option("--action-field", "-af", prompt="Action field", help="Field to modify")
@click.option("--action-value", "-av", prompt="Action value", help="New value")
@click.option("--description", "-d", default="", help="Rule description")
def add_rule(preset_name: str, name: str, operator: str, value: str, action_field: str, 
             action_value: str, description: str) -> None:
    """Add a rule to an existing preset."""
    try:
        SettingsManager.initialize()
        preset_service = PresetService(SettingsManager.get_presets_folder())
        
        # Load preset
        preset = preset_service.load_preset(preset_name)
        if not preset:
            console.print(f"[red]Preset not found: {preset_name}[/red]\n")
            sys.exit(1)
        
        # Add rule
        from df_metadata_customizer.core.preset_service import PresetRule, PresetCondition, PresetAction
        
        rule = PresetRule(
            name=name,
            description=description,
            condition=PresetCondition(field=name, operator=operator, value=value),
            action=PresetAction(field=action_field, value=action_value),
        )
        
        preset.rules.append(rule)
        
        # Save
        preset_service.save_preset(preset)
        
        console.print(f"\n✅ Rule added to preset: [bold]{preset_name}[/bold]\n")
        
    except Exception as e:
        console.print(f"[red]Error adding rule: {e}[/red]\n")
        sys.exit(1)


@cli.command()
@click.argument("preset_name")
def show_preset(preset_name: str) -> None:
    """Show details of a preset."""
    try:
        SettingsManager.initialize()
        preset_service = PresetService(SettingsManager.get_presets_folder())
        
        preset = preset_service.load_preset(preset_name)
        if not preset:
            console.print(f"[red]Preset not found: {preset_name}[/red]\n")
            sys.exit(1)
        
        console.print(f"\n📋 Preset: [bold]{preset.name}[/bold]")
        console.print(f"Description: {preset.description}")
        console.print(f"Version: {preset.version}")
        console.print(f"Rules: {len(preset.rules)}\n")
        
        if preset.rules:
            table = Table(title="Rules")
            table.add_column("Name", style="cyan")
            table.add_column("Condition", style="magenta")
            table.add_column("Action", style="yellow")
            table.add_column("Enabled", style="green")
            
            for rule in preset.rules:
                cond = f"{rule.condition.field} {rule.condition.operator} '{rule.condition.value}'"
                action = f"{rule.action.field} = '{rule.action.value}'"
                enabled = "✓" if rule.enabled else "✗"
                
                table.add_row(rule.name, cond, action, enabled)
            
            console.print(table)
        
        console.print()
        
    except Exception as e:
        console.print(f"[red]Error showing preset: {e}[/red]\n")
        sys.exit(1)


@cli.command()
@click.argument("folder", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option("--format", "-f", type=click.Choice(["json", "csv"]), default="json", help="Export format")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
def export_metadata(folder: str, format: str, output: Optional[str] = None) -> None:
    """Export metadata from files to JSON or CSV."""
    try:
        console.print(f"\n📁 Loading files from: [bold]{folder}[/bold]")
        
        file_manager = FileManager()
        file_manager.load_folder(folder)
        
        files = file_manager.get_all_files()
        console.print(f"✅ Found {len(files)} files")
        
        # Set default output path
        if not output:
            output = f"metadata_export.{format}"
        
        if format == "json":
            with open(output, "w", encoding="utf-8") as f:
                json.dump(files, f, indent=2, ensure_ascii=False)
        elif format == "csv":
            import csv
            
            if not files:
                console.print("[yellow]No files to export[/yellow]\n")
                return
            
            # Get all keys
            all_keys = set()
            for file_data in files:
                all_keys.update(file_data.keys())
            
            with open(output, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=sorted(all_keys))
                writer.writeheader()
                writer.writerows(files)
        
        console.print(f"✅ Exported to: [bold]{output}[/bold]\n")
        
    except Exception as e:
        console.print(f"[red]Error exporting metadata: {e}[/red]\n")
        sys.exit(1)


def main() -> None:
    """Entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()
