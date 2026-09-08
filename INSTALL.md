# Install the skills

The core research skill needs native search/extraction tools and Python 3.11+; its helpers
have no third-party dependencies. Archive compression automatically uses LZMA, deflate,
or uncompressed ZIP according to the codecs available in Python.
The optional research-access plugin installs its own locked Python/npm dependencies and
configures a dedicated browser. It does not configure API keys, model selection, or paid services.

## Hermes

Install the main skill:

```sh
hermes skills install BrentWilkins/research-skills/skills/deep-researcher --category research
```

For scholarly retrieval and local browser fallback, install the companion:

```sh
hermes skills install BrentWilkins/research-skills/skills/hermes-research-access --category research
```

Hermes downloads each skill and its supporting files and handles its installation checks.
Then ask Hermes: “Set up research access using the hermes-research-access skill.” This runs
Hermes's native plugin installer, then installs locked dependencies and enables the plugin with a config backup.
It requires uv and, for browser setup, Node.js/npm. See the companion's
[setup details](skills/hermes-research-access/references/setup.md) for options and prerequisites.
Start a new session afterward. If a customized version already exists, back it up and compare
before choosing to replace it; do not use `--force` without reviewing those changes.
Downloading a skill does not execute its setup automatically or install a Python runtime.

## Skills Hub discovery

To make this repository searchable in your Hermes Skills Hub, add it as a tap:

```sh
hermes skills tap add BrentWilkins/research-skills
hermes skills search research
```

This is a user-added source, not a listing in Hermes's curated default catalog. Direct
installation works without adding a tap. Private repositories require GitHub access;
anonymous discovery and installation require a public repository.

## Manual copy

From the repository root, copy each complete skill directory into the research category of
the active Hermes home's skills directory. Start a new Hermes session after installation.
For the default Hermes home on a POSIX shell:

```sh
(
research_skill_root="${HERMES_HOME:-$HOME/.hermes}/skills/research"
test ! -e "$research_skill_root/deep-researcher" || exit 1
test ! -e "$research_skill_root/hermes-research-access" || exit 1
mkdir -p "$research_skill_root"
cp -R skills/deep-researcher "$research_skill_root/deep-researcher"
cp -R skills/hermes-research-access "$research_skill_root/hermes-research-access"
)
```

Run the block together; it stops if either destination exists. To upgrade an existing skill,
first save that exact skill directory to a backup outside the scanned skills directory and
move the existing installation aside. Then run the copy block. Keep the backup until the
new workflow is verified; rollback means restoring that directory and starting a new session.
Do not overwrite a locally customized skill without comparing it first.

The companion includes plugin setup; the main research skill can also run with Hermes's
existing retrieval tools. Do not enable the companion's browser instructions before setup succeeds.

## Other skill-capable hosts

Copy `skills/deep-researcher/` into the host's supported skill location, preserving scripts
and references. Resolve SKILL in examples to that installed directory and RUN to a new
dedicated output directory. Tool names and skill discovery differ across hosts; the offline
validation here is not a claim that every host has been tested. Do not install the
Hermes-specific companion unless Hermes is installed.

## Verify without a model call

```sh
python3 -m unittest discover -s tests -v
python3 skills/deep-researcher/scripts/evidence_ledger.py --help
python3 skills/deep-researcher/scripts/research_run.py --help
```

The fixture tests do not make network/model calls. Their temporary files are cleaned up.
Generated user research should live outside the installed skill and outside this repository.
