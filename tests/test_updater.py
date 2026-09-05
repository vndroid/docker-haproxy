import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from docker_haproxy import (
    UpdateError,
    build_parser,
    discover_branches,
    parse_current_version,
    parse_latest_version,
    parse_sha256,
    render_dockerfile,
)


class UpdaterTests(unittest.TestCase):
    def test_discovers_and_numerically_sorts_branch_directories(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for branch in ("3.10", "3.2", "3.4", "not-a-branch"):
                (root / branch).mkdir()
            for branch in ("3.10", "3.2"):
                (root / branch / "Dockerfile").touch()

            self.assertEqual(discover_branches(root), ["3.2", "3.10"])

    def test_update_command_defaults_to_all_branches(self) -> None:
        args = build_parser().parse_args(["update"])

        self.assertIsNone(args.branch)

    def test_latest_version_uses_numeric_patch_order(self) -> None:
        output = "\n".join(
            [
                "aaa\trefs/tags/v3.0.9",
                "bbb\trefs/tags/v3.0.27",
                "ccc\trefs/tags/v3.0-dev28",
                "ddd\trefs/tags/v3.2.30",
                "eee\trefs/tags/v3.0.100",
            ]
        )

        self.assertEqual(parse_latest_version(output, "3.0"), "3.0.100")

    def test_latest_version_rejects_missing_stable_tag(self) -> None:
        with self.assertRaises(UpdateError):
            parse_latest_version("aaa\trefs/tags/v3.0-dev1", "3.0")

    def test_parse_sha256_validates_filename(self) -> None:
        digest = "a" * 64
        checksum = f"{digest}  haproxy-3.0.28.tar.gz\n"

        self.assertEqual(parse_sha256(checksum, "haproxy-3.0.28.tar.gz"), digest)
        with self.assertRaises(UpdateError):
            parse_sha256(checksum, "haproxy-3.0.29.tar.gz")

    def test_render_dockerfile_updates_all_release_values(self) -> None:
        original = "\n".join(
            [
                "ENV HAPROXY_VERSION=3.0.27",
                "ENV HAPROXY_URL=https://example.test/haproxy-3.0.27.tar.gz",
                f"ENV HAPROXY_SHA256={'a' * 64}",
                "RUN true",
                "",
            ]
        )
        url = "https://example.test/haproxy-3.0.28.tar.gz"
        updated = render_dockerfile(original, "3.0.28", url, "b" * 64)

        self.assertEqual(parse_current_version(updated), "3.0.28")
        self.assertIn(f"ENV HAPROXY_URL={url}", updated)
        self.assertIn(f"ENV HAPROXY_SHA256={'b' * 64}", updated)
        self.assertTrue(updated.endswith("RUN true\n"))


if __name__ == "__main__":
    unittest.main()
