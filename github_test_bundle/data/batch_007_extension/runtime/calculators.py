"""Dispatch frozen local operations; no network or semantic scoring."""
import importlib.util
from pathlib import Path
def load(filename, name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.calculate
core_calculate = load("core_calculators.py", "lh_frozen_core_calculators")
revision_calculate = load("revision_calculators.py", "lh_frozen_revision_calculators")
def calculate(kind, resources, at):
    return (revision_calculate if kind.startswith("lh_") else core_calculate)(kind, resources, at)
