#!/usr/bin/env python3
"""
Utility functions for creating Test Suites.
"""
import json
from typing import Dict

from translator_testing_model.datamodel.pydanticmodel import (
    TestCase,
    TestObjectiveEnum,
    TestEnvEnum,
    ComponentEnum,
)


def create_test_cases_from_test_assets(test_assets, test_env: TestEnvEnum) -> Dict[str, TestCase]:
    # Group test assets based on input_id and relationship
    grouped_assets = {}
    for test_asset in test_assets:
        qualifier_key = ""
        if test_asset.qualifiers and test_asset.qualifiers is not None:
            for qualifier in test_asset.qualifiers:
                qualifier_key = qualifier_key + qualifier.value
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
            test_env=test_env,
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
