# Test Suites

One suite per kind of test, run in every environment:

| Suite | What it tests |
| --- | --- |
| `mvp_tests` | Acceptance: the MVP queries (drug treats disease, chemical affects gene) |
| `pathfinder_tests` | Pathfinder queries |
| `performance_tests` | Load, with [HelmsDeep](https://github.com/TranslatorSRI/HelmsDeep) |

Suites don't say which environment they run in: the Test Harness is told, eg
`test-harness --env prod download mvp_tests`.

[`deprecated/`](deprecated) has the suites these replaced, including the old
per-environment copies (`prod_integration`, `test_integration`,
`pathfinder_tests_PROD`, ...). They still load, eg
`test-harness --env ci download deprecated/sprint_3_tests`, but nothing runs
them.

## Editing a test

A suite carries its own copy of every test asset it uses, and the copy is what
the Test Harness runs. To change an asset (eg fix a CURIE), edit it in
[`test_assets/`](../test_assets) or
[`pathfinder_test_assets/`](../pathfinder_test_assets), then bring its copies
up to date:

```bash
python test_generators/sync_asset_copies.py           # update the copies
python test_generators/sync_asset_copies.py --check   # report out-of-date copies
```

This keeps every test case id, which is how the Information Radiator follows
an asset's history; regenerating a suite renumbers its test cases.

## Skipping a test

A test that always fails for a known reason can be turned off until the issue
behind it is fixed. Set `skip` and a `skip_reason` on the asset, then sync it:

```json
"skip": true,
"skip_reason": "ARAs return the parent class: Tests#140"
```

To skip a whole test case, set them on the test case in the suite file itself
(`test_cases/` is from an older generation of the suites, and its test case
ids don't match). Skipped tests aren't run; the Test Harness reports them as
`SKIPPED` with the reason, and `--include_skipped` runs them anyway. `skip`
needs translator-testing-model 0.7.0, so a Test Harness on an older one can't
read a suite that uses it.
