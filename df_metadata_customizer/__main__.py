"""Database Reformatter entrypoint."""

try:
    from df_metadata_customizer.database_reformatter import main
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

    from df_metadata_customizer.database_reformatter import main

if __name__ == "__main__":
    main()
