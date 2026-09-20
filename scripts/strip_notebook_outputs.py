import json
import sys
from pathlib import Path


def strip_notebook(path: Path) -> bool:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    changed = False

    for cell in notebook.get("cells", []):
        if cell.get("cell_type") != "code":
            continue

        if cell.get("outputs"):
            cell["outputs"] = []
            changed = True

        if cell.get("execution_count") is not None:
            cell["execution_count"] = None
            changed = True

        metadata = cell.get("metadata", {})
        for key in ("execution", "ExecuteTime"):
            if key in metadata:
                metadata.pop(key, None)
                changed = True

    if changed:
        path.write_text(
            json.dumps(notebook, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8",
        )

    return changed


def main() -> int:
    changed_paths = []

    for arg in sys.argv[1:]:
        path = Path(arg)
        if path.suffix == ".ipynb" and path.exists():
            if strip_notebook(path):
                changed_paths.append(str(path))

    if changed_paths:
        print("Stripped notebook outputs:")
        for path in changed_paths:
            print(f"  {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
