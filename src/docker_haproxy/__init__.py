import argparse
import re
import subprocess
import sys
from pathlib import Path
from urllib.request import Request, urlopen


REMOTE_URL_TEMPLATE = "https://git.haproxy.org/git/haproxy-{branch}.git/"
DOWNLOAD_URL_TEMPLATE = (
    "https://www.haproxy.org/download/{branch}/src/haproxy-{version}.tar.gz"
)


class UpdateError(Exception):
    pass


def discover_branches(root: Path) -> list[str]:
    branches = [
        path.name
        for path in root.iterdir()
        if path.is_dir()
        and re.fullmatch(r"\d+\.\d+", path.name)
        and (path / "Dockerfile").is_file()
    ]
    if not branches:
        raise UpdateError(f"no HAProxy branch directories found in {root}.")
    return sorted(branches, key=lambda branch: tuple(map(int, branch.split("."))))


def find_repository_root(root: Path | None) -> Path:
    if root is not None:
        resolved = root.resolve()
        if not resolved.is_dir():
            raise UpdateError(f"repository root not found: {resolved}.")
        discover_branches(resolved)
        return resolved

    for directory in (Path.cwd(), *Path.cwd().parents):
        try:
            discover_branches(directory)
        except UpdateError:
            continue
        return directory
    raise UpdateError("unable to locate the repository root; use --root.")


def parse_current_version(dockerfile: str) -> str:
    match = re.search(r"^ENV HAPROXY_VERSION=(\S+)$", dockerfile, re.MULTILINE)
    if not match:
        raise UpdateError("HAPROXY_VERSION is missing from the Dockerfile.")
    return match.group(1)


def parse_latest_version(ls_remote_output: str, branch: str) -> str:
    pattern = re.compile(rf"refs/tags/v({re.escape(branch)}\.(\d+))$")
    versions: list[tuple[int, str]] = []

    for line in ls_remote_output.splitlines():
        match = pattern.search(line)
        if match:
            versions.append((int(match.group(2)), match.group(1)))

    if not versions:
        raise UpdateError(f"No stable v{branch}.x tags found in the remote repository.")
    return max(versions)[1]


def parse_sha256(checksum: str, expected_filename: str) -> str:
    pattern = re.compile(
        rf"^([0-9a-fA-F]{{64}})\s+\*?{re.escape(expected_filename)}$"
    )
    for line in checksum.splitlines():
        match = pattern.fullmatch(line.strip())
        if match:
            return match.group(1).lower()
    raise UpdateError(f"SHA256 for {expected_filename} not found in the checksum file.")


def render_dockerfile(content: str, version: str, url: str, sha256: str) -> str:
    replacements = {
        "HAPROXY_VERSION": version,
        "HAPROXY_URL": url,
        "HAPROXY_SHA256": sha256,
    }
    updated = content
    for name, value in replacements.items():
        updated, count = re.subn(
            rf"^ENV {name}=\S+$",
            f"ENV {name}={value}",
            updated,
            flags=re.MULTILINE,
        )
        if count != 1:
            raise UpdateError(f"the Dockerfile must contain exactly one {name}.")
    return updated


def find_dockerfile(root: Path | None, branch: str) -> Path:
    if root is not None:
        path = root.resolve() / branch / "Dockerfile"
        if not path.is_file():
            raise UpdateError(f"Dockerfile not found: {path}.")
        return path

    for directory in (Path.cwd(), *Path.cwd().parents):
        path = directory / branch / "Dockerfile"
        if path.is_file():
            return path
    raise UpdateError(
        f"unable to locate {branch}/Dockerfile from the current directory; use --root"
    )


def get_remote_tags(repo_url: str) -> str:
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--tags", "--refs", repo_url],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise UpdateError("git command not found") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or str(exc)
        raise UpdateError(f"failed to retrieve remote tags: {detail}") from exc
    return result.stdout


def get_checksum(url: str, expected_filename: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:150.0) Gecko/20100101 Firefox/150.0"})
    try:
        with urlopen(request, timeout=30) as response:
            content = response.read().decode("ascii")
    except (OSError, UnicodeError) as exc:
        raise UpdateError(f"failed to download SHA256 from {url}: {exc}") from exc
    return parse_sha256(content, expected_filename)


def update(
    branch: str,
    root: Path | None,
    repo_url: str | None,
    check: bool,
    dry_run: bool,
) -> int:
    if not re.fullmatch(r"\d+\.\d+", branch):
        raise UpdateError("branch must use a format such as 3.0.")

    dockerfile_path = find_dockerfile(root, branch)
    content = dockerfile_path.read_text(encoding="utf-8")
    current = parse_current_version(content)
    remote = repo_url or REMOTE_URL_TEMPLATE.format(branch=branch)
    latest = parse_latest_version(get_remote_tags(remote), branch)

    if tuple(map(int, latest.split("."))) < tuple(map(int, current.split("."))):
        raise UpdateError(
            f"latest remote version {latest} is older than current version {current}."
        )
    if latest == current:
        print(f"HAProxy {branch} is up to date: {current}")
        return 0
    if check:
        print(f"HAProxy {branch} update available: {current} -> {latest}.")
        return 1

    filename = f"haproxy-{latest}.tar.gz"
    download_url = DOWNLOAD_URL_TEMPLATE.format(branch=branch, version=latest)
    sha256 = get_checksum(f"{download_url}.sha256", filename)
    updated = render_dockerfile(content, latest, download_url, sha256)

    if dry_run:
        print(f"Would update {dockerfile_path}: {current} -> {latest}")
        print(f"HAPROXY_SHA256={sha256}")
        return 0

    dockerfile_path.write_text(updated, encoding="utf-8")
    print(f"Updated {dockerfile_path}: {current} -> {latest}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="docker-haproxy project tools")
    commands = parser.add_subparsers(dest="command", required=True)
    update_parser = commands.add_parser(
        "update", help="check stable HAProxy tags and update Dockerfiles"
    )
    update_parser.add_argument(
        "--branch",
        action="append",
        help="only update this branch (repeatable; default: all detected branches)",
    )
    update_parser.add_argument("--root", type=Path, help="docker-haproxy repository root")
    update_parser.add_argument("--repo-url", help="override the HAProxy Git repository URL")
    mode = update_parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="check only; exit with status 1 when an update is available",
    )
    mode.add_argument(
        "--dry-run", action="store_true", help="preview the update without writing files"
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        root = find_repository_root(args.root)
        branches = list(dict.fromkeys(args.branch or discover_branches(root)))
        if args.repo_url and len(branches) != 1:
            raise UpdateError("--repo-url requires exactly one --branch.")

        statuses = [
            update(
                branch=branch,
                root=root,
                repo_url=args.repo_url,
                check=args.check,
                dry_run=args.dry_run,
            )
            for branch in branches
        ]
        status = max(statuses)
    except (UpdateError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    raise SystemExit(status)
