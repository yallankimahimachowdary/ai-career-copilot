"""Unit tests for R9-7: Checkpoint Tooling on a Scratch Git Repository."""

from pathlib import Path
import subprocess
import pytest

from scripts.create_checkpoint import check_git_clean, create_checkpoint


@pytest.fixture
def scratch_git_repo(tmp_path: Path):
    """Set up an isolated, temporary git repository for testing."""
    repo_dir = tmp_path / "scratch_repo"
    repo_dir.mkdir()

    # Initialize git
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "TestUser"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo_dir), check=True, capture_output=True)

    # Create dummy asset files
    asset1 = repo_dir / "config.json"
    asset1.write_text('{"weights": {"bm25": 0.25}}', encoding="utf-8")
    asset2 = repo_dir / "eval_data.json"
    asset2.write_text('{"benchmark": "v1"}', encoding="utf-8")

    # Initial commit
    subprocess.run(["git", "add", "."], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(repo_dir), check=True, capture_output=True)

    return repo_dir


def test_checkpoint_refuses_when_dirty(scratch_git_repo: Path):
    """Checkpointing must refuse if the working tree has uncommitted modifications."""
    # Create an uncommitted change
    dirty_file = scratch_git_repo / "dirty_file.txt"
    dirty_file.write_text("uncommitted work", encoding="utf-8")

    is_clean, _ = check_git_clean(scratch_git_repo)
    assert not is_clean

    with pytest.raises(RuntimeError, match="Checkpoint refused: working tree.*is dirty"):
        create_checkpoint(
            tag_name="checkpoint-fail",
            asset_paths=["config.json"],
            repo_dir=scratch_git_repo,
        )


def test_checkpoint_succeeds_when_clean(scratch_git_repo: Path):
    """Checkpointing must compute hashes, write manifest, and create local git tag when clean."""
    is_clean, _ = check_git_clean(scratch_git_repo)
    assert is_clean

    res = create_checkpoint(
        tag_name="checkpoint-a",
        asset_paths=["config.json", "eval_data.json"],
        repo_dir=scratch_git_repo,
    )

    assert res["tag"] == "checkpoint-a"
    assert "config.json" in res["manifest"]["assets_sha256"]
    assert "eval_data.json" in res["manifest"]["assets_sha256"]
    assert Path(res["manifest_file"]).exists()

    # Verify git tag exists in scratch repo
    tag_proc = subprocess.run(
        ["git", "tag", "-l", "checkpoint-a"],
        cwd=str(scratch_git_repo),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "checkpoint-a" in tag_proc.stdout.strip()
