"""Plugin registry for external security scanner adapters."""
from typing import List
from .base import PluginAdapter
from .gitleaks import GitleaksPlugin
from .osv import OsvPlugin
from .semgrep import SemgrepPlugin
from .trivy import TrivyPlugin


def get_all_plugins() -> List[PluginAdapter]:
    return [
        GitleaksPlugin(),
        OsvPlugin(),
        SemgrepPlugin(),
        TrivyPlugin(),
    ]
