# Translator Tests
This repository contains all of the automated tests that are run by the Test Harness upon Translator.

## Overview
This repo consists of three testing parts:
- **Test Assets**: these are manually and automatically curated test inputs, outputs, and other relevant metadata for a given test.
- **Test Cases**: these are automatically generated given the Test Assets. A single Test Asset could potentially be used across multiple Test Cases. Test Cases add more definition to how the expected output should be evaluated.
- **Test Suites**: these are automatically generated given the Test Cases. Test Suites are a combination of similar Test Cases that should all be run together.
 
