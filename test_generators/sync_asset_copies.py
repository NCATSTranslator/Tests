"""Copy edits to test assets into the copies the suites carry.

A suite, and each test case file, carries its own copy of every test asset it
uses, and the copy is what the Test Harness runs. Edit an asset in
test_assets/ (or pathfinder_test_assets/), eg to fix a CURIE or to set
``skip``, then run this to bring every copy of it up to date:

    python test_generators/sync_asset_copies.py           # update the copies
    python test_generators/sync_asset_copies.py --check   # report only; exit 1 if any is out of date

The copies are in test_suites/ (not test_suites/deprecated/), test_cases/
and pathfinder_test_cases/. Only copies that differ from their asset are
rewritten, in place: the rest of each file, test case ids included, stays as
it is. Regenerating a suite instead renumbers its test cases, which breaks
each asset's history in the Information Radiator.

Test cases themselves (eg skipping a whole test case) are edited in the suite:
test_cases/ is from an older generation of the suites and doesn't match their
test case ids.
"""

import argparse
import glob
import json
import os
import re
import sys
from json.decoder import scanstring
from typing import Dict, List, Tuple

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# where each kind of asset lives, and where its copies are
SOURCES = {"acceptance": "test_assets", "pathfinder": "pathfinder_test_assets"}
COPIES = ["test_suites", "test_cases", "pathfinder_test_cases"]

WS = re.compile(r"[ \t\r\n]*")
NUMBER = re.compile(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][-+]?\d+)?")


def read(path: str) -> str:
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def relative_path(path: str) -> str:
    return os.path.relpath(path, REPO).replace(os.sep, "/")


def kind_of(asset: dict) -> str:
    return "pathfinder" if "source_input_id" in asset else "acceptance"


def asset_copies(text: str) -> Tuple[object, List[Tuple[int, int, dict]]]:
    """Parse a JSON document, and find where each object in a "test_assets"
    array is in the text: (start, end, the object)."""
    copies = []

    def value(i, in_assets=False):
        i = WS.match(text, i).end()
        c = text[i]
        if c == "{":
            start, obj = i, {}
            i = WS.match(text, i + 1).end()
            if text[i] == "}":
                i += 1
            else:
                while True:
                    key, i = scanstring(text, WS.match(text, i).end() + 1)
                    i = WS.match(text, i).end() + 1  # past the colon
                    obj[key], i = value(i, key == "test_assets")
                    i = WS.match(text, i).end()
                    if text[i] == "}":
                        i += 1
                        break
                    i += 1  # past the comma
            if in_assets:
                copies.append((start, i, obj))
            return obj, i
        if c == "[":
            items = []
            i = WS.match(text, i + 1).end()
            if text[i] == "]":
                return items, i + 1
            while True:
                item, i = value(i, in_assets)
                items.append(item)
                i = WS.match(text, i).end()
                if text[i] == "]":
                    return items, i + 1
                i += 1  # past the comma
        if c == '"':
            return scanstring(text, i + 1)
        for literal, v in (("true", True), ("false", False), ("null", None)):
            if text.startswith(literal, i):
                return v, i + len(literal)
        number = NUMBER.match(text, i)
        if number is None:
            raise ValueError(f"unexpected {c!r} at character {i}")
        return json.loads(number.group()), number.end()

    document, _ = value(0)
    return document, copies


def indented(source: str, indent: str, newline: str) -> str:
    """An asset file's text, indented to sit where its copy is."""
    lines = source.replace("\r\n", "\n").rstrip("\n").split("\n")
    return newline.join([lines[0]] + [indent + line for line in lines[1:]])


def load_sources() -> Dict[Tuple[str, str], Tuple[str, dict]]:
    sources = {}
    for kind, folder in SOURCES.items():
        for path in glob.glob(os.path.join(REPO, folder, "*.json")):
            text = read(path)
            asset = json.loads(text)
            sources[(kind, asset["id"])] = (text, asset)
    return sources


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="report out-of-date copies and change nothing; exit 1 if there are any",
    )
    args = parser.parse_args()

    sources = load_sources()
    out_of_date = []  # (file, asset id)
    no_source = []
    for folder in COPIES:
        for path in sorted(glob.glob(os.path.join(REPO, folder, "*.json"))):
            text = read(path)
            relative = relative_path(path)
            try:
                document, copies = asset_copies(text)
            except (ValueError, IndexError) as e:
                print(f"error: can't read {relative}: {e}", file=sys.stderr)
                return 1
            newline = "\r\n" if "\r\n" in text else "\n"
            edits = []
            for start, end, copy in copies:
                source = sources.get((kind_of(copy), copy.get("id")))
                if source is None:
                    no_source.append((relative, copy.get("id")))
                    continue
                source_text, asset = source
                if asset == copy:
                    continue
                out_of_date.append((relative, copy.get("id")))
                indent = text[text.rfind("\n", 0, start) + 1 : start]
                edits.append((start, end, indented(source_text, indent, newline), asset))
            if not edits or args.check:
                continue
            # from the end, so the earlier positions still hold
            for start, end, replacement, asset in sorted(edits, reverse=True):
                text = text[:start] + replacement + text[end:]
            if json.loads(text) == json.loads(read(path)):
                print(f"error: updating {relative} changed nothing", file=sys.stderr)
                return 1
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(text)

    for relative, asset_id in no_source:
        print(f"note: {relative} has {asset_id}, which has no asset file; left as is")
    if not out_of_date:
        print("Every copy matches its asset.")
        return 0
    files = sorted({relative for relative, _ in out_of_date})
    verb = "Out of date" if args.check else "Updated"
    print(f"{verb}: {len(out_of_date)} copies, in {len(files)} files:")
    for relative in files:
        ids = [asset_id for r, asset_id in out_of_date if r == relative]
        print(f"  {relative}: {', '.join(ids)}")
    return 1 if args.check else 0


if __name__ == "__main__":
    sys.exit(main())
