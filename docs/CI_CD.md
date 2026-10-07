# CI/CD Guide

## Continuous integration

The `Validate` workflow runs on every push and pull request to `main`:

1. Install Python runtime and development dependencies.
2. Lint and compile the Python source.
3. Validate that tracked files contain no common AWS credentials, literal account IDs, private runtime configs, or generated build directories.
4. Run the credential-free Task 2 rubric suite.
5. Install, build, and test the AgentCore CDK project with Node.js 20.

No AWS credentials are available to this workflow.

## Continuous delivery

The `Deploy foundation stack` workflow is deliberately manual because it creates chargeable AWS resources. It uses GitHub's OpenID Connect token to assume a short-lived AWS role and never stores an AWS access key in the repository.

### One-time GitHub/AWS setup

1. In the target AWS account, create an IAM OIDC provider for GitHub Actions and a role whose trust policy is restricted to this repository and the `aws-course` environment.
2. Grant that role only the permissions required to validate and deploy `infrastructure/starter_stack.yaml`.
3. Create a protected GitHub Environment named `aws-course`; enable required reviewers.
4. Add the role ARN as the repository variable `AWS_ROLE_ARN`. Do not save access keys as secrets.

### Run delivery

Open **Actions → Deploy foundation stack → Run workflow**, verify the target region and stack name, and approve the protected environment. The workflow validates the template, deploys the stack, and prints stack outputs.

## Intentional manual boundary

Knowledge-base creation/data synchronization, Bedrock model entitlements, Guardrail/AgentCore Runtime deployment, and live model validation remain manual. These steps depend on account-specific service access, can incur cost, and should not be triggered by an unreviewed code push. Follow `docs/DEPLOYMENT.md` after the foundation workflow succeeds.
