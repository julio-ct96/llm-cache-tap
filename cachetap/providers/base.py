"""What every provider shares: reading the version out of a model name."""

import re


def version(model, family):
    """("gpt-5.6-luna", "gpt") -> (5, 6). Date suffixes are not mistaken for a minor version."""
    m = re.search(family + r"-(\d+)(?:[.-](\d{1,2})(?!\d))?", model or "")
    return (int(m.group(1)), int(m.group(2) or 0)) if m else None
