#!/usr/bin/env python3
"""
Script to generate a TestSuite of TestCases from specified TestAssets
"""
import copy
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
    TestAsset,
    TestMetadata,
    TestPersonaEnum,
    TestSourceEnum,
    TestObjectiveEnum,
    TestEnvEnum,
)

from test_generators.utils import create_test_cases_from_test_assets, dump_to_json


def generate_message(query, num_curies):
    nodes = query["message"]["query_graph"]["nodes"]
    for node in nodes.values():
        if "ids" in node:
            node["ids"] = node["ids"][:num_curies]
    query["bypass_cache"] = True
    return query


creative_query = {
    "message": {
        "query_graph": {
            "nodes": {
                "ON": {
                    "categories": [
                        "biolink:Disease"
                    ],
                    "ids": [
                        "MONDO:0005301"
                    ]
                },
                "SN": {
                    "categories": [
                        "biolink:ChemicalEntity"
                    ]
                }
            },
            "edges": {
                "t_edge": {
                    "object": "ON",
                    "subject": "SN",
                    "predicates": [
                        "biolink:treats"
                    ],
                    "knowledge_type": "inferred"
                }
            }
        }
    },
    "bypass_cache": True,
}


def create_test_suite(
    logger: logging.Logger,
) -> None:
    """Download tests from specified location."""
    with open("./asset_backups/kp_performance_tests_2024_10_18.json", "r") as f:
        data = json.load(f)

        test_suite = {
            "id": "performance_tests",
            "name": "Performance Tests",
            "description": "Performance Tests",
            "tags": [],
            "test_runner_settings": [],
            "test_metadata": {},
            "test_persona": "Developer",
            "test_suite_specification": None,
            "test_cases": {},
        }
        # sequential KP
        for rate in [(900, 1), (180, 10), (90, 100), (30, 1000)]:
            for kp in data.values():
                infores = kp["infores"]
                uid = f"{infores}_sequential_{rate[0]}x{rate[1]}"
                test_case = {
                    "id": uid,
                    "name": f"[{infores}] {rate[0]} Sequential {rate[1]} curie queries",
                    "description": f"[{infores}] {rate[0]} Sequential {rate[1]} curie queries",
                    "tags": [],
                    "test_runner_settings": [],
                    "query": generate_message(copy.deepcopy(kp["query"]), rate[1]),
                    "num_queries": rate[0],
                    "concurrent": False,
                    "components": [infores],
                }
                test_suite["test_cases"][uid] = test_case
        # concurrent KP
        for rate in [(10, 1), (100, 1), (1000, 1), (10, 10), (100, 10), (1000, 10), (10, 1000), (100, 1000), (1000, 1000)]:
            for kp in data.values():
                infores = kp["infores"]
                uid = f"{infores}_concurrent_{rate[0]}x{rate[1]}"
                test_case = {
                    "id": uid,
                    "name": f"[{infores}] {rate[0]} Concurrent {rate[1]} curie queries",
                    "description": f"[{infores}] {rate[0]} Concurrent {rate[1]} curie queries",
                    "tags": [],
                    "test_runner_settings": [],
                    "query": generate_message(copy.deepcopy(kp["query"]), rate[1]),
                    "num_queries": rate[0],
                    "concurrent": True,
                    "components": [infores],
                }
                test_suite["test_cases"][uid] = test_case
        
        # sequential ARA
        test_suite["test_cases"]["ara_sequential_tests"] = {
            "id": "ara_sequential_tests",
            "name": "Sequential ARA Performance Tests",
            "description": "Sequential ARA Performance Tests",
            "tags": [],
            "test_runner_settings": [],
            "query": creative_query,
            "num_queries": 15,
            "concurrent": False,
            "components": ["ara"],
        }

        # concurrent ARA
        for rate in [10, 50, 100, 1000]:
            uid = f"ara_{rate}_concurrent_tests"
            test_suite["test_cases"][uid] = {
                "id": uid,
                "name": f"{rate} Concurrent ARA Performance Tests",
                "description": f"{rate} Concurrent ARA Performance Tests",
                "tags": [],
                "test_runner_settings": [],
                "query": creative_query,
                "num_queries": rate,
                "concurrent": True,
                "components": ["ara"],
            }

        # sequential ARS
        test_suite["test_cases"]["ars_sequential_tests"] = {
            "id": "ars_sequential_tests",
            "name": "Sequential ARS Performance Tests",
            "description": "Sequential ARS Performance Tests",
            "tags": [],
            "test_runner_settings": [],
            "query": creative_query,
            "num_queries": 15,
            "concurrent": False,
            "components": ["ars"],
        }

        # concurrent ARS
        for rate in [10, 50, 100, 1000]:
            uid = f"ars_{rate}_concurrent_tests"
            test_suite["test_cases"][uid] = {
                "id": uid,
                "name": "Concurrent ARS Performance Tests",
                "description": "Concurrent ARS Performance Tests",
                "tags": [],
                "test_runner_settings": [],
                "query": creative_query,
                "num_queries": rate,
                "concurrent": True,
                "components": ["ars"],
            }
        
        with open("../test_suites/performance_tests.json", "w") as f:
            json.dump(test_suite, f, indent=2)


if __name__ == "__main__":
    create_test_suite(
        logging.Logger("tester"),
    )
