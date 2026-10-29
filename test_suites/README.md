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
