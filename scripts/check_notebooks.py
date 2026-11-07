"""Verify research notebook JSON and Python syntax without executing video models."""
from pathlib import Path
import nbformat
from IPython.core.interactiveshell import InteractiveShell


def main():
    files = sorted(Path("notebooks").glob("*.ipynb"))
    if len(files) != 3:
        raise RuntimeError(f"Expected 3 notebooks, found {len(files)}")
    shell = InteractiveShell.instance()
    total = 0
    failed = []
    for filename in files:
        nb = nbformat.read(filename, as_version=4)
        nbformat.validate(nb)
        passed = 0
        for index, cell in enumerate(nb.cells, 1):
            if cell.cell_type != "code" or not cell.source.strip():
                continue
            try:
                source = shell.input_transformer_manager.transform_cell(cell.source)
                compile(source, f"{filename}::cell{index}", "exec")
                passed += 1
            except Exception as exc:
                failed.append(f"{filename}: cell {index}: {exc}")
        total += passed
        print(f"{filename}: {passed} code cells checked")
    if failed:
        raise RuntimeError("\n".join(failed))
    print(f"Syntax OK: {len(files)} notebooks, {total} code cells")


if __name__ == "__main__":
    main()
