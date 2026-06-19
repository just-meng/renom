"""Tests for rename-tool."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def run_rename(args):
    """Run rename as a console script."""
    cmd = [sys.executable, "-m", "rename_tool"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 and result.stderr:
        print(f"stderr: {result.stderr}")
    return result.returncode, result.stdout, result.stderr


def test_add_prefix():
    """123456A -> sub-123456A"""
    with tempfile.TemporaryDirectory() as tmpdir:
        old_dir = Path(tmpdir) / "123456A"
        old_dir.mkdir()
        rc, _, _ = run_rename([str(old_dir), "sub-", ""])
        assert rc == 0
        assert (Path(tmpdir) / "sub-123456A").exists()
        assert not old_dir.exists()


def test_add_suffix():
    """123456A -> 123456A_Sim-Cre"""
    with tempfile.TemporaryDirectory() as tmpdir:
        old_dir = Path(tmpdir) / "123456A"
        old_dir.mkdir()
        rc, _, _ = run_rename([str(old_dir), "", "_Sim-Cre"])
        assert rc == 0
        assert (Path(tmpdir) / "123456A_Sim-Cre").exists()
        assert not old_dir.exists()


def test_remove():
    """123456A_Sim-Cre -> 123456A"""
    with tempfile.TemporaryDirectory() as tmpdir:
        old_dir = Path(tmpdir) / "123456A_Sim-Cre"
        old_dir.mkdir()
        rc, _, _ = run_rename([str(old_dir), "_Sim-Cre", ""])
        assert rc == 0
        assert (Path(tmpdir) / "123456A").exists()
        assert not old_dir.exists()


def test_replace():
    """sub-123456A -> sub-125436A"""
    with tempfile.TemporaryDirectory() as tmpdir:
        old_dir = Path(tmpdir) / "sub-123456A"
        old_dir.mkdir()
        rc, _, _ = run_rename([str(old_dir), "345", "543"])
        assert rc == 0
        assert (Path(tmpdir) / "sub-125436A").exists()
        assert not old_dir.exists()


def test_multiple_inputs():
    with tempfile.TemporaryDirectory() as tmpdir:
        dir1 = Path(tmpdir) / "123456A"
        dir2 = Path(tmpdir) / "123456B"
        dir1.mkdir()
        dir2.mkdir()
        rc, _, _ = run_rename([str(dir1), str(dir2), "sub-", ""])
        assert rc == 0
        remaining = os.listdir(tmpdir)
        assert "sub-123456A" in remaining
        assert "sub-123456B" in remaining


def test_add_number():
    """_T1 -> _T38 (offset +37)"""
    with tempfile.TemporaryDirectory() as tmpdir:
        files = [
            "2024-05-06_1545_right_T1.mp4",
            "2024-05-06_1545_right_T2.mp4",
            "2024-05-06_1545_right_T38.mp4",
            "2024-05-06_1545_right_T39.mp4",
        ]
        for f in files:
            (Path(tmpdir) / f).touch()
        rc, _, _ = run_rename(
            [*[str(Path(tmpdir) / f) for f in files], "_T", "+37"]
        )
        assert rc == 0
        remaining = os.listdir(tmpdir)
        assert "2024-05-06_1545_right_T38.mp4" in remaining
        assert "2024-05-06_1545_right_T39.mp4" in remaining
        assert "2024-05-06_1545_right_T75.mp4" in remaining
        assert "2024-05-06_1545_right_T76.mp4" in remaining


def test_full_replace():
    """ses-pre_LSD-0.4 -> ses-pre"""
    with tempfile.TemporaryDirectory() as tmpdir:
        old_dir = Path(tmpdir) / "ses-pre_LSD-0.4"
        old_dir.mkdir()
        rc, _, _ = run_rename([str(old_dir), "*", "ses-pre"])
        assert rc == 0
        assert (Path(tmpdir) / "ses-pre").exists()
        assert not old_dir.exists()


def test_regex():
    """exp-2024-04-29_Saline -> exp-Saline"""
    with tempfile.TemporaryDirectory() as tmpdir:
        old_dir = Path(tmpdir) / "exp-2024-04-29_Saline"
        old_dir.mkdir()
        rc, _, _ = run_rename([str(old_dir), r"\d{4}-\d{2}-\d{2}_", ""])
        assert rc == 0
        assert (Path(tmpdir) / "exp-Saline").exists()
        assert not old_dir.exists()


def test_path_mode_cross_tree_move():
    """Backfill snr.npy from 02_roi2cell/.../cells/ -> 01_suite2p/...,
    preserving sub/exp/plane and creating the (non-existent) destination tree.

    02_roi2cell/sub-240226O/exp-LSD/plane0/cells/snr.npy
      -> 01_suite2p/sub-240226O/exp-LSD/plane0/snr.npy
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        subjects = [
            ("sub-240226O", "exp-LSD"),
            ("sub-240222M", "exp-Ketam"),
        ]
        for sub, exp in subjects:
            src_cells = root / "02_roi2cell" / sub / exp / "plane0" / "cells"
            src_cells.mkdir(parents=True)
            (src_cells / "snr.npy").write_text(f"{sub}-{exp}")  # unique content
            # sibling files that must NOT move
            (src_cells / "iscell.npy").touch()

        # run on absolute input paths; the regex matches the substring within them
        inputs = [
            str(root / "02_roi2cell" / sub / exp / "plane0" / "cells" / "snr.npy")
            for sub, exp in subjects
        ]
        rc, out, err = run_rename(
            [*inputs, "02_roi2cell/(.*)/cells/snr.npy", r"01_suite2p/\1/snr.npy"]
        )
        assert rc == 0, err

        for sub, exp in subjects:
            moved = root / "01_suite2p" / sub / exp / "plane0" / "snr.npy"
            src = root / "02_roi2cell" / sub / exp / "plane0" / "cells" / "snr.npy"
            assert moved.exists(), f"{moved} should exist"
            assert moved.read_text() == f"{sub}-{exp}"  # content preserved, right file
            assert not src.exists(), f"{src} should be gone"
            # sibling left untouched
            assert (root / "02_roi2cell" / sub / exp / "plane0" / "cells" / "iscell.npy").exists()


def test_path_mode_delete_segment():
    """A plain (non-regex) arg1 with '/' deletes a path segment, in place.

    .../plane0/cells/snr.npy -> .../plane0/snr.npy
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        cells = root / "plane0" / "cells"
        cells.mkdir(parents=True)
        (cells / "snr.npy").touch()
        rc, _, err = run_rename([str(cells / "snr.npy"), "cells/", ""])
        assert rc == 0, err
        assert (root / "plane0" / "snr.npy").exists()
        assert not (cells / "snr.npy").exists()
