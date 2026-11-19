# .github/

GitHub settings for the repo.

| File | What it does |
|---|---|
| [workflows/ci.yml](workflows/ci.yml) | On every push and pull request: install with uv on Python 3.10, 3.12, and 3.13, run ruff, run the tests, check that the CSV matches the generator, smoke-test the demo client, and run a gitleaks secret scan. |
