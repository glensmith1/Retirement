#!/usr/bin/env python

"""
Rich development tools
"""

from rich.console import Console
from rich.table import Table

console = Console()


def RichTableViewer(
    pf: list[list], table_title: str = "", color: str = "white", first_row: bool = True
) -> Table:
    """
    Displays a list of list in a rich table
    """
    table = Table(title=table_title)

    # Set up columns
    df = pf
    if first_row is True:
        df = pf[1:]
        for colname in pf[0]:
            table.add_column(colname, justify="right", style=color, no_wrap=False)

    # Load data
    for value_list in df:
        row = [str(x) for x in value_list]
        table.add_row(*row)

    return table
