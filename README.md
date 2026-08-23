# job-applicator

![PyPI version](https://img.shields.io/pypi/v/job-applicator.svg)

Job Applicator

* [GitHub](https://github.com/boplk/job-applicator/) | [PyPI](https://pypi.org/project/job-applicator/) | [Documentation](https://boplk.github.io/job-applicator/)
* Created by [Bogdan Pavliuk](https://audrey.feldroy.com/) | GitHub [@bopvlk](https://github.com/bopvlk) | PyPI [@bopvlk](https://pypi.org/user/bopvlk/)
* MIT License

## Features

* TODO

## Documentation

Documentation is built with [Zensical](https://zensical.org/) and deployed to GitHub Pages.

* **Live site:** https://boplk.github.io/job-applicator/
* **Preview locally:** `just docs-serve` (serves at http://localhost:8000)
* **Build:** `just docs-build`

API documentation is auto-generated from docstrings using [mkdocstrings](https://mkdocstrings.github.io/).

Docs deploy automatically on push to `main` via GitHub Actions. To enable this, go to your repo's Settings > Pages and set the source to **GitHub Actions**.

## Development

To set up for local development:

```bash
# Clone your fork
git clone git@github.com:your_username/job-applicator.git
cd job-applicator

# Install in editable mode with live updates
uv tool install --editable .
```

This installs the CLI globally but with live updates - any changes you make to the source code are immediately available when you run `job_applicator`.

Run tests:

```bash
uv run pytest
```

Run quality checks (format, lint, type check, test):

```bash
just qa
```

## Author

job-applicator was created in 2026 by Bogdan Pavliuk.

Built with [Cookiecutter](https://github.com/cookiecutter/cookiecutter) and the [audreyfeldroy/cookiecutter-pypackage](https://github.com/audreyfeldroy/cookiecutter-pypackage) project template.
