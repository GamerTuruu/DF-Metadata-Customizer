#!/usr/bin/env python3
"""Fetch GitHub release download analytics, generate a bar chart, and update a Markdown summary."""

import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

REPO = "GamerTuruu/DF-Metadata-Customizer"
API_URL = f"https://api.github.com/repos/{REPO}/releases"
ANALYTICS_DIR = Path(__file__).parent
PRIMARY_COLOR = "#0e639c"


def fetch_releases(token: str | None = None) -> list[dict]:
    """Fetch all releases from the GitHub API."""
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API_URL, headers=headers)  # noqa: S310
    with urllib.request.urlopen(req) as resp:  # noqa: S310
        return json.loads(resp.read())


def build_rows(releases: list[dict]) -> list[dict]:
    """Build a flat list of {release, asset, downloads} rows."""
    rows = []
    for release in releases:
        tag = release["tag_name"]
        for asset in release.get("assets", []):
            rows.append(
                {
                    "release": tag,
                    "asset": asset["name"],
                    "downloads": asset["download_count"],
                }
            )
    return rows


def generate_graph(rows: list[dict]) -> None:
    """Generate and save a grouped bar chart of downloads per release per asset."""
    if not rows:
        print("No release assets found — skipping graph generation.")
        return

    # Aggregate: releases -> assets -> counts
    releases: dict[str, dict[str, int]] = {}
    for row in rows:
        releases.setdefault(row["release"], {})[row["asset"]] = row["downloads"]

    release_names = list(releases.keys())
    all_assets = list(dict.fromkeys(asset for assets in releases.values() for asset in assets))

    n_releases = len(release_names)
    n_assets = max(len(all_assets), 1)
    bar_width = 0.8 / n_assets

    # Build alpha shading so each asset group is distinguishable
    alphas = [0.55 + 0.45 * (i / max(n_assets - 1, 1)) for i in range(n_assets)]

    fig, ax = plt.subplots(figsize=(max(8, n_releases * 2), 6))

    for i, asset in enumerate(all_assets):
        counts = [releases[r].get(asset, 0) for r in release_names]
        x_positions = [j + (i - n_assets / 2 + 0.5) * bar_width for j in range(n_releases)]
        bars = ax.bar(x_positions, counts, bar_width, label=asset, color=PRIMARY_COLOR, alpha=alphas[i])
        for bar, count in zip(bars, counts):
            if count > 0:
                ax.annotate(
                    str(int(count)),
                    xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                )

    ax.set_xlabel("Release", fontsize=12)
    ax.set_ylabel("Downloads", fontsize=12)
    ax.set_title("Downloads per Release & Asset", fontsize=14, fontweight="bold")
    ax.set_xticks(range(n_releases))
    ax.set_xticklabels(release_names, rotation=45, ha="right")
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.set_facecolor("#f5f5f5")
    fig.patch.set_facecolor("white")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if n_assets > 1:
        ax.legend(loc="upper left", fontsize=9)

    plt.tight_layout()
    graph_path = ANALYTICS_DIR / "download_graph.png"
    plt.savefig(graph_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Graph saved to {graph_path}")


def generate_markdown(rows: list[dict]) -> None:
    """Write ANALYTICS.md with a summary table of downloads per release and asset."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total = sum(r["downloads"] for r in rows)

    lines = [
        "# Download Analytics",
        "",
        f"_Last updated: {now}_",
        "",
        f"**Total Downloads: {total:,}**",
        "",
        "## Graph",
        "",
        "![Download Graph](download_graph.png)",
        "",
        "## Downloads by Release and Asset",
        "",
        "| Release | Asset | Downloads |",
        "|---------|-------|----------:|",
    ]
    for row in rows:
        lines.append(f"| {row['release']} | {row['asset']} | {row['downloads']:,} |")

    lines.append("")

    md_path = ANALYTICS_DIR / "ANALYTICS.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Markdown saved to {md_path}")


def main() -> None:
    """Entry point."""
    token = os.environ.get("GITHUB_TOKEN")
    releases = fetch_releases(token)
    rows = build_rows(releases)
    generate_graph(rows)
    generate_markdown(rows)


if __name__ == "__main__":
    main()
