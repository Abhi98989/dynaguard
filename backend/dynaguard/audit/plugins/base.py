"""Plugin base interface for external security tool adapters."""
import shutil
from typing import List, Tuple
from pathlib import Path
from ..finding import AuditFinding, CoverageItem


class PluginAdapter:
    name: str = 'unknown'
    layer: str = 'code'

    def is_available(self) -> bool:
        return shutil.which(self.name) is not None

    def run(self, root: Path, offline: bool = False) -> Tuple[List[AuditFinding], CoverageItem]:
        raise NotImplementedError
