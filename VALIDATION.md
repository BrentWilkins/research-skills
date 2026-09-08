# Tests and limitations

Run the suite from the repository root:

```sh
python3 -m unittest discover -s tests -v
```

The unit tests use synthetic data and temporary directories. They make no network or model calls.

## Coverage

- Evidence locations and claim links, including malformed, missing, and unrelated evidence.
- Source independence: unassessed origins do not count as corroboration, and publications
  sharing one assessed origin count once.
- Explicit brief truncation without changing stored evidence.
- Offline report citation checks.
- Checkpoint preservation, storage warnings, and refusal to archive active or incomplete runs.
- Lossless archive/restore, verified pruning, preservation of unregistered files,
  corrupt archive rejection, and refusal to overwrite existing archives or restore targets.
- Successful archive/restore when LZMA is unavailable, and when both LZMA and zlib are unavailable.
- Artifact path and symlink checks.
- Source-package inventory and checksums, with the research tests rerun from an extracted copy.
- Installation into an isolated Hermes home and refusal to overwrite an existing customization.
- Plugin setup preservation, dependency-failure rollback, and refusal of unsafe destinations.

The suite has been exercised on Python 3.11 and 3.14 on Linux.

## Limits

Structural checks cannot prove factual truth, semantic citation support, source independence,
or research completeness. These require review of the actual evidence.

Optional `tests/check_hermes_runtime.py` and `tests/check_browser_runtime.py` exercise actual
Hermes plugin discovery, web extraction, and browser dispatch in a disposable home. The
browser fixture permits only its exact loopback URL in the test process; it does not change
host URL policy. `--live` on the extraction check retrieves a public PubMed article. These
checks make no model calls. They require Hermes and a plugin installation made by setup.py.

`tests/check_hub_install.py` verifies tap discovery, both skill installs, and optionally native
plugin installation in a temporary Hermes home. It requires GitHub access and uses the normal
skill/plugin scanners without force overrides. Run dependency setup from the downloaded plugin
before the runtime checks. This tests direct/tap delivery, not inclusion in a curated catalog.

These checks do not establish research quality across models or backends, validate paid-service
configuration, or deploy a search/Firecrawl service. They have been exercised on Linux.

The storage budget is a warning for registered artifacts, not a hard disk quota or a policy
for backend caches. Compression ratios depend on the input; already compressed documents
may not shrink. Archives are not encrypted and do not replace a separate backup.
