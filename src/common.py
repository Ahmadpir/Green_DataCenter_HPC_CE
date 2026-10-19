"""Shared paths and config loader."""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]          # code/
DATA = ROOT / "data"
OUT = ROOT / "outputs"
PAPER = ROOT.parent / "latex"
FIG = PAPER / "figures"
TAB = PAPER / "tables"


def load_cfg():
    with open(ROOT / "config" / "params.yaml", encoding="utf8") as f:
        return yaml.safe_load(f)
