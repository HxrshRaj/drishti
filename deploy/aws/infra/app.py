import aws_cdk as cdk

from stack import DrishtiAwsStack

app = cdk.App()
DrishtiAwsStack(
    app, "DrishtiAws",
    model_id=app.node.try_get_context("model_id") or "anthropic.claude-3-haiku-20240307-v1:0",
)
app.synth()
