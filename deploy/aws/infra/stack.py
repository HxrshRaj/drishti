"""AWS CDK stack for the Drishti serverless inspection pipeline.

  image upload -> S3 -> Lambda (inspect) -> Amazon Bedrock (vision) -> DynamoDB
                                              API Gateway (HTTP API) -> Lambda (api) -> DynamoDB / Bedrock
"""
from pathlib import Path

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_apigatewayv2 as apigw,
    aws_apigatewayv2_integrations as apigw_int,
    aws_cloudwatch as cw,
    aws_dynamodb as ddb,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_logs as logs,
    aws_s3 as s3,
    aws_s3_notifications as s3n,
)
from constructs import Construct

SRC = str(Path(__file__).resolve().parent.parent / "src")
DEFAULT_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"


class DrishtiAwsStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, model_id: str = DEFAULT_MODEL_ID,
                 **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        bucket = s3.Bucket(
            self, "ImageBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            versioned=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        table = ddb.Table(
            self, "FindingsTable",
            partition_key=ddb.Attribute(name="image_key", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery_specification=ddb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True),
            removal_policy=RemovalPolicy.RETAIN,
        )
        table.add_global_secondary_index(
            index_name="by_severity",
            partition_key=ddb.Attribute(name="severity", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="created_at", type=ddb.AttributeType.NUMBER),
        )

        env = {"TABLE_NAME": table.table_name, "MODEL_ID": model_id}
        common = dict(
            runtime=_lambda.Runtime.PYTHON_3_12,
            code=_lambda.Code.from_asset(SRC),
            environment=env,
        )

        inspect_fn = _lambda.Function(
            self, "InspectFn", handler="inspect_fn.handler.handler",
            timeout=Duration.seconds(60), memory_size=512,
            reserved_concurrent_executions=5,  # caps Bedrock spend if many images land at once
            log_group=logs.LogGroup(self, "InspectLogs", retention=logs.RetentionDays.ONE_MONTH),
            **common)
        api_fn = _lambda.Function(
            self, "ApiFn", handler="api_fn.handler.handler",
            timeout=Duration.seconds(30), memory_size=256,
            log_group=logs.LogGroup(self, "ApiLogs", retention=logs.RetentionDays.ONE_MONTH),
            **common)

        # Least privilege: read images, write findings, invoke ONE named model.
        bucket.grant_read(inspect_fn)
        table.grant_write_data(inspect_fn)
        table.grant_read_data(api_fn)
        model_arns = [
            f"arn:{self.partition}:bedrock:{self.region}::foundation-model/{model_id}",
        ]
        for fn in (inspect_fn, api_fn):
            fn.add_to_role_policy(iam.PolicyStatement(
                actions=["bedrock:InvokeModel"], resources=model_arns))

        bucket.add_event_notification(s3.EventType.OBJECT_CREATED,
                                      s3n.LambdaDestination(inspect_fn))

        http_api = apigw.HttpApi(self, "HttpApi", api_name="drishti-findings")
        integration = apigw_int.HttpLambdaIntegration("ApiIntegration", api_fn)
        http_api.add_routes(path="/findings", methods=[apigw.HttpMethod.GET],
                            integration=integration)
        http_api.add_routes(path="/summary", methods=[apigw.HttpMethod.GET],
                            integration=integration)

        cw.Alarm(
            self, "InspectErrors",
            metric=inspect_fn.metric_errors(period=Duration.minutes(5)),
            threshold=1, evaluation_periods=1,
            comparison_operator=cw.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            alarm_description="Inspect Lambda failed at least once in 5 minutes",
        )

        CfnOutput(self, "BucketName", value=bucket.bucket_name)
        CfnOutput(self, "TableName", value=table.table_name)
        CfnOutput(self, "ApiUrl", value=http_api.url or "")
