# Drishti on AWS: serverless inspection pipeline

An AWS version of Drishti's perception step. Upload an aerial image to S3; a Lambda asks a
vision model on **Amazon Bedrock** for a schema-validated finding and stores it in
**DynamoDB**; an **API Gateway** HTTP API serves the findings and an optional plain-English
summary. Everything is defined as code with the **AWS CDK (Python)**.

```
 image upload ──▶ S3 ──event──▶ Lambda "inspect" ──▶ Bedrock (vision) ──▶ DynamoDB
                                                                              ▲
 client ──▶ API Gateway (HTTP API) ──▶ Lambda "api" ──────────────────────────┘
              GET /findings[?severity=]      (+ Bedrock for the optional narrative)
              GET /summary[?narrative=true]
```

## Services used

| Service | Role |
|---|---|
| Amazon S3 | Image storage: private, encrypted, versioned, HTTPS-only |
| AWS Lambda (Python 3.12) | `inspect` (S3-triggered, concurrency capped at 5 to limit Bedrock spend) and `api` |
| Amazon Bedrock (Converse API) | Vision model reads each image and returns the finding JSON; also writes the summary |
| Amazon DynamoDB | Findings table (on-demand, point-in-time recovery) with a `by_severity` index |
| Amazon API Gateway (HTTP API) | Read-only `GET /findings` and `GET /summary` |
| AWS IAM | Least privilege: each Lambda can invoke **one named model**, never `bedrock:*` or `*` |
| Amazon CloudWatch | Log groups with 1-month retention and an alarm on `inspect` errors |
| AWS CDK | The whole stack as Python code |

## Behaviour worth knowing

- The model's reply is validated against the same rules as the main app's `VLMFinding` schema.
  If it is invalid, the Lambda retries once with a repair prompt. If it still fails, it stores a
  `parse_failed` record instead of guessing, so failures are visible, not silent.
- Unsupported file types and images over Bedrock's 3.75 MB limit are stored as `skipped`
  records, not dropped.
- Re-uploading the same key overwrites its record (idempotent).
- The summary's numbers are always computed from the table; the model only phrases them, and if
  Bedrock is unavailable the counts are still returned.

## Test it (no AWS account needed)

```bash
cd deploy/aws
pip install -r requirements-dev.txt
python -m pytest tests -q     # 23 tests
./synth.sh                    # synthesizes the CloudFormation template and runs cfn-lint
```

## Deploy (needs your AWS account)

```bash
npm install -g aws-cdk
aws configure                           # credentials for your account
# In the Bedrock console, enable access to the model (default: Claude 3 Haiku) in your region.
cdk bootstrap                           # once per account/region
cdk deploy                              # prints BucketName, TableName and ApiUrl
aws s3 cp site.jpg s3://<BucketName>/site.jpg
curl "<ApiUrl>findings?severity=major"
curl "<ApiUrl>summary?narrative=true"
```

Use another model with `cdk deploy -c model_id=<bedrock-model-id>` (it must accept image input
through the Converse API). The stack keeps the bucket and table on `cdk destroy`; delete them by hand.

## What has and has not been verified

| Claim | Status |
|---|---|
| Lambda logic: S3 event handling, validation, retry, idempotency, API filtering, summary | **Tested** (moto emulates S3 and DynamoDB; 23 tests passing) |
| Stack security properties: private encrypted bucket, HTTPS-only, PITR, single-model IAM, GET-only routes | **Tested** by synthesizing the real stack and asserting on the template |
| CloudFormation template validity | **Linted** with `cfn-lint` (no findings; one noisy CDK-generated warning, W3005, is ignored) |
| Real Bedrock responses | **Not tested.** Bedrock is a fake client returning canned replies, so prompt quality and the real model's JSON compliance are unmeasured |
| Deployment to AWS, real latency, real cost | **Not done.** No AWS account was available when this was written |
| Model access and region availability | Depends on your account; the default model ID may need changing |

Treat it as deployment-ready code, not a deployed system, until `cdk deploy` has run and a real
image has gone through.
