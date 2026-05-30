from pathlib import Path

from prism.transcripts import write_transcript


def test_writes_raw_to_labelled_file(tmp_path: Path) -> None:
    write_transcript(tmp_path, "code_quality", '{"type":"assistant"}\n')
    assert (tmp_path / "code_quality.jsonl").read_text() == '{"type":"assistant"}\n'


def test_appends_successive_invocations(tmp_path: Path) -> None:
    write_transcript(tmp_path, "coordinator", "first\n")
    write_transcript(tmp_path, "coordinator", "second\n")
    assert (tmp_path / "coordinator.jsonl").read_text() == "first\nsecond\n"


def test_empty_raw_writes_nothing(tmp_path: Path) -> None:
    write_transcript(tmp_path, "security", "")
    assert not (tmp_path / "security.jsonl").exists()


def test_none_dir_is_noop(tmp_path: Path) -> None:
    write_transcript(None, "security", "data\n")  # disabled -> no error, nothing written
    assert list(tmp_path.iterdir()) == []


def test_fire_and_forget_never_raises(tmp_path: Path) -> None:
    blocker = tmp_path / "afile"
    blocker.write_text("x")  # a regular file used as the run dir -> writes must fail
    write_transcript(blocker, "security", "data\n")  # must not raise
