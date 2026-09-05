# HAProxy for container

[HAProxy](https://www.haproxy.org/), The Reliable, High Performance TCP/HTTP Load Balancer.

## Latest version

| Branch | Release date | End of life | Latest version | Links |
| --- | --- | --- | --- | --- |
| [3.4](http://git.haproxy.org/?p=haproxy-3.4.git) | 2026-06-03 | 2031-Q2 (LTS) | 3.4.4 | [git](http://git.haproxy.org/git/haproxy-3.4.git/) |
| [3.2](http://git.haproxy.org/?p=haproxy-3.2.git) | 2025-05-28 | 2030-Q2 (LTS) | 3.2.23 | [git](http://git.haproxy.org/git/haproxy-3.2.git/) |
| [3.0](http://git.haproxy.org/?p=haproxy-3.0.git) | 2024-05-29 | 2029-Q2 (LTS) | 3.0.27 | [git](http://git.haproxy.org/git/haproxy-3.0.git/) |

## Automated tool

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
