#!/usr/bin/env bash
# Synthesize the CloudFormation template and lint it. No AWS account needed.
set -euo pipefail
cd "$(dirname "$0")/infra"
python3 - <<'PY'
import aws_cdk as cdk, shutil
from stack import DrishtiAwsStack
app = cdk.App(); DrishtiAwsStack(app, "DrishtiAws"); a = app.synth()
shutil.copy(a.directory + "/DrishtiAws.template.json", "../DrishtiAws.template.json")
PY
cfn-lint ../DrishtiAws.template.json --ignore-checks W3005 && echo "cfn-lint: no findings"
