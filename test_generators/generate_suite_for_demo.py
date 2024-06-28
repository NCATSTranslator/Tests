
import bmt
import csv
import enum
import json
from translator_testing_model.datamodel.pydanticmodel import (
  TestAsset,
  TestCase,
  TestSuite,
  TestMetadata,
  Qualifier,
  TestPersonaEnum,
  TestSourceEnum,
  TestObjectiveEnum,
  TestEnvEnum,
  ComponentEnum,
)
from typing import Dict, List

toolkit = bmt.Toolkit()


class SuiteNames(enum.Enum):
    pass_fail = "pass_fail"
    quantitative = "quantitative"
    full = "full"


def parse_tsv(filename):
    """
    Parse a TSV file and return a list of dictionaries.

    :param filename: The path to the TSV file.
    :return: A list of dictionaries, where each dictionary represents a row in the TSV.
    """
    with open(filename, newline='', encoding='utf-8') as tsvfile:
        # Use csv.DictReader, specifying the delimiter as a tab
        reader = csv.DictReader(tsvfile, delimiter='\t')

        # Convert the reader into a list of dictionaries
        return list(reader)


def get_converted_predicate(specified_predicate, toolkit):
    if specified_predicate == "decreases abundance or activity of":
        specified_predicate = "decreases activity or abundance of"
    element = toolkit.get_element(specified_predicate)
    if element is not None:
        return element.name.replace(" ", "_"), "", "", "biolink:" + element.name
    else:
        for collection in toolkit.pmap.values():
            for item in collection:
                if item.get("mapped predicate") == specified_predicate:
                    return (
                        item.get("predicate").replace(" ", "_"),
                        item.get("object aspect qualifier"),
                        item.get("object direction qualifier"),
                        "biolink:" + item.get("qualified predicate"),
                    )
    return specified_predicate, "", "", ""


def get_category(prefixes, id):
    if id.startswith("NCBIGene:"):
        return 'biolink:Gene'
    elif id.startswith("MONDO:"):
        return 'biolink:Disease'
    elif id.startswith("UBERON:"):
        return 'biolink:AnatomicalEntity'
    elif id.startswith("HP:"):
        return 'biolink:PhenotypicFeature'
    elif id.startswith("DRUGBANK:") or id.startswith("CHEBI:") or any(id.startswith(prefix) for prefix in prefixes):
        return 'biolink:ChemicalEntity'
    return None


def get_expected_output(row):
    output = row.get("Expected Result / Suggested Comparator")
    if output in ["4_NeverShow", "3_BadButForgivable", "2_Acceptable", "1_TopAnswer", "5_OverlyGeneric"]:
        return output.split("_")[1]
    print(f"{row.get('id')} has invalid expected output: {output}")
    return None


def create_test_asset(row):
    specified_predicate = row.get("Relationship").lower().strip()
    converted_predicate, biolink_object_aspect_qualifier, biolink_object_direction_qualifier, biolink_qualified_predicate = get_converted_predicate(specified_predicate, toolkit)

    expected_output = get_expected_output(row)
    if not expected_output:
        print(f"Asset id {row.get('id')} has no expected output")
        return None

    chem_prefixes = toolkit.get_element("chemical entity").id_prefixes
    input_category = get_category(chem_prefixes, row.get("InputID"))
    output_category = get_category(chem_prefixes, row.get("OutputID"))

    ta = TestAsset(
        id=row.get("id").replace(":", "_"),
        name=f"{expected_output}: {row.get('OutputName').strip()} {specified_predicate} {row.get('InputName').strip()}",
        description=f"{expected_output}: {row.get('OutputName').strip()} {specified_predicate} {row.get('InputName').strip()}",
        input_id=row.get("InputID").strip(),
        input_name=row.get("InputName").strip(),
        predicate_name=converted_predicate,
        predicate_id=f"biolink:{converted_predicate}",
        output_id=row.get("OutputID").strip(),
        output_name=row.get("OutputName").strip(),
        output_category=output_category,
        expected_output=expected_output.strip(),
        association=None,
        test_issue=None,
        semantic_severity=None,
        in_v1=None,
        well_known=None,
        test_reference=None,
        test_metadata=TestMetadata(
            id="1",
            name=None,
            description=None,
            test_source=TestSourceEnum.SMURF,
            test_reference=row.get("Translator GitHubIssue").strip() if row.get("Translator GitHubIssue") else None,
            test_objective=TestObjectiveEnum.AcceptanceTest,
        ),
        input_category=input_category,
    )
    ta.input_name = row.get("InputName").strip()
    ta.test_runner_settings = [row.get("Settings").lower()]

    if biolink_qualified_predicate:
        ta.qualifiers = [
            Qualifier(parameter="biolink_qualified_predicate", value=biolink_qualified_predicate),
            Qualifier(parameter="biolink_object_aspect_qualifier", value=biolink_object_aspect_qualifier.replace(" ", "_")),
            Qualifier(parameter="biolink_object_direction_qualifier", value=biolink_object_direction_qualifier),
        ]

    ta.well_known = row.get("Well Known") == "yes"

    return ta


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


# Functions to create TestAssets, TestCases, and TestSuite
def create_test_assets_from_tsv(test_assets: list, suite_name: SuiteNames) -> List[TestAsset]:
    asset_ids = set()
    assets = []
    for row in test_assets:
        if row.get("Relationship") == "" or row.get("OutputID") == "" or row.get("InputID") == "":
            print("Skipping row with missing relationship, input or output ID", row.get("id"))
            continue
        if suite_name == SuiteNames.pass_fail:
            ta = create_test_asset(row)
            try:
                if ta.id in asset_ids:
                    print(f"Got duplicate asset id {ta.id}")
            except Exception as e:
                print(ta)
            asset_ids.add(ta.id)
            assets.append(ta)
    return assets


def main():
    # Reading the TSV file
    tsv_file_path = "asset_backups/2024_06_20.tsv"
    tsv_data = parse_tsv(tsv_file_path)

    # Create TestAsset objects
    test_assets = create_test_assets_from_tsv(tsv_data, SuiteNames.pass_fail)

    print(len(test_assets))

    test_assets = sorted(test_assets, key=lambda asset: int(asset.id.split("_")[1]))

    # Create TestCase objects
    test_cases = create_test_cases_from_test_assets(test_assets)

    print(len(test_cases.values()))

    for i, item in enumerate(test_cases.values()):
        dump_to_json("../test_cases", item)

    for i, item in enumerate(test_assets):
        dump_to_json("../test_assets", item)

    suite_id = "sprint_4_tests"
    suite_test_assets = []
    # trim test assets for specific suite
    for test_asset in test_assets:
        if test_asset.expected_output == "TopAnswer":
            suite_test_assets.append(test_asset)
    suite_test_cases = create_test_cases_from_test_assets(suite_test_assets)

    # Assemble into a TestSuite
    tmd = TestMetadata(
        id="1",
        name=None,
        description="Sprint 4 TopAnswer tests",
        test_source=TestSourceEnum.SMURF,
        test_objective=TestObjectiveEnum.AcceptanceTest,
        test_reference=None,
    )
    new_suite = TestSuite(
        id=suite_id,
        name="sprint_4_tests",
        description="Sprint 4 TopAnswer tests",
        test_persona=TestPersonaEnum.All,
        test_suite_specification=None,
        test_cases=suite_test_cases,
        test_metadata=tmd,
    )
    #

    dump_to_json("../test_suites", new_suite)


if __name__ == '__main__':
    main()
