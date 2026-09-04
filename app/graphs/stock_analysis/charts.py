"""Deterministic Chart Renderer, Chart Critic, and Chart Curator for NSE Stock Analysis."""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import pandas as pd
from app.tools.stock_fact_store import StockFactStore

logger = logging.getLogger(__name__)


def render_chart(
    chart_id: str,
    title: str,
    chart_type: str,
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    output_dir: str = "app/static/top_charts",
) -> Optional[str]:
    """Deterministically renders a publication-grade PNG chart using Matplotlib."""
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, f"{chart_id}.png")

    if df.empty or x_col not in df.columns or y_col not in df.columns:
        logger.warning(f"Cannot render chart {chart_id}: missing columns or empty data.")
        return None

    plt.style.use("default")
    fig, ax = plt.subplots(figsize=(9, 4.8), dpi=160)
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#ffffff")

    # Clean spines & horizontal grid matching institutional dossier
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#cbd5e1")
    ax.spines["bottom"].set_color("#cbd5e1")
    ax.grid(True, axis="y", linestyle="--", alpha=0.6, color="#e2e8f0")
    ax.grid(False, axis="x")

    burgundy = "#8b1528"
    burgundy_border = "#6b1d2f"
    navy = "#1e3a8a"

    try:
        clean_title = title.replace("₹", "INR ")
        if chart_type == "bar":
            plot_df = df.head(10)
            ax.bar(range(len(plot_df)), plot_df[y_col], color=burgundy, edgecolor=burgundy_border, width=0.65, alpha=0.92)
            ax.set_xticks(range(len(plot_df)))
            ax.set_xticklabels(plot_df[x_col].astype(str), rotation=25, ha="right", fontsize=9, color="#1e293b")
            ax.set_ylabel(y_col.replace("_", " ").title(), fontsize=9.5, fontweight="600", color="#475569")
            # Annotate values on top of bars
            for idx_bar, val_bar in enumerate(plot_df[y_col]):
                ax.annotate(
                    f"{val_bar:.1f}",
                    xy=(idx_bar, val_bar),
                    xytext=(0, 4),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=8.5,
                    fontweight="bold",
                    color="#0f172a",
                )

        elif chart_type == "scatter":
            # Risk-return or Valuation vs ROE scatter plot
            ax.scatter(df[x_col], df[y_col], c=burgundy, s=70, alpha=0.85, edgecolors=burgundy_border)
            ax.set_xlabel(x_col.replace("_", " ").title(), fontsize=9.5, fontweight="600", color="#475569")
            ax.set_ylabel(y_col.replace("_", " ").title(), fontsize=9.5, fontweight="600", color="#475569")
            # Label top 6 outliers
            for _, row in df.head(6).iterrows():
                label = row.get("symbol", str(row[x_col]))
                ax.annotate(str(label), (row[x_col], row[y_col]), fontsize=8, alpha=0.9, xytext=(4, 4), textcoords="offset points", color="#1e293b")

        elif chart_type == "line":
            plot_df = df.head(15)
            ax.plot(range(len(plot_df)), plot_df[y_col], marker="o", color=burgundy, linewidth=2.2, markersize=5)
            ax.set_xticks(range(len(plot_df)))
            ax.set_xticklabels(plot_df[x_col].astype(str), rotation=25, ha="right", fontsize=9, color="#1e293b")
            ax.set_ylabel(y_col.replace("_", " ").title(), fontsize=9.5, fontweight="600", color="#475569")

        else:
            plot_df = df.head(8)
            ax.bar(range(len(plot_df)), plot_df[y_col], color=burgundy, edgecolor=burgundy_border, width=0.65)
            ax.set_xticks(range(len(plot_df)))
            ax.set_xticklabels(plot_df[x_col].astype(str), rotation=25, ha="right", fontsize=9, color="#1e293b")

        ax.set_title(clean_title, fontsize=11.5, fontweight="bold", pad=14, color="#0f172a")
        plt.tight_layout()
        fig.savefig(file_path, bbox_inches="tight", facecolor=fig.get_facecolor(), edgecolor="none")
        plt.close(fig)
        logger.info(f"Chart rendered successfully: {file_path}")
        return file_path


    except Exception as exc:
        plt.close(fig)
        logger.error(f"Error rendering chart {chart_id}: {exc}")
        return None


def run_chart_critic(chart_spec: Dict[str, Any], realized_df: pd.DataFrame) -> Tuple[bool, str]:
    """Chart Critic: Evaluates realized data to ensure visual integrity and prevent misleading plots."""
    if realized_df is None or realized_df.empty:
        return False, "Drop chart: Realized SQL returned zero rows."

    if len(realized_df) < 2:
        return False, "Drop chart: Insufficient data points (fewer than 2 rows)."

    y_col = chart_spec.get("y_col")
    if y_col in realized_df.columns:
        vals = pd.to_numeric(realized_df[y_col], errors="coerce").dropna()
        if vals.empty:
            return False, f"Drop chart: Target column {y_col} contains no numeric values."
        if vals.min() == vals.max():
            return False, f"Drop chart: Zero variance in {y_col} across all records."

    return True, "Chart approved by Chart Critic."


def curate_charts(
    rendered_charts: List[Dict[str, Any]],
    output_dir: str = "app/static/top_charts",
    top_k: int = 4,
) -> Tuple[List[Dict[str, Any]], str]:
    """Chart Curator: Ranks charts by severity, question relevance, and data volume; selects top K and writes figures.json."""
    os.makedirs(output_dir, exist_ok=True)
    approved = [c for c in rendered_charts if c.get("critic_verdict") == "approved" and c.get("file_path")]

    # Rank based on data points and severity score
    for c in approved:
        score = c.get("data_count", 5) * 1.5 + (10 if "breakout" in c.get("id", "") or "valuation" in c.get("id", "") else 5)
        c["curator_score"] = score

    approved.sort(key=lambda x: x.get("curator_score", 0), reverse=True)
    top_exhibits = approved[:top_k]

    for rank, ex in enumerate(top_exhibits, 1):
        ex["curator_rank"] = rank

    # Write figures.json inventory
    inventory_path = os.path.join(output_dir, "figures.json")
    try:
        with open(inventory_path, "w", encoding="utf-8") as f:
            json.dump(top_exhibits, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to write figures.json: {e}")

    return top_exhibits, inventory_path
