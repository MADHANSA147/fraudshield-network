"""Record installed dependency closure without unrelated host packages."""
import importlib.metadata as md
from pathlib import Path
import tomllib
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

root = Path(__file__).resolve().parents[1]
project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
pending = [Requirement(r) for r in project["dependencies"] + project["optional-dependencies"]["dev"]]
resolved = {}
while pending:
    req = pending.pop()
    name = canonicalize_name(req.name)
    dist = md.distribution(name)
    if name in resolved:
        continue
    resolved[name] = dist.version
    for text in dist.requires or []:
        child = Requirement(text)
        if child.marker is None or any(child.marker.evaluate({"extra": extra}) for extra in {"", *req.extras}):
            pending.append(child)
(root / "requirements.lock").write_text(
    "# Exact versions tested on Python 3.13 / Windows. CPU PyTorch preferred.\n"
    "# Linux wheels and secure RNG require clean-environment verification.\n"
    + "\n".join(name + "==" + version for name, version in sorted(resolved.items())) + "\n")
print("Locked", len(resolved), "installed distributions")
