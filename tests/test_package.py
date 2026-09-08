"""Publish only enumerated files and exercise the skill from a clean extracted copy."""
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_package", ROOT / "scripts/build_package.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class PackageTests(unittest.TestCase):
    def test_explicit_inventory_excludes_unrelated_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "PACKAGE_FILES.txt").write_text("public.txt\n")
            (root / "public.txt").write_text("Public fixture")
            (root / "private.txt").write_text("Excluded fixture")
            output = root / "package.tar.gz"
            builder.build(output, root)
            with tarfile.open(output) as archive:
                self.assertEqual(set(archive.getnames()), {"research-skills/public.txt", "research-skills/SHA256SUMS"})
            with self.assertRaises(FileExistsError):
                builder.build(output, root)
            (root / "PACKAGE_FILES.txt").write_text("../private.txt\n")
            with self.assertRaises(ValueError):
                builder.inventory(root)

    def test_package_checksums_and_installed_helpers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "package.tar.gz"
            builder.build(output)
            # Files are our verified explicit inventory, not an external archive.
            with tarfile.open(output) as archive:
                for member in archive.getmembers():
                    self.assertTrue(member.isfile())
                    self.assertNotIn("..", Path(member.name).parts)
                    path = root / member.name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(archive.extractfile(member).read())
            package = root / "research-skills"
            for line in (package / "SHA256SUMS").read_text().splitlines():
                checksum, name = line.split("  ", 1)
                self.assertEqual(hashlib.sha256((package / name).read_bytes()).hexdigest(), checksum)
            # Helpers must work when installed in a different directory.
            result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests",
                                     "-p", "test_research.py", "-v"], cwd=package, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            manual = (package / "INSTALL.md").read_text().split("## Manual copy", 1)[1]
            install_block = re.search(r"```sh\n(.*?)\n```", manual, re.S).group(1)
            environment = dict(os.environ, HERMES_HOME=str(root / "isolated-hermes"))
            installed = subprocess.run(["bash", "-c", install_block], cwd=package,
                                       env=environment, capture_output=True, text=True)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            skill = root / "isolated-hermes/skills/research/deep-researcher"
            self.assertTrue((skill / "SKILL.md").is_file())
            self.assertTrue((skill.parent / "hermes-research-access/SKILL.md").is_file())
            help_result = subprocess.run([sys.executable, str(skill / "scripts/research_run.py"), "--help"],
                                         capture_output=True, text=True)
            self.assertEqual(help_result.returncode, 0, help_result.stderr)
            sentinel = skill / "local-customization.txt"
            sentinel.write_text("Preserve installed customization")
            repeated = subprocess.run(["bash", "-c", install_block], cwd=package,
                                      env=environment, capture_output=True, text=True)
            self.assertNotEqual(repeated.returncode, 0)
            self.assertEqual(sentinel.read_text(), "Preserve installed customization")


if __name__ == "__main__":
    unittest.main()
