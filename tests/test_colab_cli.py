"""Offline smoke tests for official Colab CLI workflow; no VM is allocated."""
from __future__ import annotations
from contextlib import redirect_stdout
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import colab_benchmark_cli as cli
import colab_benchmark_job as job


class LocalCLI(unittest.TestCase):
    def test_small_selection(self):
        self.assertEqual(cli.model_ids("small"), ["qwen08", "botpsy", "mini_agent", "qwen2b"])
        self.assertEqual(cli.model_ids("small,botpsy"), cli.model_ids("small"))
        self.assertLess(cli.planned_gb(cli.model_ids("small")), 16)

    def test_adapter_deduplicates_base_weights(self):
        self.assertLess(cli.planned_gb(cli.model_ids("lfm3_base,lfm3_hermes")), 3)
        with self.assertRaises(ValueError):
            cli.model_ids("bogus")

    def test_dry_run_has_no_cloud_or_installs(self):
        with mock.patch.object(cli, "install_colab_cli", side_effect=AssertionError("installed")), \
             mock.patch.object(cli, "invoke", side_effect=AssertionError("cloud called")), \
             redirect_stdout(io.StringIO()) as stream:
            status = cli.main(["--models", "small", "--dry-run"])
        self.assertEqual(status, 0)
        self.assertIn("DRY RUN", stream.getvalue())

    def test_no_cost_if_invalid_model_or_large(self):
        with mock.patch.object(cli, "install_colab_cli", side_effect=AssertionError("installed")):
            with self.assertRaises(ValueError):
                cli.main(["--models", "madeup", "--yes"])
            with self.assertRaises(SystemExit):
                cli.main(["--models", "all", "--yes"])

    def test_run_download_stop_even_on_failure(self):
        calls = []
        def fake_invoke(argv, quiet_failure=False):
            calls.append(argv)
            return 17 if "run" in argv else 0
        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(cli, "install_colab_cli", return_value="/usr/bin/colab"), \
             mock.patch.object(cli, "git_head", return_value="a"*40), \
             mock.patch.object(cli, "invoke", side_effect=fake_invoke), \
             mock.patch.object(cli, "retrieve", return_value=None), \
             redirect_stdout(io.StringIO()):
            status = cli.main(["--yes", "--session", "edgebench-test", "--models", "small",
                               "--results-dir", td])
        self.assertEqual(status, 17)
        self.assertIn("run", calls[0])
        self.assertIn("--keep", calls[0])
        self.assertIn("--gpu", calls[0])
        self.assertEqual(calls[-1][-3:], ["-s", "edgebench-test"] if False else ["stop", "-s", "edgebench-test"])

    def test_retrieve_zip_and_reject_path_traversal(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            archive = d / "edgebench-test.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("comparison.md", "# OK\n")
                z.writestr("results.json", "{}")
            with mock.patch.object(cli, "invoke", return_value=0), redirect_stdout(io.StringIO()):
                out = cli.retrieve(["colab"], "edgebench-test", d)
            self.assertEqual(out, archive)
            self.assertEqual((d/"edgebench-test"/"comparison.md").read_text(), "# OK\n")
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("../outside.txt", "bad")
            with mock.patch.object(cli, "invoke", return_value=0), redirect_stdout(io.StringIO()):
                with self.assertRaises(RuntimeError):
                    cli.retrieve(["colab"], "edgebench-test", d)
            self.assertFalse((d/"outside.txt").exists())


class RemoteJob(unittest.TestCase):
    def test_failure_still_archives_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            with mock.patch.object(job, "RESULTS", base/"results"), \
                 mock.patch.object(job, "ARCHIVE", base/"results.zip"), \
                 mock.patch.object(job, "gpu_preflight", return_value="Test GPU"), \
                 mock.patch.object(job, "dependencies", return_value=None), \
                 mock.patch.object(job, "checkout", return_value="a"*40), \
                 mock.patch.object(job, "execute_benchmark", side_effect=RuntimeError("simulated failure")):
                with redirect_stdout(io.StringIO()):
                    status = job.main(["--models", "small", "--git-commit", "a"*40])
                self.assertEqual(status, 1)
                self.assertTrue((base/"results.zip").is_file())
                with zipfile.ZipFile(base/"results.zip") as z:
                    self.assertIn("colab_run.json", z.namelist())
                    self.assertIn("error.txt", z.namelist())


if __name__ == "__main__":
    unittest.main()
