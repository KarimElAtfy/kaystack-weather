r"""Copies the old prototype's issued forecasts into the lake's `legacy` container.

Each file in `emesse/` on the `archivio` branch goes up unchanged, with a
manifest of where it came from. Run it once per town, after the old nightly
jobs are switched off and the clone is fetched:

    git -C ../../meteo-dati/pedrengometeo fetch origin archivio
    uv run python -m scripts.import_legacy --slug pedrengo \
        --clone ../../meteo-dati/pedrengometeo --lake stkaystackmeteolakeprod

`--folder` writes to a local folder instead, to look at the result first. In
prod the container is immutable: a second upload of the same name is refused.
"""

import argparse
import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from meteo.store import AzureStore, FolderStore, Store

BRANCH = "origin/archivio"

README = """\
The issued forecasts of the old prototype sites for Pedrengo and Sesto Calende,
copied unchanged from the archivio branch of their repositories. They are kept
as a descriptive record only: no score computed from them supports a claim
about the new site.

Limits of these forecasts:
- issue times varied from 07:29 to 16:37 UTC, with GitHub's delays on
  scheduled jobs;
- the target was an inverse-distance mix of stations shifted by a median offset;
- ARPA times were read as UTC, one hour off;
- daily extremes are the local-day maximum and minimum of hourly means.

Each town folder has a manifest.json listing every file with its commit and
SHA-256.
"""


def git(clone: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(clone), *args], capture_output=True, check=True).stdout


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m scripts.import_legacy")
    parser.add_argument("--clone", type=Path, required=True)
    parser.add_argument("--slug", required=True, choices=["pedrengo", "sesto-calende"])
    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--lake", help="lake storage account name")
    where.add_argument("--folder", type=Path, help="a local folder instead of the lake")
    args = parser.parse_args()

    lake: Store
    if args.folder:
        lake = FolderStore(args.folder)
    else:
        from azure.identity import AzureCliCredential

        lake = AzureStore(args.lake, AzureCliCredential())

    origin = git(args.clone, "remote", "get-url", "origin").decode().strip()
    repo = re.sub(r"^.*github\.com[:/]|\.git$", "", origin)
    tip = git(args.clone, "rev-parse", BRANCH).decode().strip()
    paths = git(args.clone, "ls-tree", "--name-only", BRANCH, "emesse/").decode().split()

    files = []
    for path in sorted(paths):
        data = git(args.clone, "show", f"{BRANCH}:{path}")
        last = git(args.clone, "log", "-1", "--format=%H%x09%cI", BRANCH, "--", path)
        commit, commit_time = last.decode().strip().split("\t")
        # A file rewritten the same day is stored in its last version only; the
        # earlier ones are named here.
        history = git(args.clone, "log", "--format=%H", BRANCH, "--", path).decode().split()
        superseded = [
            {"commit": c, "emessa": json.loads(git(args.clone, "show", f"{c}:{path}"))["emessa"]}
            for c in history[1:]
        ]
        files.append(
            {
                "path": path,
                "sha256": hashlib.sha256(data).hexdigest(),
                "emessa": json.loads(data)["emessa"],
                "commit": commit,
                "commit_time": commit_time,
                "superseded": superseded,
            }
        )
        name = f"{args.slug}/{path}"
        stored = lake.put_new("legacy", name, data, "application/json")
        print(name, "stored" if stored else "already there")

    manifest = {
        "repo": repo,
        "branch": BRANCH.removeprefix("origin/"),
        "tip_commit": tip,
        "exported_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "files": files,
    }
    body = json.dumps(manifest, indent=1).encode()
    print(f"{args.slug}/manifest.json", len(files), "files from", repo, tip[:7])
    if not lake.put_new("legacy", f"{args.slug}/manifest.json", body, "application/json"):
        print("a manifest is already there and was left as it is")
    lake.put_new("legacy", "README.txt", README.encode(), "text/plain; charset=utf-8")


if __name__ == "__main__":
    main()
