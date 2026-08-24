from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_FILE = PROJECT_ROOT / "MetalSense_Project_Export.txt"

INCLUDE_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".json",
    ".sql",
    ".yaml",
    ".yml",
    ".md",
    ".txt",
    ".html",
    ".css",
    ".scss",
    ".xml",
    ".toml",
    ".ini",
    ".properties",
}

EXCLUDE_DIRS = {
    "node_modules",
    ".git",
    ".next",
    "dist",
    "build",
    "coverage",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".idea",
    ".vscode",
}

EXCLUDE_FILES = {
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    "MetalSense_Project_Export.txt",
    "export_project.py",
}

MAX_FILE_SIZE = 2 * 1024 * 1024


def should_include(path):
    if path.name in EXCLUDE_FILES:
        return False

    if path.suffix.lower() not in INCLUDE_EXTENSIONS:
        return False

    try:
        if path.stat().st_size > MAX_FILE_SIZE:
            return False
    except OSError:
        return False

    return True


def collect_files():
    files = []

    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file():
            continue

        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue

        if should_include(path):
            files.append(path)

    return sorted(files, key=lambda p: str(p).lower())


def build_tree():
    lines = []
    lines.append("METALSENSE PROJECT STRUCTURE")
    lines.append("=" * 80)
    lines.append("")

    def walk(directory, prefix=""):
        entries = []

        for item in sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
            if item.name in EXCLUDE_DIRS:
                continue

            if item.is_file() and not should_include(item):
                continue

            entries.append(item)

        for index, item in enumerate(entries):
            last = index == len(entries) - 1
            branch = "└── " if last else "├── "
            lines.append(prefix + branch + item.name)

            if item.is_dir():
                extension = "    " if last else "│   "
                walk(item, prefix + extension)

    lines.append(PROJECT_ROOT.name)
    walk(PROJECT_ROOT)

    return "\n".join(lines)


def read_file(path):
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="utf-8-sig")
        except Exception:
            return "[Unable to decode this file]"
    except Exception as error:
        return f"[Unable to read file: {error}]"


def main():
    files = collect_files()

    with OUTPUT_FILE.open("w", encoding="utf-8") as output:
        output.write(build_tree())
        output.write("\n\n")
        output.write("=" * 80)
        output.write("\nPROJECT SOURCE FILES\n")
        output.write("=" * 80)
        output.write("\n\n")

        for path in files:
            relative_path = path.relative_to(PROJECT_ROOT)

            output.write("\n")
            output.write("=" * 80)
            output.write("\n")
            output.write(f"FILE: {relative_path}\n")
            output.write("=" * 80)
            output.write("\n\n")

            output.write(read_file(path))
            output.write("\n\n")

    print()
    print("MetalSense project export completed.")
    print()
    print(f"Project: {PROJECT_ROOT}")
    print(f"Files exported: {len(files)}")
    print(f"Output: {OUTPUT_FILE}")
    print()


if __name__ == "__main__":
    main()