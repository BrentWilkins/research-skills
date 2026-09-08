# Evidence-led research skills

A research workflow for source-backed decisions: track atomic claims against exact
passages, distinguish shared origins from independent corroboration, and keep retrieval
failures and evidence gaps visible. Reports are reviewed for semantic support as well as
checked by scripts. Script checks do not establish that a claim is true.

The package contains two skills:

- **deep-researcher:** research framing, bounded discovery, evidence/claim ledger, source
  locators, confidence calibration, counter-evidence, report audit, run checkpoints, and
  verified lossless archive/restore. Requires native retrieval tools and standard-library Python.
- **hermes-research-access:** bundled scholarly retrieval plugin, isolated dependency setup,
  and a local browser helper, with native-tool and no-extra-model controls.

Install directly with `hermes skills install BrentWilkins/research-skills/skills/deep-researcher --category research`, then read
[installation instructions](INSTALL.md). A synthetic [worked example](skills/deep-researcher/references/worked-example.md)
shows shared-origin evidence and an unresolved claim. [Run management](skills/deep-researcher/references/run-management.md)
explains checkpoints, storage warnings, and archive recovery. SKILL and RUN in examples are
path placeholders; replace them with absolute directories for your installation and run.

## Storage and context

Keep a compact ledger and derived brief; retain full source text only when verification
needs it. Brief output defaults to a visible 24,000-character cap. Registered working files
have a configurable 64 MiB warning budget, not a hard disk or backend-cache quota.

Completed runs use lossless LZMA compression, falling back to deflate or an uncompressed ZIP
when optional Python codecs are unavailable. No extra packages are required. Optional pruning happens only after
archive verification and leaves report.md and the recovery manifest readable. Compression
reduces disk storage; selective reading reduces model context.

## Tests and packaging

See [test coverage and limitations](VALIDATION.md).

```sh
python3 -m unittest discover -s tests -v
python3 scripts/build_package.py --output dist/research-skills.tar.gz
```

The tests use temporary synthetic artifacts and make no network or model calls. The builder
includes only [the explicit file list](PACKAGE_FILES.txt), adds SHA256SUMS, and verifies the
archive. It refuses to overwrite an existing output. Generated research and runtime state
are excluded from the source package.

## Attribution

Licensed under [MIT](LICENSE). Related work:
[SkillMedev's deep-research skill](https://github.com/SkillMedev/skills/blob/main/skills/deep-research/SKILL.md)
on research scope and worked examples, and
[LovStudio's deep-research skill](https://github.com/lovstudio/deep-research-skill/blob/main/SKILL.md)
on evidence locators and run manifests.
