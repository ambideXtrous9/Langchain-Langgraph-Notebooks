"""Graph visualization export helper module."""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def export_graph_visualization(compiled_graph: Any, output_path: str = "app/static/graph.png") -> None:
    """Saves a visual PNG and Mermaid text representation of a compiled LangGraph to disk.

    Args:
        compiled_graph: The compiled LangGraph StateGraph instance.
        output_path: Path to write the .png and .mmd file to.
    """
    if compiled_graph is None:
        return

    try:
        parent_dir = os.path.dirname(output_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        # 1. Save mermaid text definition (.mmd)
        mermaid_path = output_path.replace(".png", ".mmd")
        mermaid_code = compiled_graph.get_graph().draw_mermaid()
        with open(mermaid_path, "w", encoding="utf-8") as f:
            f.write(mermaid_code)

        # 2. Save PNG if rendering is available
        try:
            png_bytes = compiled_graph.get_graph().draw_mermaid_png()
            with open(output_path, "wb") as f:
                f.write(png_bytes)
            logger.info(f"Graph visualization saved to {output_path}")
        except Exception as pe:
            logger.debug(f"Mermaid PNG online render skipped: {pe}")

    except Exception as e:
        logger.warning(f"Could not generate graph visualization for {output_path}: {e}")
