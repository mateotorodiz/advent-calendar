import argparse
from pathlib import Path

from advent_tools.gifts import PackageError, package_gifts


def main():
    parser = argparse.ArgumentParser(description="Validate gifts and build the calendar's private assets.")
    parser.add_argument("mode", choices=("demo", "production"))
    args = parser.parse_args()

    project = Path.cwd().resolve()
    try:
        output = package_gifts(args.mode, project)
    except (PackageError, OSError) as error:
        parser.exit(2, f"Gift packaging failed: {error}\n")
    print(f"Packaged {args.mode} gifts in {output.relative_to(project)}")


if __name__ == "__main__":
    main()
