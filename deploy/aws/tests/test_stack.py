"""Infrastructure tests: synthesize the real CDK stack and assert security-relevant properties."""
import json

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template

from stack import DrishtiAwsStack


@pytest.fixture(scope="module")
def template():
    app = cdk.App()
    stack = DrishtiAwsStack(app, "T", env=cdk.Environment(account="123456789012", region="us-east-1"))
    return Template.from_stack(stack)


def test_bucket_is_private_encrypted_versioned(template):
    template.has_resource_properties("AWS::S3::Bucket", {
        "PublicAccessBlockConfiguration": {
            "BlockPublicAcls": True, "BlockPublicPolicy": True,
            "IgnorePublicAcls": True, "RestrictPublicBuckets": True},
        "BucketEncryption": Match.any_value(),
        "VersioningConfiguration": {"Status": "Enabled"}})
    template.has_resource_properties("AWS::S3::BucketPolicy", {
        "PolicyDocument": {"Statement": Match.array_with([
            Match.object_like({"Effect": "Deny",
                               "Condition": {"Bool": {"aws:SecureTransport": "false"}}})])}})


def test_table_on_demand_with_pitr_and_severity_index(template):
    template.has_resource_properties("AWS::DynamoDB::Table", {
        "BillingMode": "PAY_PER_REQUEST",
        "PointInTimeRecoverySpecification": {"PointInTimeRecoveryEnabled": True},
        "GlobalSecondaryIndexes": [Match.object_like({"IndexName": "by_severity"})]})


def test_bedrock_permission_is_one_named_model_never_wildcard(template):
    policies = template.find_resources("AWS::IAM::Policy")
    bedrock = [s for p in policies.values() for s in p["Properties"]["PolicyDocument"]["Statement"]
               if s["Action"] == "bedrock:InvokeModel"]
    assert len(bedrock) == 2
    for s in bedrock:
        res = json.dumps(s["Resource"])  # an intrinsic Fn::Join, so compare its text
        assert "*" not in res and "claude-3-haiku" in res


def test_inspect_lambda_has_concurrency_cap_and_alarm(template):
    template.has_resource_properties("AWS::Lambda::Function", {
        "Handler": "inspect_fn.handler.handler", "ReservedConcurrentExecutions": 5,
        "Runtime": "python3.12"})
    template.resource_count_is("AWS::CloudWatch::Alarm", 1)


def test_http_api_exposes_only_get_routes(template):
    routes = template.find_resources("AWS::ApiGatewayV2::Route")
    assert sorted(r["Properties"]["RouteKey"] for r in routes.values()) == [
        "GET /findings", "GET /summary"]
