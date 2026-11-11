# Contributing to Terminedia

Thanks for helping improve Terminedia. Contributions can include bug fixes, tests, documentation, examples, and new features.

## Before you start

- Check the issue tracker for an existing report or discussion about your change.
- For a substantial change, open an issue first to agree on the scope and expected behavior.
- Keep pull requests focused. If your change fixes an issue, reference it in the pull request description.

## Set up the project

Use a supported Python version and create a virtual environment. From the repository root, install Terminedia and its test dependency:

```sh
python -m pip install -e ".[tests]"
```

To work on image support as well, install the image extra:

```sh
python -m pip install -e ".[tests,images]"
```

## Run the tests

Run the test suite from the repository root:

```sh
python -m pytest -q
```

When changing behavior, add or update tests that cover the change. Some rendering tests can optionally display their output in a terminal with:

```sh
python -m pytest -s --DISPLAY
```

## Open a pull request

- Use a descriptive title and explain the problem and the behavior of the change.
- Include the tests you ran and any relevant platform or terminal details.
- Update documentation or examples when the public API or user-facing behavior changes.
- Do not include unrelated formatting or refactoring changes.