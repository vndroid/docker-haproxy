# docker-haproxy updater

Checks the HAProxy remote repository for the latest stable tag and updates
`HAPROXY_VERSION`, `HAPROXY_URL`, and `HAPROXY_SHA256` in the corresponding
Dockerfile.

The tool retrieves tags with `git ls-remote --tags --refs` and only considers
stable releases from the selected branch. It obtains the SHA256 checksum from
the official HAProxy download site and validates the archive filename.

```bash
# Run from the repository root; defaults to checking and updating 3.0/Dockerfile
uv run tools update

# Check without modifying files; exits with status 1 when an update is available
uv run tools update --check

# Preview the version and SHA256 without modifying files
uv run tools update --dry-run

# Check another maintained branch
uv run tools update --branch 3.0
```

If the repository root cannot be detected automatically, specify it explicitly
with `--root /path/to/repository`.
