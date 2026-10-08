# Security Policy

## Reporting a vulnerability

Please do not disclose security vulnerabilities in a public issue. Use GitHub's private vulnerability reporting feature for this repository, or contact the repository owner privately through their GitHub profile.

Include the affected file or component, reproduction conditions, potential impact, and any suggested remediation. Do not include live credentials, customer data, or exploitable cloud-resource identifiers in the report.

## Credential handling

This project expects AWS authentication through the standard AWS credential chain. Use short-lived credentials, IAM Identity Center, or an approved role. Never commit access keys, secret keys, session tokens, passwords, federation URLs, or generated credential files.

The checked-in `.env` contains only the non-secret Udacity sandbox account and deployed resource identifiers required by the project submission rubric. These identifiers are intentionally disclosed for evaluator traceability and do not authenticate a caller. `agentcore/agentcore.json`, `agentcore/aws-targets.json`, and all AWS credentials remain ignored. Temporary course credentials must be supplied through the standard credential chain and must never be copied into `.env`.

## Supported version

Security fixes are applied to the current `main` branch. This educational project does not maintain separate long-term-support releases.

## Dependency note

As of October 7, 2026, `npm audit --omit=dev` reports one high-severity denial-of-service advisory in a `brace-expansion` copy bundled inside `aws-cdk-lib`. npm cannot update that bundled copy independently. The affected dependency is used by the local CDK deployment toolchain, not by the Python AgentCore runtime. Upgrade the pinned AgentCore/CDK release when AWS publishes a compatible build containing the patched dependency, and rerun the CDK tests before deployment.
