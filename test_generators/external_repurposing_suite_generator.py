#!/usr/bin/env python3
"""Generate the External Repurposing test suite from its source spreadsheet.

The spreadsheet (external_repurposing_test_assets/source/) lists drug
repurposing outcomes reported outside Translator, with where each came from:

- sheet MVP1: disease, drug (drug treats disease)
- sheet MVP2: gene or chemical, direction, the other one (chemical increases
  or decreases the activity or abundance of a gene)

Every row becomes an ``Acceptable`` test asset whose test_metadata keeps its
provenance: test_source ``ExternalRepurposing``, test_reference the first link
in the row's source, and the source text, sheet and row as test_annotations.
Rows whose data looks doubtful are flagged with test_issue ``questionable``
and a ``questionable_reason`` annotation; they still run.

    python -m test_generators.external_repurposing_suite_generator

writes external_repurposing_test_assets/*.json and
test_suites/external_repurposing_tests.json. An asset already generated for
the same statement keeps its id, so the Information Radiator keeps its
history; the suite's test case ids are renumbered, as for the other suites.

Needs translator-testing-model 0.8.0 (ExternalRepurposing, questionable) and
openpyxl.
"""
import glob
import json
import os
import re
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import openpyxl
from translator_testing_model.datamodel.pydanticmodel import (
    TestAsset,
    TestMetadata,
    TestObjectiveEnum,
    TestPersonaEnum,
    TestSourceEnum,
    TestSuite,
)

from test_generators.utils import create_test_cases_from_test_assets

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET_DIR = os.path.join(REPO, "external_repurposing_test_assets")
SPREADSHEET = os.path.join(ASSET_DIR, "source", "SmartQueryTestCaseProposals.xlsx")
SUITE_DIR = os.path.join(REPO, "test_suites")
SUITE_ID = "external_repurposing_tests"
ID_PREFIX = "ExternalRepurposing_Asset_"

# CURIE prefixes the Translator normalizers know, as Biolink spells them
PREFIXES = {
    "MONDO", "HP", "CHEBI", "UNII", "UMLS", "NCBIGene", "PUBCHEM.COMPOUND",
    "DRUGBANK", "CHEMBL.COMPOUND", "RXCUI", "MESH",
}
# spreadsheet spellings of a known prefix
PREFIX_SPELLINGS = {"NCBIGENE": "NCBIGene"}

# Rows a person flagged on review, by (input name, output name, direction):
# what's doubtful isn't something the checks below can see.
REVIEWED = {
    ("MET", "etoposide", "Increase"): "cited DOIs run 10.1111/cts.70284 to cts.70288 down the MET rows; looks like a spreadsheet fill, check the reference",
    ("MET", "hydroxyurea", "Increase"): "cited DOIs run 10.1111/cts.70284 to cts.70288 down the MET rows; looks like a spreadsheet fill, check the reference",
    ("MET", "methotrexate", "Increase"): "cited DOIs run 10.1111/cts.70284 to cts.70288 down the MET rows; looks like a spreadsheet fill, check the reference",
    ("MET", "tretinoin", "Increase"): "cited DOIs run 10.1111/cts.70284 to cts.70288 down the MET rows; looks like a spreadsheet fill, check the reference",
    ("MET", "prednisolone", "Increase"): "cited DOIs run 10.1111/cts.70284 to cts.70288 down the MET rows; looks like a spreadsheet fill, check the reference",
    **{
        ("KIF2A", drug, "Decrease"): "cites 10.1111/cts.70288, the vascular Ehlers-Danlos celiprolol paper; check the reference"
        for drug in [
            "acetylsalicylic acid (aspirin)", "amantadine", "quercetin",
            "Spermidine", "epigallocatechin gallate", "resveratrol",
        ]
    },
    ("COVID-19", "Nirmatrelvir And Ritonavir Drug Combination", None): "combination product (UMLS); may not normalize to an entity the ARAs return",
}

URL = re.compile(r"https?://\S+")


def clean(value) -> Optional[str]:
    """A cell's text without stray (incl. non-breaking) whitespace."""
    if value is None:
        return None
    text = " ".join(str(value).replace("\xa0", " ").split())
    return text or None


def clean_source(value) -> Optional[str]:
    """A source cell, keeping its line breaks."""
    if value is None:
        return None
    lines = [" ".join(line.replace("\xa0", " ").split()) for line in str(value).splitlines()]
    return "\n".join(line for line in lines if line) or None


def curie(value) -> Optional[str]:
    text = clean(value)
    if not text:
        return None
    prefix, _, local = text.partition(":")
    return f"{PREFIX_SPELLINGS.get(prefix, prefix)}:{local}"


def read_rows() -> List[dict]:
    """The spreadsheet's rows as one dict each, in sheet and row order."""
    workbook = openpyxl.load_workbook(SPREADSHEET, data_only=True)
    rows = []
    for row_number, cells in enumerate(
        workbook["MVP1"].iter_rows(min_row=2, values_only=True), start=2
    ):
        if not any(cells):
            continue
        question, question_id, answer, answer_id, source = cells[:5]
        rows.append(dict(
            sheet="MVP1", row=row_number, direction=None,
            input_name=clean(question), input_id=curie(question_id),
            output_name=clean(answer), output_id=curie(answer_id),
            source=clean_source(source),
        ))
    for row_number, cells in enumerate(
        workbook["MVP2"].iter_rows(min_row=2, values_only=True), start=2
    ):
        if not any(cells):
            continue
        question, direction, question_id, answer, answer_id, source = cells[:6]
        rows.append(dict(
            sheet="MVP2", row=row_number, direction=clean(direction),
            input_name=clean(question), input_id=curie(question_id),
            output_name=clean(answer), output_id=curie(answer_id),
            source=clean_source(source),
        ))
    return rows


def questionable_reasons(rows: List[dict]) -> Dict[int, List[str]]:
    """Why each doubtful row is doubtful, by its index in rows."""
    reasons = defaultdict(list)
    seen_outputs = {}
    directions = defaultdict(set)
    for row in rows:
        pair = frozenset([row["input_id"], row["output_id"]])
        if row["sheet"] == "MVP2":
            directions[pair].add(row["direction"])

    for i, row in enumerate(rows):
        for role in ("input", "output"):
            value = row[f"{role}_id"]
            if not value:
                reasons[i].append(f"no {role} CURIE")
            elif value.split(":")[0] not in PREFIXES:
                reasons[i].append(f"{role} CURIE {value} has no Biolink prefix")
        if row["sheet"] == "MVP1" and row["input_id"] and not row["input_id"].startswith("MONDO:"):
            reasons[i].append(
                f"input {row['input_id']} is not a disease (MONDO) ID, but is queried as one"
            )
        key = (row["sheet"], row["input_id"], row["output_id"], row["direction"])
        if row["output_id"] and key in seen_outputs:
            first = rows[seen_outputs[key]]
            reasons[i].append(
                f"same answer CURIE as row {first['row']} ({first['output_name']})"
                if first["output_name"] != row["output_name"]
                else f"duplicate of row {first['row']}"
            )
        else:
            seen_outputs.setdefault(key, i)
        if row["sheet"] == "MVP2":
            pair = frozenset([row["input_id"], row["output_id"]])
            if len(directions[pair]) > 1:
                reasons[i].append(
                    f"{row['input_name']} and {row['output_name']} are listed as both increasing and decreasing"
                )
        reviewed = REVIEWED.get((row["input_name"], row["output_name"], row["direction"]))
        if reviewed:
            reasons[i].append(reviewed)
    return reasons


def statement_key(asset: dict) -> Tuple:
    """What an asset says, independent of its id or CURIE fixes."""
    direction = next(
        (q["value"] for q in asset.get("qualifiers") or []
         if q["parameter"] == "biolink_object_direction_qualifier"),
        "",
    )
    return (asset["input_name"], asset["predicate_name"], direction, asset["output_name"])


def existing_ids() -> Dict[Tuple, str]:
    ids = {}
    for path in glob.glob(os.path.join(ASSET_DIR, "*.json")):
        with open(path, encoding="utf-8") as f:
            asset = json.load(f)
        ids[statement_key(asset)] = asset["id"]
    return ids


def make_asset(row: dict, reasons: List[str]) -> dict:
    if row["sheet"] == "MVP1":
        predicate = "treats"
        direction = ""
        aspect = ""
        qualified_predicate = "biolink:treats"
        # MVP1 queries are for a disease; a phenotype is queried as one
        input_category, output_category = "biolink:Disease", "biolink:ChemicalEntity"
        statement = f"{row['output_name']} treats {row['input_name']}"
    else:
        predicate = "affects"
        direction = {"Increase": "increased", "Decrease": "decreased"}[row["direction"]]
        aspect = "activity_or_abundance"
        qualified_predicate = "biolink:causes"
        gene_input = row["input_id"].startswith("NCBIGene:")
        input_category, output_category = (
            ("biolink:Gene", "biolink:ChemicalEntity") if gene_input
            else ("biolink:ChemicalEntity", "biolink:Gene")
        )
        chemical, gene = (
            (row["output_name"], row["input_name"]) if gene_input
            else (row["input_name"], row["output_name"])
        )
        statement = f"{chemical} {direction[:-1]}s activity or abundance of {gene}"

    source = row["source"] or ""
    links = URL.findall(source)
    annotations = [
        {"parameter": "source", "value": source},
        {"parameter": "source_file", "value": os.path.basename(SPREADSHEET)},
        {"parameter": "source_sheet", "value": row["sheet"]},
        {"parameter": "source_row", "value": str(row["row"])},
    ] + [{"parameter": "questionable_reason", "value": reason} for reason in reasons]

    name = f"Acceptable: {statement}"
    return {
        "name": name,
        "description": name,
        "tags": [],
        "test_runner_settings": ["inferred"],
        "input_id": row["input_id"],
        "input_name": row["input_name"],
        "input_category": input_category,
        "predicate_id": f"biolink:{predicate}",
        "predicate_name": predicate,
        "output_ids": [row["output_id"]] if row["output_id"] else [],
        "output_name": row["output_name"],
        "output_category": output_category,
        "association": None,
        "qualifiers": [
            {"parameter": "biolink_qualified_predicate", "value": qualified_predicate},
            {"parameter": "biolink_object_aspect_qualifier", "value": aspect},
            {"parameter": "biolink_object_direction_qualifier", "value": direction},
        ],
        "expected_output": "Acceptable",
        "test_issue": "questionable" if reasons else None,
        "semantic_severity": None,
        "in_v1": None,
        "well_known": False,
        "test_reference": None,
        "test_metadata": {
            "id": "1",
            "name": None,
            "description": None,
            "tags": [],
            "test_runner_settings": [],
            "test_source": "ExternalRepurposing",
            "test_reference": links[0] if links else None,
            "test_objective": "AcceptanceTest",
            "test_annotations": annotations,
        },
    }


def main():
    rows = read_rows()
    reasons = questionable_reasons(rows)
    ids = existing_ids()
    next_number = 1 + max(
        (int(i[len(ID_PREFIX):]) for i in ids.values() if i.startswith(ID_PREFIX)),
        default=0,
    )

    assets = []
    for i, row in enumerate(rows):
        asset = make_asset(row, reasons.get(i, []))
        key = statement_key(asset)
        if key not in ids:
            ids[key] = f"{ID_PREFIX}{next_number}"
            next_number += 1
        # through the model, so the file has every field the suite's copy has
        asset = TestAsset.model_validate({"id": ids[key], **asset}).model_dump(mode="json")
        assets.append(asset)

    keep = {asset["id"] for asset in assets}
    for path in glob.glob(os.path.join(ASSET_DIR, f"{ID_PREFIX}*.json")):
        if os.path.basename(path)[:-5] not in keep:
            os.remove(path)  # its row is gone from the spreadsheet
    for asset in assets:
        with open(os.path.join(ASSET_DIR, f"{asset['id']}.json"), "w", encoding="utf-8") as f:
            json.dump(asset, f, ensure_ascii=False, indent=4)
            f.write("\n")

    test_cases = create_test_cases_from_test_assets(
        [TestAsset.model_validate(asset) for asset in assets]
    )
    suite = TestSuite(
        id=SUITE_ID,
        name=SUITE_ID,
        description=(
            "External Repurposing: drug repurposing outcomes reported outside "
            "Translator, each test asset carrying its source"
        ),
        test_persona=TestPersonaEnum.All,
        test_suite_specification=None,
        test_cases=test_cases,
        test_metadata=TestMetadata(
            id="1",
            name=None,
            description="External Repurposing tests",
            test_source=TestSourceEnum.ExternalRepurposing,
            test_objective=TestObjectiveEnum.AcceptanceTest,
            test_reference=None,
            test_annotations=[
                {"parameter": "source_file", "value": os.path.basename(SPREADSHEET)},
            ],
        ),
    )
    with open(os.path.join(SUITE_DIR, f"{SUITE_ID}.json"), "w", encoding="utf-8") as f:
        json.dump(suite.model_dump(mode="json"), f, ensure_ascii=False, indent=4)
        f.write("\n")

    flagged = [a for a in assets if a["test_issue"] == "questionable"]
    print(
        f"{len(assets)} assets in {len(test_cases)} test cases, "
        f"{len(flagged)} flagged questionable:"
    )
    for asset in flagged:
        why = [a["value"] for a in asset["test_metadata"]["test_annotations"]
               if a["parameter"] == "questionable_reason"]
        print(f"  {asset['id']}: {asset['name']}: {'; '.join(why)}")


if __name__ == "__main__":
    main()
