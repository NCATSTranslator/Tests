"""Convert the Tests repo for translator-testing-model 0.6.0.

Three changes, all made in place. The files are edited as text, so nothing
else in them changes:

1. Every test asset's ``"output_id": "X"`` becomes ``"output_ids": ["X"]``
   (``null`` becomes ``[]``), wherever the asset appears: test_assets/, and
   the copies inside test_cases/ and test_suites/. Some expected outputs also
   get alternative CURIEs (``--alias``; sirolimus's ChEBI id by default), so
   the answer counts under either identifier now that node normalization keeps
   them apart. Expected outputs that aren't real CURIEs (eg
   ``"PUBCHEM.COMPOUND:"``) are kept as they are and flagged in the report.

2. ``test_env`` is removed from every test case. Suites are the same in every
   environment; the Test Harness is told which one to test (``--env``).

3. The suites are consolidated: one suite per kind, run in every environment.
   ``sprint_6_tests`` becomes ``mvp_tests``; ``pathfinder_tests`` and
   ``performance_tests`` keep their names; every other suite, including the
   old per-environment copies, moves to test_suites/deprecated/.

Files are read and written as UTF-8 with their line endings untouched, so
the result is the same on every OS. Run it from anywhere; it is idempotent:

    python test_generators/migrate_to_testing_model_0_6.py --dry-run   # report only
    python test_generators/migrate_to_testing_model_0_6.py --check     # convert, then validate

``--check`` validates every file against the installed translator-testing-model,
which must be 0.6.0 or later. Afterwards, ``git add -A`` picks up the moves.
"""

import argparse
import glob
import json
import os
import re
import sys
from collections import defaultdict
from typing import Dict, List

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUITES = os.path.join(REPO, "test_suites")
DEPRECATED = os.path.join(SUITES, "deprecated")

# expected output -> CURIEs to accept alongside it
DEFAULT_ALIASES = {
    # sirolimus
    "PUBCHEM.COMPOUND:5284616": ["CHEBI:9168"],
}

# the suite each kind is now, and the suite it's made from
SHARED_SUITES = {
    "mvp_tests": ("sprint_6_tests", "MVP tests"),
    "pathfinder_tests": ("pathfinder_tests", None),
    "performance_tests": ("performance_tests", None),
}

OUTPUT_ID = re.compile(r'"output_id"(\s*):(\s*)(null|"((?:[^"\\]|\\.)*)")')
ENV_VALUE = r'(?:null|"[^"]*")'
# test_env as an object's last member (take the comma before it), or not
TEST_ENV_LAST = re.compile(r',(\s*)"test_env"\s*:\s*' + ENV_VALUE + r'(?=\s*\})')
TEST_ENV = re.compile(r'"test_env"\s*:\s*' + ENV_VALUE + r'\s*,\s*')
CURIE = re.compile(r"^[A-Za-z][\w.\-]*:\S+$")

# which model class each directory's files are
KINDS = {
    "test_suites": "TestSuite",
    "test_suites/deprecated": "TestSuite",
    "test_cases": "TestCase",
    "test_assets": "TestAsset",
    "pathfinder_test_cases": "PathfinderTestCase",
    "pathfinder_test_assets": "PathfinderTestAsset",
}
# invalid before this migration, for reasons unrelated to it
ALREADY_INVALID = {
    "test_suites/deprecated/DrugCentral_subset.json",
    "test_cases/TestCase_87.json",
}


def output_ids(value: str, aliases: Dict[str, List[str]]) -> List[str]:
    curies = [value]
    for alias in aliases.get(value, []):
        if alias not in curies:
            curies.append(alias)
    return curies


def convert_output_ids(text: str, aliases: Dict[str, List[str]]) -> str:
    def replace(match):
        value = None if match[3] == "null" else json.loads(match[3])
        curies = [] if value is None else output_ids(value, aliases)
        return f'"output_ids"{match[1]}:{match[2]}{json.dumps(curies)}'

    return OUTPUT_ID.sub(replace, text)


def remove_test_env(text: str) -> str:
    text = TEST_ENV_LAST.sub("", text)
    # keep the indentation of the member that followed it
    return TEST_ENV.sub("", text)


def assets_in(node):
    """Every test asset (any dict with output_id or output_ids) in a document."""
    if isinstance(node, dict):
        if "output_id" in node or "output_ids" in node:
            yield node
        for value in node.values():
            yield from assets_in(value)
    elif isinstance(node, list):
        for value in node:
            yield from assets_in(value)


def flag_curies(asset) -> List[str]:
    """The asset's expected outputs that aren't real CURIEs."""
    if "output_ids" in asset:
        values = asset["output_ids"] or []
    else:
        values = [asset["output_id"]] if asset["output_id"] is not None else []
    return [value for value in values if not CURIE.match(value)]


def consolidate_suites(dry_run: bool) -> List[str]:
    """Make the shared suites and move the rest to deprecated/; say what moved."""
    done = []
    for suite, (source, description) in SHARED_SUITES.items():
        target = os.path.join(SUITES, f"{suite}.json")
        if suite == source or os.path.exists(target):
            continue
        source_path = os.path.join(SUITES, f"{source}.json")
        with open(source_path, encoding="utf-8", newline="") as f:
            text = f.read()
        # the suite's own id, name and descriptions; its test cases keep theirs
        document = json.loads(text)
        renames = {
            f'"id": {json.dumps(document["id"])}': f'"id": {json.dumps(suite)}',
            f'"name": {json.dumps(document["name"])}': f'"name": {json.dumps(suite)}',
        }
        old_description = document.get("description")
        if old_description:
            renames[f'"description": {json.dumps(old_description)}'] = (
                f'"description": {json.dumps(description)}'
            )
        head, sep, tail = text.partition('"test_cases"')
        for old, new in renames.items():
            head = head.replace(old, new)
        done.append(f"test_suites/{source}.json -> test_suites/{suite}.json")
        if not dry_run:
            with open(target, "w", encoding="utf-8", newline="") as f:
                f.write(head + sep + tail)
    keep = set(SHARED_SUITES)
    for path in sorted(glob.glob(os.path.join(SUITES, "*.json"))):
        name = os.path.splitext(os.path.basename(path))[0]
        if name in keep:
            continue
        done.append(f"test_suites/{name}.json -> test_suites/deprecated/")
        if not dry_run:
            os.makedirs(DEPRECATED, exist_ok=True)
            os.rename(path, os.path.join(DEPRECATED, os.path.basename(path)))
    return done


def relative_path(path: str) -> str:
    """``path`` relative to the repo, with forward slashes on every OS."""
    return os.path.relpath(path, REPO).replace(os.sep, "/")


def check(paths: List[str]) -> int:
    """Validate the files against the installed model; return the new failures."""
    try:
        from translator_testing_model.datamodel import pydanticmodel as model
    except ImportError:
        print("\n--check: translator-testing-model isn't installed", file=sys.stderr)
        return 1
    if (
        "output_ids" not in model.TestAsset.model_fields
        or "test_env" in model.TestCase.model_fields
    ):
        print(
            "\n--check: the installed translator-testing-model predates 0.6.0; "
            "install 0.6.0 or later",
            file=sys.stderr,
        )
        return 1
    failures = 0
    print("\nValidating against translator-testing-model:")
    for directory, class_name in KINDS.items():
        cls = getattr(model, class_name)
        files = [
            p for p in paths if os.path.dirname(relative_path(p)) == directory
        ]
        new, old = [], []
        for path in files:
            relative = relative_path(path)
            try:
                with open(path, encoding="utf-8", newline="") as f:
                    cls.model_validate(json.load(f))
            except Exception as e:
                (old if relative in ALREADY_INVALID else new).append((relative, e))
        print(f"  {directory}: {len(files)} files, {len(new)} invalid", end="")
        print(f" (+{len(old)} invalid before this migration)" if old else "")
        for relative, e in new:
            print(f"    {relative}: {str(e).splitlines()[0]}")
        failures += len(new)
    return failures


def json_files() -> List[str]:
    return sorted(
        p
        for p in glob.glob(os.path.join(REPO, "**", "*.json"), recursive=True)
        if os.sep + ".git" + os.sep not in p
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="report, change nothing")
    parser.add_argument(
        "--check", action="store_true", help="validate every file afterwards"
    )
    parser.add_argument(
        "--alias",
        action="append",
        default=[],
        metavar="CURIE=ALT[,ALT]",
        help="also accept ALT wherever CURIE is the expected output (repeatable)",
    )
    parser.add_argument(
        "--no-default-aliases",
        action="store_true",
        help=f"don't add the built-in aliases ({', '.join(DEFAULT_ALIASES)})",
    )
    args = parser.parse_args()

    aliases = (
        {}
        if args.no_default_aliases
        else {k: list(v) for k, v in DEFAULT_ALIASES.items()}
    )
    for alias in args.alias:
        curie, _, alts = alias.partition("=")
        if not curie or not alts:
            parser.error(f"--alias {alias!r} isn't CURIE=ALT[,ALT]")
        aliases.setdefault(curie.strip(), []).extend(
            alt.strip() for alt in alts.split(",") if alt.strip()
        )

    changed_files = 0
    converted = 0
    envs_removed = 0
    aliased = defaultdict(int)
    flagged = {}
    leftover_env = []
    for path in json_files():
        with open(path, encoding="utf-8", newline="") as f:
            text = f.read()
        relative = relative_path(path)
        matches = OUTPUT_ID.findall(text)
        new_text = convert_output_ids(text, aliases)
        for _, _, raw, _ in matches:
            if raw != "null" and json.loads(raw) in aliases:
                aliased[json.loads(raw)] += 1
        envs = text.count('"test_env"')
        new_text = remove_test_env(new_text)
        if '"test_env"' in new_text:
            leftover_env.append(relative)
        envs_removed += envs - new_text.count('"test_env"')
        try:
            document = json.loads(new_text)
        except ValueError:
            document = None
            if new_text != text:
                print(f"error: {relative} wouldn't be valid JSON; left as is")
                continue
        for asset in assets_in(document):
            bad = flag_curies(asset)
            if bad and relative.startswith("test_assets/"):
                flagged[asset.get("id")] = (relative, asset.get("name"), bad)
        if new_text != text:
            changed_files += 1
            converted += len(matches)
            if not args.dry_run:
                with open(path, "w", encoding="utf-8", newline="") as f:
                    f.write(new_text)

    verb = "Would change" if args.dry_run else "Changed"
    print(f"{verb} {changed_files} files:")
    print(f"  {converted} output_id fields to output_ids")
    for curie, count in aliased.items():
        print(f"    {curie} also accepts {', '.join(aliases[curie])} ({count} places)")
    print(f"  {envs_removed} test_env fields removed")
    for relative in leftover_env:
        print(f"    error: couldn't remove test_env from {relative}")

    moves = consolidate_suites(args.dry_run)
    if moves:
        print(f"\n{'Would move' if args.dry_run else 'Moved'} suites:")
        for move in moves:
            print(f"  {move}")

    if flagged:
        print(
            f"\nFlagged: {len(flagged)} test assets whose expected output isn't a "
            "real CURIE. They can never match, so NeverShow/BadButForgivable ones "
            "pass without testing anything. Fix them in test_assets/, then "
            "regenerate or patch their copies in test_cases/ and test_suites/:"
        )
        for asset_id, (relative, name, bad) in sorted(
            flagged.items(), key=lambda item: int(re.sub(r"\D", "", item[0]) or 0)
        ):
            print(f"  {asset_id}: {name}  [{', '.join(map(repr, bad))}]  {relative}")

    if args.check and not args.dry_run:
        sys.exit(1 if check(json_files()) or leftover_env else 0)


if __name__ == "__main__":
    main()
