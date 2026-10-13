"""verilog-explorer — read a synthesised netlist and render it for browsing.

One command, one file, no server: `verilog-explorer netlist.json --src-root . -o page.html`.
"""

from __future__ import annotations

from verilog_explorer.cli import main

__all__ = ["main"]
