#!/usr/bin/env python3
"""
CLI Script to generate a TestSuite of TestCases from specified TestAssets
"""
from typing import List
from argparse import ArgumentParser
from urllib.parse import urlparse
from linkml_runtime.loaders import tsv_loader, json_loader, yaml_loader
from linkml_runtime.dumpers import json_dumper

from translator_testing_model.datamodel.translator_testing_model import (
    TestAsset,
    TestCase,
    TestSuite
)


def url_type(arg):
    url = urlparse(arg)
    if all((url.scheme, url.netloc)):
        return arg
    raise TypeError("Invalid URL")


def main(args):
    test_suite_id: str = args["test_suite_id"]
    test_suite_name: str = args["test_suite_name"]

    test_assets_url: str = args["test_assets_url"]
    test_assets_format: str = test_assets_url.split('.')[-1]

    test_suite_url: str = args["test_suite_url"]
    # sanity check - remove any trailing slash in URL; anything else will really screw things up for now!
    test_suite_url = test_suite_url.rstrip("/")

    # Load the targeted TestAssets
    if test_assets_format == "tsv":
        test_assets = tsv_loader.load_any(test_assets_url, target_class=TestAsset)
    elif test_assets_format == "json":
        test_assets = json_loader.load_any(test_assets_url, target_class=TestAsset)
    elif test_assets_format == "yaml":
        test_assets = yaml_loader.load_any(test_assets_url, target_class=TestAsset)
    else:
        raise RuntimeError(f"Unknown TestAsset file format: {test_assets_format}")

    # TODO: Filter out TestAssets if required (need more CLI params and methodology)

    # Build the list of TestCases
    test_cases: List[TestCase] = list()
    n = 0
    for asset in test_assets:
        n += 1
        tc_id = f"TestCase:{n}"
        test_case = TestCase(id=tc_id, test_assets=asset)
        test_cases.append(test_case)

    test_suite = TestSuite(id=test_suite_id, name=test_suite_name, test_cases=test_cases)

    test_suite_text: str = json_dumper.dumps(element=test_suite)

    # TODO: Publish the new Test Suite as a JSON file 'blob' in the target (Github) location
    test_suite_file = f"{test_suite_url}/{test_suite_name.strip()}.json"
    pass


def cli():
    """Parse args and run tests."""
    parser = ArgumentParser(description="Translator Testing Test Suite Generator")

    parser.add_argument(
        "-i", "--test_suite_id",
        type=str,
        required=True,
        help="CURIE of Test Suite to create.",
    )

    parser.add_argument(
        "-n", "--test_suite_name",
        type=str,
        required=True,
        help="Human readable name of Test Suite to create.",
    )

    parser.add_argument(
        "-a", "--test_assets_url",
        type=url_type,
        required=True,
        help="Input source URL location of test assets file. " +
             "File format discerned from file extension " +
             "(One of 'tsv', 'json' or 'yaml' assumed).",
    )

    parser.add_argument(
        "-s", "--test_suite_url",
        type=url_type,
        default="https://github.com/NCATSTranslator/Tests",
        help="Target storage URL location of resulting Test Suite and related data" +
             " (Default: 'https://github.com/NCATSTranslator/Tests')",
    )

    # parser.add_argument(
    #     "--log_level",
    #     type=str,
    #     choices=["ERROR", "WARNING", "INFO", "DEBUG"],
    #     help="Level of the logs.",
    #     default="WARNING",
    # )

    args = parser.parse_args()

    main(vars(args))


if __name__ == "__main__":
    cli()

