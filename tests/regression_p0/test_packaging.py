"""J: bounded static regression for the current single-stage Dockerfile.

This checks COPY source/layout coverage, not an actual Docker build or runtime.
"""
import json
from pathlib import Path, PurePosixPath
import shlex


def test_docker_copy_includes_frontend_at_application_runtime_path():
    from app.main import FRONTEND_DIR
    repo = Path(__file__).resolve().parents[2]
    dockerfile = (repo / "Dockerfile").read_text(encoding="utf-8")
    workdir = PurePosixPath("/")
    copied = set()
    stages = 0
    for raw in dockerfile.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        instruction, _, arguments = line.partition(" ")
        instruction = instruction.upper()
        if instruction == "FROM":
            stages += 1
        elif instruction == "WORKDIR":
            workdir = workdir / arguments.strip()
        elif instruction == "COPY":
            parts = json.loads(arguments) if arguments.startswith("[") else shlex.split(arguments)
            assert not any(p.startswith("--") for p in parts), "extend static check for COPY flags"
            destination = workdir / parts[-1]
            for source in parts[:-1]:
                source_path = repo / source
                if source_path.is_dir():
                    copied.update(destination / p.relative_to(source_path).as_posix()
                                  for p in source_path.rglob("*") if p.is_file())
                else:
                    copied.add(destination / source_path.name)
    assert stages == 1, "extend static check if Docker becomes multi-stage"
    # Derive the expected path from the app's actual FRONTEND_DIR and the image
    # layout, not from an arbitrary desired COPY spelling.
    expected = PurePosixPath("/app") / FRONTEND_DIR.relative_to(repo).as_posix() / "index.html"
    assert (FRONTEND_DIR / "index.html").is_file()
    assert expected in copied, f"Docker COPY layout omits required runtime file: {expected}"
