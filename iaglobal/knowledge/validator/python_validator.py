# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

from __future__ import annotations

import importlib.metadata
import importlib.util
import logging
from typing import Optional

from iaglobal.knowledge.contracts import MaturityLevel
from iaglobal.knowledge.technology import TechnologyDescriptor
from iaglobal.knowledge.validator.protocol import (
    TechnologyValidationResult,
    TechnologyValidator,
)

logger = logging.getLogger(__name__)

# Version comparison helpers
# PEP 440 is complex; for the minimal version we handle:
#   exact: "4.2.5"
#   minimum: ">=4.0.0"
#   range: ">=4.0.0,<5.0.0"


def _parse_version_spec(spec: str) -> tuple[str, str, str | None]:
    """Return (operator, version, upper_version)."""
    spec = spec.strip()
    if spec.startswith(">="):
        parts = spec[2:].split(",", 1)
        lower = parts[0].strip()
        upper = parts[1].strip() if len(parts) > 1 else None
        if upper and upper.startswith("<"):
            return (">=", lower, upper[1:].strip())
        return (">=", lower, None)
    if spec.startswith(">"):
        return (">", spec[1:].strip(), None)
    if spec.startswith("<="):
        return ("<=", spec[2:].strip(), None)
    if spec.startswith("<"):
        return ("<", spec[1:].strip(), None)
    if spec.startswith("=="):
        return ("==", spec[3:].strip(), None)
    if spec.startswith("~="):
        return ("~=", spec[2:].strip(), None)
    return ("==", spec.strip(), None)


def _version_tuple(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(p) for p in v.split(".") if p.isdigit())
    except ValueError:
        return (0,)


def _check_version(installed: str, required: str) -> bool:
    """Check if installed version satisfies the required spec.

    Supports: exact (``4.2.5``), minimum (``>=4.0.0``),
    range (``>=1.0,<2.0``).
    """
    op, ver, upper = _parse_version_spec(required)
    iv = _version_tuple(installed)
    rv = _version_tuple(ver)

    if op == "==":
        return iv == rv
    if op == ">=":
        if iv < rv:
            return False
        if upper:
            uv = _version_tuple(upper)
            if iv >= uv:
                return False
        return True
    if op == ">":
        return iv > rv
    if op == "<=":
        return iv <= rv
    if op == "<":
        return iv < rv
    if op == "~=":
        # PEP 440 compatible release: first N-1 segments exact, last <= installed
        prefix = rv[:-1]
        iv_part = iv[: len(prefix)]
        if iv_part != prefix:
            return False
        # Remaining segments of installed must be >= last segment of required
        iv_rest = iv[len(prefix) :]
        rv_last = rv[-1:]
        return (iv_rest or (0,)) >= rv_last
    return False


class PythonValidator:
    """Validate Python packages against the installed environment.

    Uses ``importlib.util.find_spec()`` (does NOT execute module code)
    and ``importlib.metadata.version()`` to check availability and
    version compatibility.

    Boundary Rule compliant: read-only, no side effects, no execution
    of discovered code.
    """

    ecosystem = "python"

    async def validate(
        self,
        technology: TechnologyDescriptor,
        required_version: str | None = None,
    ) -> TechnologyValidationResult:
        """Validate that *technology* is available in the current Python env."""
        name = technology.name
        pkg_name = name.replace("-", "_")

        # Check existence without importing
        spec = importlib.util.find_spec(pkg_name)
        available = spec is not None

        # Check installed version
        version_installed = ""
        try:
            version_installed = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass

        required = required_version or ""
        version_compatible = (
            _check_version(version_installed, required)
            if required and version_installed
            else True
        )

        # Importable: stronger check that the module actually loads
        importable = False
        errors: list[str] = []
        if available:
            try:
                importlib.import_module(pkg_name)
                importable = True
            except ImportError as exc:
                errors.append(f"import failed: {exc}")
            except Exception as exc:
                errors.append(f"unexpected error on import: {exc}")

        confidence = _compute_confidence(
            technology, available, importable, version_compatible
        )

        return TechnologyValidationResult(
            available=available,
            importable=importable,
            version_installed=version_installed,
            version_required=required,
            version_compatible=version_compatible,
            confidence=confidence,
            errors=tuple(errors),
        )


def _compute_confidence(
    tech: TechnologyDescriptor,
    available: bool,
    importable: bool,
    version_compatible: bool,
) -> float:
    """Heuristic confidence score (0–1) that the technology works."""
    if not available:
        return 0.0
    base = 0.5
    if importable:
        base += 0.3
    if version_compatible:
        base += 0.15
    # Mature/stable packages get a small bonus
    if tech.maturity in (MaturityLevel.STABLE, MaturityLevel.GOLD):
        base += 0.05
    return round(min(base, 1.0), 4)
