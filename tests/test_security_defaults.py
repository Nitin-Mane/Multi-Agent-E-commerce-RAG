"""Focused tests for privacy-preserving and authenticated defaults."""

from __future__ import annotations

import json
import hashlib
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import agent_observability  # noqa: E402
import agent_orchestrator  # noqa: E402
from infrastructure import cleanup  # noqa: E402


class ObservabilityPrivacyTests(unittest.TestCase):
    def test_trace_omits_raw_customer_session_and_request_by_default(self):
        with patch.dict(
            os.environ,
            {
                "AGENT_TRACING_ENABLED": "true",
                "AGENT_TRACE_SAMPLING_RATE": "0",
                "AGENT_OBSERVABILITY_INCLUDE_SENSITIVE": "false",
            },
            clear=False,
        ):
            tracer = agent_observability.AgentTracer()
            with self.assertLogs("novamart.observability", level="INFO") as captured:
                with tracer.trace_request(
                    "private-session-id",
                    "private-customer-id",
                    "private request text",
                ) as root:
                    trace_document = json.dumps(root.to_doc())

        emitted_logs = "\n".join(captured.output)

        for secret in (
            "private-session-id",
            "private-customer-id",
            "private request text",
        ):
            self.assertNotIn(secret, trace_document)
            self.assertNotIn(secret, emitted_logs)

    def test_identifier_pseudonym_is_not_derived_from_public_project_data(self):
        customer_id = "CUST-001"
        public_digest = hashlib.sha256(
            f"{agent_observability.config.PROJECT_NAME}:customer:{customer_id}".encode()
        ).hexdigest()[:16]
        self.assertNotEqual(
            agent_observability._identifier_hash("customer", customer_id),
            public_digest,
        )

    def test_tool_argument_summary_never_contains_values(self):
        summary = agent_observability._short_args(
            {
                "customer_id": "private-customer-id",
                "query": "private request text",
                "order_id": "private-order-id",
            }
        )
        self.assertIn("customer_id", summary)
        self.assertIn("query", summary)
        self.assertNotIn("private-", summary)


class GatewaySecurityTests(unittest.TestCase):
    def test_optional_gateway_requires_iam_authorization(self):
        source = (ROOT / "src" / "agent_orchestrator.py").read_text(encoding="utf-8")
        self.assertIn("authorizerType='AWS_IAM'", source)
        self.assertNotIn("authorizerType='NONE'", source)

    def test_gateway_role_policy_is_limited_to_resolved_functions(self):
        class NoSuchEntity(Exception):
            pass

        class FakeIam:
            exceptions = SimpleNamespace(NoSuchEntityException=NoSuchEntity)

            def __init__(self):
                self.policy = None

            def get_role(self, **_kwargs):
                raise NoSuchEntity()

            def create_role(self, **_kwargs):
                return {"Role": {"Arn": "arn:aws:iam::<AWS_ACCOUNT_ID>:role/test"}}

            def put_role_policy(self, **kwargs):
                self.policy = json.loads(kwargs["PolicyDocument"])

        iam = FakeIam()
        function_arns = [
            "arn:aws:lambda:us-east-1:<AWS_ACCOUNT_ID>:function:orders",
            "arn:aws:lambda:us-east-1:<AWS_ACCOUNT_ID>:function:customers",
        ]
        with patch.object(agent_orchestrator.boto3, "client", return_value=iam):
            role_arn = agent_orchestrator._gw_get_or_create_role(
                "novamart-gateway-test",
                function_arns,
            )

        self.assertEqual(role_arn, "arn:aws:iam::<AWS_ACCOUNT_ID>:role/test")
        statement = iam.policy["Statement"][0]
        self.assertEqual(statement["Action"], "lambda:InvokeFunction")
        self.assertEqual(statement["Resource"], sorted(function_arns))

    def test_legacy_unauthenticated_gateway_is_not_reused(self):
        class Conflict(Exception):
            pass

        class FakeAgentCore:
            exceptions = SimpleNamespace(ConflictException=Conflict)

            def create_gateway(self, **_kwargs):
                raise Conflict()

            def list_gateways(self):
                return {"items": [{"name": "test-gateway", "gatewayId": "gateway-id"}]}

            def get_gateway(self, **_kwargs):
                return {"authorizerType": "NONE", "status": "READY"}

        with self.assertRaisesRegex(RuntimeError, "not IAM-authorized"):
            agent_orchestrator._gw_get_or_create(
                FakeAgentCore(),
                "test-gateway",
                "arn:aws:iam::<AWS_ACCOUNT_ID>:role/test",
                "test instructions",
            )

    def test_existing_gateway_must_use_the_requested_dedicated_role(self):
        class Conflict(Exception):
            pass

        class FakeAgentCore:
            exceptions = SimpleNamespace(ConflictException=Conflict)

            def create_gateway(self, **_kwargs):
                raise Conflict()

            def list_gateways(self):
                return {"items": [{"name": "test-gateway", "gatewayId": "gateway-id"}]}

            def get_gateway(self, **_kwargs):
                return {
                    "authorizerType": "AWS_IAM",
                    "roleArn": "arn:aws:iam::<AWS_ACCOUNT_ID>:role/legacy-broad",
                    "status": "READY",
                }

        with self.assertRaisesRegex(RuntimeError, "dedicated execution role"):
            agent_orchestrator._gw_get_or_create(
                FakeAgentCore(),
                "test-gateway",
                "arn:aws:iam::<AWS_ACCOUNT_ID>:role/novamart-gateway-dedicated",
                "test instructions",
            )

    def test_preexisting_role_with_unrelated_permissions_is_rejected(self):
        class NoSuchEntity(Exception):
            pass

        class FakeIam:
            exceptions = SimpleNamespace(NoSuchEntityException=NoSuchEntity)

            def get_role(self, **_kwargs):
                return {
                    "Role": {
                        "Arn": "arn:aws:iam::<AWS_ACCOUNT_ID>:role/novamart-gateway-test",
                        "AssumeRolePolicyDocument": {},
                    }
                }

            def put_role_policy(self, **_kwargs):
                pass

        with patch.object(agent_orchestrator.boto3, "client", return_value=FakeIam()):
            with self.assertRaisesRegex(RuntimeError, "not a dedicated NovaMart role"):
                agent_orchestrator._gw_get_or_create_role(
                    "novamart-gateway-test",
                    ["arn:aws:lambda:us-east-1:<AWS_ACCOUNT_ID>:function:orders"],
                )

    def test_conflicting_gateway_target_must_match_expected_configuration(self):
        class Conflict(Exception):
            pass

        class FakeAgentCore:
            exceptions = SimpleNamespace(ConflictException=Conflict)

            def create_gateway_target(self, **_kwargs):
                raise Conflict()

            def list_gateway_targets(self, **_kwargs):
                return {"items": [{"name": "orders-api", "targetId": "target-id"}]}

            def get_gateway_target(self, **_kwargs):
                return {
                    "name": "orders-api",
                    "description": "stale target",
                    "targetConfiguration": {
                        "mcp": {"lambda": {"lambdaArn": "arn:aws:lambda:other"}}
                    },
                    "credentialProviderConfigurations": [],
                }

        target = {
            "name": "orders-api",
            "description": "Order lookup",
            "tool_name": "check_order_status",
            "tool_description": "Check an order",
            "param_name": "order_id",
            "param_desc": "Order ID",
        }
        with self.assertRaisesRegex(RuntimeError, "does not match"):
            agent_orchestrator._gw_create_target(
                FakeAgentCore(),
                "gateway-id",
                target,
                "arn:aws:lambda:us-east-1:<AWS_ACCOUNT_ID>:function:orders",
            )


class CleanupSafetyTests(unittest.TestCase):
    def test_memory_cleanup_requires_the_exact_project_configuration(self):
        class FakeAgentCore:
            def __init__(self, description):
                self.description = description

            def get_memory(self, memoryId):
                return {
                    "memory": {
                        "id": memoryId,
                        "name": cleanup.config.MEMORY_NAME,
                        "description": self.description,
                        "eventExpiryDuration": 7,
                        "strategies": [{
                            "type": "SUMMARIZATION",
                            "name": "SessionSummary",
                            "namespaces": ["/summaries/{actorId}/{sessionId}"],
                        }],
                    }
                }

        memory_id = f"{cleanup.config.MEMORY_NAME}-generated"
        self.assertTrue(
            cleanup._is_project_memory(
                FakeAgentCore("Seven-day session summaries for NovaMart customer support."),
                memory_id,
            )
        )
        self.assertFalse(
            cleanup._is_project_memory(FakeAgentCore("unrelated memory"), memory_id)
        )

    def test_gateway_cleanup_names_are_derived_from_the_configured_stack(self):
        class FakeCloudFormation:
            def describe_stacks(self, **_kwargs):
                return {
                    "Stacks": [{
                        "StackId": (
                            "arn:aws:cloudformation:us-east-1:<AWS_ACCOUNT_ID>:stack/"
                            "udacity-agentcore/abcd1234-1111-2222-3333-aaaabbbbcccc"
                        )
                    }]
                }

        self.assertEqual(
            cleanup._project_gateway_names(FakeCloudFormation()),
            {
                "novamart-support-abcd1234",
                f"novamart-support-{cleanup.PREFIX}",
            },
        )

    def test_gateway_role_cleanup_fails_closed_on_unrelated_policies(self):
        class FakeIam:
            def get_role(self, **_kwargs):
                return {
                    "Role": {
                        "Tags": [
                            {"Key": "ManagedBy", "Value": "NovaMart"},
                            {"Key": "Project", "Value": cleanup.PREFIX},
                            {"Key": "TargetDigest", "Value": "0" * 64},
                        ]
                    }
                }

            def list_role_policies(self, **_kwargs):
                return {
                    "PolicyNames": [
                        cleanup.GATEWAY_ROLE_POLICY,
                        "UnrelatedPolicy",
                    ]
                }

            def list_attached_role_policies(self, **_kwargs):
                return {"AttachedPolicies": []}

        self.assertFalse(
            cleanup._gateway_role_cleanup_state(
                FakeIam(),
                "novamart-gateway-test",
            )
        )

    def test_gateway_role_cleanup_rejects_resources_not_matching_target_digest(self):
        class FakeIam:
            def get_role(self, **_kwargs):
                return {
                    "Role": {
                        "AssumeRolePolicyDocument": cleanup.GATEWAY_TRUST_POLICY,
                        "Tags": [
                            {"Key": "ManagedBy", "Value": "NovaMart"},
                            {"Key": "Project", "Value": cleanup.PREFIX},
                            {"Key": "TargetDigest", "Value": "0" * 64},
                        ],
                    }
                }

            def list_role_policies(self, **_kwargs):
                return {"PolicyNames": [cleanup.GATEWAY_ROLE_POLICY]}

            def list_attached_role_policies(self, **_kwargs):
                return {"AttachedPolicies": []}

            def get_role_policy(self, **_kwargs):
                return {
                    "PolicyDocument": {
                        "Version": "2012-10-17",
                        "Statement": [{
                            "Effect": "Allow",
                            "Action": "lambda:InvokeFunction",
                            "Resource": (
                                "arn:aws:lambda:us-east-1:<AWS_ACCOUNT_ID>:"
                                "function:unrelated-production-function"
                            ),
                        }],
                    }
                }

        self.assertIsNone(
            cleanup._gateway_role_cleanup_state(
                FakeIam(),
                "novamart-gateway-test",
            )
        )

    def test_lambda_arn_validation_is_partition_aware_and_rejects_wildcards(self):
        self.assertTrue(
            cleanup._is_concrete_lambda_arn(
                "arn:aws-us-gov:lambda:us-gov-west-1:<AWS_ACCOUNT_ID>:function:orders"
            )
        )
        self.assertFalse(
            cleanup._is_concrete_lambda_arn(
                "arn:aws:lambda:us-east-1:<AWS_ACCOUNT_ID>:function:*"
            )
        )

    def test_gateway_role_cleanup_can_retry_after_policy_was_deleted(self):
        class FakeIam:
            def get_role(self, **_kwargs):
                return {
                    "Role": {
                        "AssumeRolePolicyDocument": cleanup.GATEWAY_TRUST_POLICY,
                        "Tags": [
                            {"Key": "ManagedBy", "Value": "NovaMart"},
                            {"Key": "Project", "Value": cleanup.PREFIX},
                            {"Key": "TargetDigest", "Value": "0" * 64},
                        ],
                    }
                }

            def list_role_policies(self, **_kwargs):
                return {"PolicyNames": []}

            def list_attached_role_policies(self, **_kwargs):
                return {"AttachedPolicies": []}

        self.assertIs(
            cleanup._gateway_role_cleanup_state(
                FakeIam(),
                "novamart-gateway-test",
            ),
            False,
        )


if __name__ == "__main__":
    unittest.main()
