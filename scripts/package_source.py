"""Package Git-visible source only, excluding environments, runtime data and keys."""
import argparse
from pathlib import Path
import subprocess
import zipfile

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, default=Path("../FraudShield-source.zip"))
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
result = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                        cwd=root, check=True, capture_output=True)
names = sorted(set(n for n in result.stdout.decode().split("\0") if n))
for name in names:
    parts = Path(name).parts
    if any(p in (".git", ".venv", "var", "node_modules", "reference-review") for p in parts):
        raise ValueError("Runtime or reference data appeared in the source allowlist")
    if name.endswith((".key", ".pem")) or Path(name).name == ".env":
        raise ValueError("A private configuration appeared in the source allowlist")
with zipfile.ZipFile(args.output.resolve(), "w", zipfile.ZIP_DEFLATED) as archive:
    for name in names:
        archive.write(root / name, "fraudshield/" + Path(name).as_posix())
with zipfile.ZipFile(args.output.resolve()) as archive:
    assert archive.testzip() is None
print("Packaged", len(names), "files:", args.output.resolve())
