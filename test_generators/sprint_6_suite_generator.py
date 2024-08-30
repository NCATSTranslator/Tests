#!/usr/bin/env python3
"""
Script to generate a TestSuite of TestCases from specified TestAssets
"""
import glob
import httpx
import io
import json
import logging
from pathlib import Path
import tempfile
from typing import List, Union, Dict
import zipfile

from translator_testing_model.datamodel.pydanticmodel import (
    TestCase,
    TestSuite,
    TestAsset,
    TestMetadata,
    Qualifier,
    TestPersonaEnum,
    TestSourceEnum,
    TestObjectiveEnum,
    TestEnvEnum,
    ComponentEnum,
)


def create_test_cases_from_test_assets(test_assets) -> Dict[str, TestCase]:
    # Group test assets based on input_id and relationship
    grouped_assets = {}
    for test_asset in test_assets:
        qualifier_key = ""
        if test_asset.qualifiers and test_asset.qualifiers is not None:
            for qualifier in test_asset.qualifiers:
                qualifier_key = qualifier_key+qualifier.value
        key = (test_asset.input_id, test_asset.predicate_name, qualifier_key)
        if key not in grouped_assets:
            grouped_assets[key] = []
        grouped_assets[key].append(test_asset)

    # Create test cases from grouped test assets
    test_cases = {}
    for idx, (key, assets) in enumerate(grouped_assets.items()):
        test_case_id = f"TestCase_{idx}"
        descriptions = '; '.join(asset.description for asset in assets)
        first_asset = next(iter(assets))
        test_case = TestCase(
            id=test_case_id,
            name="what " + key[1] + " " + key[0],
            description=descriptions,
            test_env=TestEnvEnum.ci,
            components=[ComponentEnum.ars],
            test_case_objective=TestObjectiveEnum.AcceptanceTest,
            test_case_predicate_name=first_asset.predicate_name,
            test_case_predicate_id=first_asset.predicate_id,
            test_case_input_id=first_asset.input_id,
            input_category=first_asset.input_category,
            output_category=first_asset.output_category,
            test_assets=assets,
            test_runner_settings=["inferred"],
            query_type=None,
            trapi_template=None,
            test_case_source=None,
        )
        if test_case.test_assets is None:
            print("test case has no assets", test_case)

        if test_case.test_case_objective == "AcceptanceTest":
            test_input_id = ""
            test_case_predicate_name = ""
            test_case_qualifiers = []
            input_category = ""
            output_category = ""
            for asset in assets:
                # these all assume group by applies to the same input_id and predicate_name
                test_input_id = asset.input_id
                test_case_predicate_name = asset.predicate_name
                test_case_qualifiers = asset.qualifiers
                input_category = asset.input_category
                output_category = asset.output_category

            test_case.test_case_input_id = test_input_id
            test_case.test_case_predicate_name = test_case_predicate_name
            test_case.test_case_predicate_id = "biolink:" + test_case_predicate_name
            test_case.qualifiers = test_case_qualifiers
            test_case.input_category = input_category
            test_case.output_category = output_category
            test_cases[test_case_id] = test_case

    return test_cases


def dump_to_json(file_path, test_object):
    filename = f"{file_path}/{test_object.id}.json"
    with open(f"{filename}", 'w', encoding='utf-8') as file:
        json.dump(test_object.dict(), file, ensure_ascii=False, indent=4)


def create_test_suite(
    url: str,
    logger: logging.Logger,
) -> None:
    """Download tests from specified location."""
    assert Path(url).suffix == ".zip"
    logger.info(f"Downloading tests from {url}...")
    # download file from internet
    with httpx.Client(follow_redirects=True) as client:
        tests_zip = client.get(url)
        tests_zip.raise_for_status()
        # we already checked if zip before download, so now unzip
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(io.BytesIO(tests_zip.read())) as zip_ref:
            zip_ref.extractall(tmpdir)

        # Find all json files in the downloaded zip
        # tests_paths = glob.glob(f"{tmpdir}/**/*.json", recursive=True)

        tests_paths = glob.glob(f"{tmpdir}/*/test_assets/*.json")

        test_assets = []

        for test_asset_path in tests_paths:
            with open(test_asset_path) as f:
                asset_json = json.load(f)
                try:
                    test_asset = TestAsset.parse_obj(asset_json)
                    if test_asset.expected_output in ["TopAnswer", "NeverShow"]:
                        test_assets.append(test_asset)
                except Exception as e:
                    logger.warning(f"Failed to read asset {asset_json['id']}: {e}")
        
        test_cases = create_test_cases_from_test_assets(test_assets)

        suite_id = "sprint_6_tests"

        # Assemble into a TestSuite
        tmd = TestMetadata(
            id="1",
            name=None,
            description="Sprint 6 tests",
            test_source=TestSourceEnum.SMURF,
            test_objective=TestObjectiveEnum.AcceptanceTest,
            test_reference=None,
        )
        new_suite = TestSuite(
            id=suite_id,
            name="sprint_6_tests",
            description="Sprint 6 tests",
            test_persona=TestPersonaEnum.All,
            test_suite_specification=None,
            test_cases=test_cases,
            test_metadata=tmd,
        )

        dump_to_json("../test_suites", new_suite)


if __name__ == "__main__":
    create_test_suite(
        "https://github.com/NCATSTranslator/Tests/archive/refs/heads/main.zip",
        logging.Logger("tester"),
    )
