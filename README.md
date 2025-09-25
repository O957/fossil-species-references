# Fossil Species References Application

> [!CAUTION]
>
> This project is very new and as such may have inadequacies, including bugs and errors. If you spot something that you would like changed, please make an issue [here](https://github.com/O957/fossil-species-references/issues) or contact the author [here](https://o957.github.io/#contact-information).

## This Repository

__What is this repository?__

This repository consists of a Streamlit application and standalone Python script for retrieving original publication data for fauna using the Paleobiology Database.

__What background information is needed?__

* Only knowledge of fossil fauna is needed (e.g. _Enchodus petrosus_ or _Diplodocus carnegii_) to get started.
* (optional) To run items locally you will need to have Python3 installed.

__What is in this repository?__

* The folder `.devcontainer` contains:
  * Items necessary for the `streamlit` application to be hosted online (see [here](https://github.com/O957/fossil-species-references/tree/main/.devcontainer)).
* The folder `.github` contains:
  * GitHub workflows for dependency management (`deptry`), styling and linting (`pre-commit`), and type-checking (`ty`) (see [here](https://github.com/O957/fossil-species-references/tree/main/.github/workflows)).
  * Code owners file (see [here](https://github.com/O957/fossil-species-references/blob/main/.github/CODEOWNERS)).
  * A `dependabot` workflow file (see [here](https://github.com/O957/fossil-species-references/blob/main/.github/dependabot.yaml)).
* The folder `.streamlit` contains:
  * A `streamlit` theme file (see [here](https://github.com/O957/fossil-species-references/blob/main/.streamlit/config.toml)).
* The folder `assets` contains:
  * Decisions relevant to this repository (see [here](https://github.com/O957/fossil-species-references/blob/main/assets/misc/decisions.md)).
  * A feature list for this repository (see [here](https://github.com/O957/fossil-species-references/blob/main/assets/misc/feature-list.md)).
  * Glossary terms relevant to this repository (see [here](https://github.com/O957/fossil-species-references/blob/main/assets/misc/glossary.md)).
  * Online resources relevant to this repository (see [here](https://github.com/O957/fossil-species-references/blob/main/assets/misc/resources.md)).
  * A project roadmap for this repository (see [here](https://github.com/O957/fossil-species-references/blob/main/assets/misc/roadmap.md)).
* The folder `src` contains:
  * The standalone species reference finder script `pbdb_publication_lookup.py` (see [here](https://github.com/O957/fossil-species-references/blob/main/src/pbdb_publication_lookup.py)).
  * The `streamlit` application (which is hosted publicly but can also be locally served) (see [here](https://github.com/O957/fossil-species-references/blob/main/src/streamlit_app.py)).

## Usage

__How can this repository be used?__

This repository supports:

1. Using the online `streamlit` application hosted [here](https://fsr-pbdb.streamlit.app/).
2. Locally hosting the `streamlit` application yourself.
3. Using the command line script yourself.

For (1) and (2):

* Head to <https://docs.astral.sh/uv/getting-started/installation/> to install UV.

For (1):

* `git clone https://github.com/O957/fossil-species-references.git`
* `cd fossil-species-references`
* `cd src`
* `uv run streamlit run streamlit_app.py`

For (2):

* `git clone https://github.com/O957/fossil-species-references.git`
* `cd fossil-species-references`
* `cd src`
* `uv run python3 pbdb_publication_lookup.py --help`


## Contributing

__How may I contribute to this project?__

First look at the Contribution file (see [here](https://github.com/O957/fossil-species-references/blob/main/CONTRIBUTING.md)).

* Making an [issue](https://github.com/O957/fossil-species-references/issues) (comment, feature, bug) in this repository.
* Making a [pull request](https://github.com/O957/fossil-species-references/pulls) to this repository.
* Engaging in a [discussion thread](https://github.com/O957/fossil-species-references/discussions) in this repository.
* Contacting me via email: [my username]+[@]+[pro]+[ton]+[.]+[me]

## Motivation

__Why does this repository exist?__

This repository exists because:

* I kept seeing (Cope, 1874) without the title of the original publication anywhere nearby.
* I found the Paleobiology Database's interface frustrating to use for finding the author information for a single fossil species.


## License Standard Notice

```
Copyright 2025 O957 (Pseudonym)

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```
