# Finds and prints the newest file (not directory) with path
# recursively starting at current directory

from pathlib import Path
import time


def has_hidden_component(file: Path) -> bool:
    return any(part.startswith('.') for part in file.parts)


def get_newest_file(d: str) -> tuple[Path, str] | None:
    candidates = [
        x for x in Path(d).rglob('*')
        if x.is_file() and not has_hidden_component(x)
    ]
    if not candidates:
        return None
    newest = max(candidates, key=lambda x: x.stat().st_mtime)
    dt = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(newest.stat().st_mtime))
    return newest, dt


def main() -> None:
    result = get_newest_file('.')
    if result:
        file, dt = result
        print(file, dt)
    else:
        print("No files found.")


if __name__ == '__main__':
    main()
