# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from iaglobal.knowledge.technology import TechnologyDescriptor


@dataclass(frozen=True)
class TechnologyValidationResult:
    """Result of validating a TechnologyDescriptor against the environment.

    Unlike the generic ``ValidationResult`` (which reports pass/fail),
    this type carries evidence: *why* a technology is or isn't viable.
    """

    available: bool
    importable: bool = False
    version_installed: str = ""
    version_required: str = ""
    version_compatible: bool = False
    api_match: float = 0.0
    confidence: float = 0.5
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def success(self) -> bool:
        return self.available and self.importable


@runtime_checkable
class TechnologyValidator(Protocol):
    """Validate that a TechnologyDescriptor works in the current environment.

    Each ecosystem has its own validator:

    - PythonValidator:  ``importlib.util.find_spec()`` + version check
    - NpmValidator:     ``npm list`` + semver check
    - CratesValidator:  ``cargo metadata`` + version check

    The validator NEVER installs, removes, or mutates packages.
    It only reads the current environment state.

    Boundary Rule compliant: read-only inspection, no side effects.
    """

    ecosystem: str

    async def validate(
        self,
        technology: TechnologyDescriptor,
        required_version: str | None = None,
    ) -> TechnologyValidationResult: ...
