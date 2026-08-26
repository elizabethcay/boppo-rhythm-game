"""boppo_chart — offline chart-generation pipeline for the Boppo rhythm game.

Audio in -> onset/beat analysis -> lane assignment -> chart.json (+ Rust codegen)
+ device-format audio. Runs on a computer, never on the tablet.
"""

from .chart import Chart, Note
from .lanes import Onset, build_notes

__all__ = ["Chart", "Note", "Onset", "build_notes"]
__version__ = "0.1.0"
