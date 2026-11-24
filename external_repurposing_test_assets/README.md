# External Repurposing Test Assets

Drug repurposing outcomes reported outside Translator: a repurposing
portfolio, NCATS drug approvals, publications, clinical programs. They make up
the [`external_repurposing_tests`](../test_suites/external_repurposing_tests.json)
suite, run like any other:

```bash
test-harness --env prod download external_repurposing_tests
```

They live apart from [`test_assets/`](../test_assets) so the MVP suite
generator, which takes every asset there, doesn't pick them up.

## Where they come from

[`source/SmartQueryTestCaseProposals.xlsx`](source/SmartQueryTestCaseProposals.xlsx)
is the spreadsheet as it was handed over. Each row is one asset:

- sheet `MVP1`: a disease and a drug: *what drug treats this disease?*
- sheet `MVP2`: a gene or a chemical, a direction (`Increase`/`Decrease`) and
  the other one: *what chemical increases (decreases) the activity or
  abundance of this gene?*, or the same asked from the chemical

Every asset expects its answer as `Acceptable`, and its `test_metadata`
keeps its provenance:

| Field | Holds |
| --- | --- |
| `test_source` | `ExternalRepurposing` |
| `test_reference` | the first link in the row's source, if it has one |
| `test_annotations` `source` | the row's source cell, as written (eg `HHS CMS`, or several links) |
| `test_annotations` `source_file`, `source_sheet`, `source_row` | where in the spreadsheet the row is |

## Questionable assets

Rows whose data looks doubtful have `test_issue: questionable`, and one
`questionable_reason` annotation per doubt. They still run; read their results
with care until someone checks them. The generator flags a row that has

- no CURIE, or a CURIE without a Biolink prefix (eg `PUBCHEM:` rather than
  `PUBCHEM.COMPOUND:`)
- an MVP1 input that isn't a MONDO disease (it is queried as a disease anyway)
- the same answer CURIE as an earlier row for the same question
- a chemical and gene listed as both increasing and decreasing

and the rows listed in `REVIEWED` in the generator, which a person flagged
(eg a citation that looks like a spreadsheet fill). Once a row is checked,
fix it in the spreadsheet, or take it out of `REVIEWED`, and regenerate.

## Changing the assets

Change the spreadsheet (replace it with a new version, keeping its name), then
regenerate, from the repository root:

```bash
pip install -r test_generators/requirements.txt
python -m test_generators.external_repurposing_suite_generator
```

An asset keeps its id while its statement (input, predicate, direction and
answer name) stays the same, so the Information Radiator keeps its history;
fixing a CURIE doesn't change it. Assets whose rows are gone are deleted. The
suite's test case ids are renumbered, as for the other suites.

To change a single asset without the spreadsheet (eg to `skip` it), edit its
file here and run `python test_generators/sync_asset_copies.py`, as for any
other asset; but the next regeneration from the spreadsheet will undo it.
