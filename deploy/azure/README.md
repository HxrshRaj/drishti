# Drishti on Azure: serverless inspection pipeline

The Azure counterpart of [`../aws/`](../aws): upload an aerial image to Blob Storage; an
**Azure Function** reads it, asks a vision model on **Azure OpenAI** for a schema-validated
finding, and stores it in **Table Storage**. The same Function App serves a read-only HTTP API.
Infrastructure is code, written with **Pulumi (Python)**.

```
 image ──▶ Blob container "images" ──blob trigger──▶ Function "inspect_image"
                                                        │  Azure OpenAI (gpt-4o-mini, vision)
                                                        ▼
 client ──▶ GET /api/findings, /api/summary ──▶ Table Storage "findings"
```

## Services used

| Azure service | Role |
|---|---|
| Blob Storage | Image intake: private container, HTTPS only, TLS 1.2, no public access |
| Azure Functions (Python 3.12, Linux Consumption) | `inspect_image` (blob trigger) and the HTTP routes `findings` and `summary` |
| Azure OpenAI | Vision model returns the finding JSON and writes the optional summary; key auth is **disabled**, only Entra ID can call it |
| Table Storage | Findings store (upsert by image name, so re-uploads overwrite) |
| Managed identity + RBAC | Function App identity gets exactly two built-in roles: *Storage Table Data Contributor* and *Cognitive Services OpenAI User* |
| Application Insights | Logs and traces |
| Pulumi (Python) | All of the above as code |

## Behaviour worth knowing

- The model's reply is validated against the same rules as the main app's `VLMFinding`; one retry
  with a repair prompt, then a `parse_failed` record instead of a guess.
- Unsupported types and oversized images are stored as `skipped` records, not dropped.
- Summary counts always come from the table; the model only phrases them.
- Table keys can't contain `/ \ # ?`, so the row key is the URL-safe base64 of the blob name.

## Test it (no Azure account needed)

```bash
cd deploy/azure
pip install -r requirements-dev.txt
npm install -g azurite && azurite --silent --location .azurite --skipApiVersionCheck &   # local Azure Storage emulator
python -m pytest tests -q        # 24 tests
```

## Deploy (needs your Azure subscription)

```bash
az login
pulumi login --local && pulumi stack init dev
pulumi config set azure-native:location eastus      # pick a region that offers your Azure OpenAI model
pulumi up                                           # creates everything and prints the API host
cd src && func azure functionapp publish <function_app_name> --python
```

Azure OpenAI needs an approved subscription and model availability in the chosen region; set
`openaiModel` / `openaiModelVersion` with `pulumi config set` if the default is not offered.
The Function App reads its storage connection string from app settings (required by the Functions
host); a Key Vault reference would be the next hardening step.

## What has and has not been verified

| Claim | Status |
|---|---|
| Findings storage: keys, upsert, filtering, summaries | **Tested against a real Table Storage API** (Azurite emulator) |
| Blob upload then process flow | **Tested** on Azurite Blob Storage; the blob *trigger itself* is not emulated, the handler is called directly |
| Function registration (blob trigger path, HTTP routes) and HTTP responses | **Tested** with the Azure Functions Python library |
| Infrastructure: private HTTPS-only storage, key auth off on OpenAI, managed identity, two specific roles | **Tested** by running the real Pulumi program against mocked Azure calls |
| Real Azure OpenAI responses | **Not tested.** The model is a fake client returning canned replies, so prompt quality is unmeasured |
| `pulumi up` against real Azure, real cold-start, latency and cost | **Not done.** No Azure subscription was available when this was written |

Treat it as deployment-ready code, not a deployed system, until it has been deployed and a real
image has gone through.
