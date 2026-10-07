# Contributing

Thank you for improving this project. Keep changes focused, readable, and safe for a public repository.

## Development workflow

1. Create a feature branch from `main`.
2. Use Python 3.12 and install `requirements-dev.txt` in a virtual environment.
3. Copy the example configuration only when local AWS testing is needed.
4. Add or update tests alongside behavior changes.
5. Run the credential-free validation commands from the README.
6. Review the staged diff for secrets and generated artifacts before opening a pull request.

## Code quality

- Prefer small functions with clear names and focused responsibilities.
- Add comments where they explain intent, constraints, or a non-obvious AWS behavior.
- Avoid comments that merely repeat the code.
- Handle service errors with actionable context without exposing request payloads or credentials.
- Keep deployment-specific values in ignored local configuration.

## Pull requests

Describe the problem, the chosen approach, the validation performed, and any AWS resources or costs involved. Never attach unredacted console screenshots, credentials, account IDs, or private runtime responses.
