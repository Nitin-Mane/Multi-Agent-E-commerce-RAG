"""Create and synchronize the three policy knowledge bases.

The CloudFormation foundation already creates the policy document bucket and
three S3 Vector indexes. This script connects one Bedrock Knowledge Base to
each index, limits its S3 data source to the matching policy prefix, and waits
for the first ingestion job to complete. It is safe to run more than once.
"""

from __future__ import annotations

import os
import time
import uuid

import boto3


REGION = os.environ.get("AWS_REGION", "us-east-1")
PROJECT = os.environ.get("PROJECT_NAME", "udacity-agentcore")
EMBEDDING_MODEL_ARN = (
    f"arn:aws:bedrock:{REGION}::foundation-model/amazon.titan-embed-text-v2:0"
)

bedrock = boto3.client("bedrock-agent", region_name=REGION)
cloudformation = boto3.client("cloudformation", region_name=REGION)
s3vectors = boto3.client("s3vectors", region_name=REGION)


def _exports() -> dict[str, str]:
    """Return this project's CloudFormation exports as a short-name mapping."""
    prefix = f"{PROJECT}-"
    values: dict[str, str] = {}
    for page in cloudformation.get_paginator("list_exports").paginate():
        for export in page.get("Exports", []):
            if export["Name"].startswith(prefix):
                values[export["Name"][len(prefix):]] = export["Value"]
    return values


def _wait_for_kb(kb_id: str, timeout: int = 300) -> dict:
    """Wait for a Knowledge Base to become ACTIVE or fail with its reason."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        kb = bedrock.get_knowledge_base(knowledgeBaseId=kb_id)["knowledgeBase"]
        if kb["status"] == "ACTIVE":
            return kb
        if kb["status"] == "FAILED":
            raise RuntimeError(kb.get("failureReasons", ["Knowledge Base failed"])[0])
        time.sleep(5)
    raise TimeoutError(f"Knowledge Base {kb_id} did not become ACTIVE in time")


def _wait_for_ingestion(kb_id: str, data_source_id: str, job_id: str,
                        timeout: int = 600) -> dict:
    """Wait for one data-source synchronization job to finish."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = bedrock.get_ingestion_job(
            knowledgeBaseId=kb_id,
            dataSourceId=data_source_id,
            ingestionJobId=job_id,
        )["ingestionJob"]
        if job["status"] == "COMPLETE":
            return job
        if job["status"] in {"FAILED", "STOPPED"}:
            raise RuntimeError(
                f"Ingestion for {kb_id} ended as {job['status']}: "
                f"{job.get('failureReasons', [])}"
            )
        time.sleep(10)
    raise TimeoutError(f"Ingestion job {job_id} did not complete in time")


def _existing_knowledge_bases() -> dict[str, dict]:
    """Index existing Knowledge Bases by name for idempotent reruns."""
    found: dict[str, dict] = {}
    paginator = bedrock.get_paginator("list_knowledge_bases")
    for page in paginator.paginate():
        for summary in page.get("knowledgeBaseSummaries", []):
            found[summary["name"]] = summary
    return found


def create_all() -> dict[str, str]:
    """Create, synchronize, and return IDs for Returns, Shipping and Warranty."""
    exports = _exports()
    required = {
        "PolicyBucket", "VectorBucket", "VectorBucketArn", "AgentCoreRoleArn",
        "ReturnsVectorIndex", "ShippingVectorIndex", "WarrantyVectorIndex",
    }
    missing = sorted(required.difference(exports))
    if missing:
        raise RuntimeError(f"Missing CloudFormation exports: {', '.join(missing)}")

    index_arns = {
        item["indexName"]: item["indexArn"]
        for item in s3vectors.list_indexes(
            vectorBucketName=exports["VectorBucket"]
        ).get("indexes", [])
    }
    existing = _existing_knowledge_bases()
    ids: dict[str, str] = {}

    for label, prefix, index_export in (
        ("Returns", "returns", "ReturnsVectorIndex"),
        ("Shipping", "shipping", "ShippingVectorIndex"),
        ("Warranty", "warranty", "WarrantyVectorIndex"),
    ):
        name = f"{PROJECT}-{prefix}-kb"
        index_name = exports[index_export]
        if name in existing:
            kb_id = existing[name]["knowledgeBaseId"]
            print(f"{label}: using existing Knowledge Base {kb_id}")
        else:
            response = bedrock.create_knowledge_base(
                name=name,
                description=f"NovaMart {label.lower()} policy knowledge base.",
                roleArn=exports["AgentCoreRoleArn"],
                knowledgeBaseConfiguration={
                    "type": "VECTOR",
                    "vectorKnowledgeBaseConfiguration": {
                        "embeddingModelArn": EMBEDDING_MODEL_ARN,
                        "embeddingModelConfiguration": {
                            "bedrockEmbeddingModelConfiguration": {
                                "dimensions": 1024,
                                "embeddingDataType": "FLOAT32",
                            }
                        },
                    },
                },
                storageConfiguration={
                    "type": "S3_VECTORS",
                    "s3VectorsConfiguration": {
                        "vectorBucketArn": exports["VectorBucketArn"],
                        "indexArn": index_arns[index_name],
                    },
                },
                clientToken=str(uuid.uuid4()),
            )
            kb_id = response["knowledgeBase"]["knowledgeBaseId"]
            print(f"{label}: created Knowledge Base {kb_id}")

        _wait_for_kb(kb_id)
        sources = bedrock.list_data_sources(
            knowledgeBaseId=kb_id
        ).get("dataSourceSummaries", [])
        data_source_name = f"{PROJECT}-{prefix}-policies"
        match = next((item for item in sources if item["name"] == data_source_name), None)
        if match:
            data_source_id = match["dataSourceId"]
        else:
            source = bedrock.create_data_source(
                knowledgeBaseId=kb_id,
                name=data_source_name,
                description=f"S3 documents for NovaMart {label.lower()} policy.",
                dataDeletionPolicy="RETAIN",
                dataSourceConfiguration={
                    "type": "S3",
                    "s3Configuration": {
                        "bucketArn": f"arn:aws:s3:::{exports['PolicyBucket']}",
                        "inclusionPrefixes": [f"policies/{prefix}/"],
                    },
                },
                vectorIngestionConfiguration={
                    "chunkingConfiguration": {
                        "chunkingStrategy": "FIXED_SIZE",
                        "fixedSizeChunkingConfiguration": {
                            "maxTokens": 300,
                            "overlapPercentage": 20,
                        },
                    }
                },
                clientToken=str(uuid.uuid4()),
            )
            data_source_id = source["dataSource"]["dataSourceId"]

        job = bedrock.start_ingestion_job(
            knowledgeBaseId=kb_id,
            dataSourceId=data_source_id,
            description=f"Initial {label.lower()} policy synchronization.",
            clientToken=str(uuid.uuid4()),
        )["ingestionJob"]
        _wait_for_ingestion(kb_id, data_source_id, job["ingestionJobId"])
        ids[label] = kb_id
        print(f"{label}: synchronized successfully")

    return ids


if __name__ == "__main__":
    for domain, knowledge_base_id in create_all().items():
        print(f"{domain.upper()}_KB_ID={knowledge_base_id}")
