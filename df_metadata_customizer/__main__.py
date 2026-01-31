"""Database Formatter entrypoint - Launcher for UI, API, or CLI."""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))


def main() -> None:
    """Main entry point - launches UI by default."""
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "api":
            # Launch API server
            from df_metadata_customizer.api.server import main as api_main
            api_main()
        elif cmd == "cli":
            # Launch CLI
            from df_metadata_customizer.cli.commands import main as cli_main
            cli_main()
        elif cmd in ["-h", "--help"]:
            print_help()
        else:
            print(f"Unknown command: {cmd}")
            print_help()
            sys.exit(1)
    else:
        # Launch UI by default
        from df_metadata_customizer.ui.main_window import main as ui_main
        ui_main()


def print_help() -> None:
    """Print help message."""
    print("""
Database Formatter - MP3 Metadata Customizer

Usage:
  python -m df_metadata_customizer [COMMAND]

Commands:
  (none)    Launch PyQt6 UI (default)
  api       Launch REST API server (http://localhost:8000)
  cli       Launch Command-Line Interface
  
Examples:
  python -m df_metadata_customizer          # Launch UI
  python -m df_metadata_customizer api      # Start API server
  python -m df_metadata_customizer cli --help  # CLI help
""")


if __name__ == "__main__":
    main()
