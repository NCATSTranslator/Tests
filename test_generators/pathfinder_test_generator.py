import glob
import httpx
import io
import json
import logging
from pathlib import Path
import tempfile
import zipfile

from translator_testing_model.datamodel.pydanticmodel import (
    TestSuite,
    PathfinderTestAsset,
    TestMetadata,
    TestPersonaEnum,
    TestSourceEnum,
    TestObjectiveEnum,
    TestEnvEnum,
)

from utils import create_pathfinder_test_cases_from_test_assets, dump_to_json


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

        tests_paths = glob.glob(f"{tmpdir}/*/pathfinder_test_assets/*.json")

        test_assets = []

        for test_asset_path in tests_paths:
            with open(test_asset_path) as f:
                asset_json = json.load(f)
                try:
                    test_asset = PathfinderTestAsset.parse_obj(asset_json)
                    if test_asset.expected_output in ["TopAnswer", "Acceptable", "BadButForgivable", "NeverShow"]:
                        test_assets.append(test_asset)
                except Exception as e:
                    logger.warning(f"Failed to read asset {asset_json['id']}: {e}")
        
        test_cases = create_pathfinder_test_cases_from_test_assets(test_assets, TestEnvEnum.ci)

        suite_id = "pathfinder_tests"

        # Assemble into a TestSuite
        tmd = TestMetadata(
            id="1",
            name=None,
            description="Pathfinder tests",
            test_source=TestSourceEnum.SMURF,
            test_objective=TestObjectiveEnum.AcceptanceTest,
            test_reference=None,
        )
        new_suite = TestSuite(
            id=suite_id,
            name="pathfinder_tests",
            description="Pathfinder tests",
            test_persona=TestPersonaEnum.All,
            test_suite_specification=None,
            test_cases=test_cases,
            test_metadata=tmd,
        )

        dump_to_json("../test_suites", new_suite)
        for test_case in test_cases.values():
            dump_to_json("../pathfinder_test_cases", test_case)


if __name__ == "__main__":
    create_test_suite(
        "https://github.com/NCATSTranslator/Tests/archive/refs/heads/more_pathfinder.zip",
        logging.Logger("tester"),
    )
