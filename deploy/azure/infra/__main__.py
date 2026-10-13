"""Pulumi (Python) program for the Drishti Azure pipeline.

Blob container `images` -> Function App (blob trigger) -> Azure OpenAI (vision) -> Table Storage,
plus an HTTP API on the same Function App. The Function App uses a system-assigned managed
identity with least-privilege roles for Table Storage and Azure OpenAI.
"""
import pulumi
import pulumi_azure_native as az

cfg = pulumi.Config()
location = cfg.get("location") or "eastus"
openai_model = cfg.get("openaiModel") or "gpt-4o-mini"
openai_model_version = cfg.get("openaiModelVersion") or "2024-07-18"

# Built-in Azure role definition IDs (the same in every tenant).
ROLE_TABLE_DATA_CONTRIBUTOR = "0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3"
ROLE_COGNITIVE_OPENAI_USER = "5e0bd9bd-7b93-4f28-af87-19fc36ad61bd"

client = az.authorization.get_client_config()
rg = az.resources.ResourceGroup("drishti-rg", location=location)

storage = az.storage.StorageAccount(
    "drishtistore",
    resource_group_name=rg.name,
    kind="StorageV2",
    sku=az.storage.SkuArgs(name="Standard_LRS"),
    enable_https_traffic_only=True,
    minimum_tls_version="TLS1_2",
    allow_blob_public_access=False,
)
images = az.storage.BlobContainer(
    "images", account_name=storage.name, resource_group_name=rg.name,
    container_name="images", public_access="None")
table = az.storage.Table(
    "findings", account_name=storage.name, resource_group_name=rg.name, table_name="findings")

keys = az.storage.list_storage_account_keys_output(
    account_name=storage.name, resource_group_name=rg.name)
storage_conn = pulumi.Output.all(storage.name, keys.keys[0].value).apply(
    lambda a: f"DefaultEndpointsProtocol=https;AccountName={a[0]};AccountKey={a[1]};"
              f"EndpointSuffix=core.windows.net")

openai = az.cognitiveservices.Account(
    "drishti-openai",
    resource_group_name=rg.name,
    kind="OpenAI",
    sku=az.cognitiveservices.SkuArgs(name="S0"),
    properties=az.cognitiveservices.AccountPropertiesArgs(
        custom_sub_domain_name=pulumi.Output.concat("drishti-", rg.name),
        public_network_access="Enabled",
        disable_local_auth=True),  # keys disabled: only Entra ID (managed identity) can call it
)
deployment = az.cognitiveservices.Deployment(
    "vision-deployment",
    resource_group_name=rg.name,
    account_name=openai.name,
    deployment_name=openai_model,
    properties=az.cognitiveservices.DeploymentPropertiesArgs(
        model=az.cognitiveservices.DeploymentModelArgs(
            format="OpenAI", name=openai_model, version=openai_model_version)),
    sku=az.cognitiveservices.SkuArgs(name="Standard", capacity=10),
)

insights = az.applicationinsights.Component(
    "drishti-insights", resource_group_name=rg.name, kind="web",
    application_type="web", flow_type="Bluefield")
plan = az.web.AppServicePlan(
    "drishti-plan", resource_group_name=rg.name, kind="functionapp", reserved=True,
    sku=az.web.SkuDescriptionArgs(name="Y1", tier="Dynamic"))

app = az.web.WebApp(
    "drishti-func",
    resource_group_name=rg.name,
    kind="functionapp,linux",
    server_farm_id=plan.id,
    https_only=True,
    identity=az.web.ManagedServiceIdentityArgs(type="SystemAssigned"),
    site_config=az.web.SiteConfigArgs(
        linux_fx_version="PYTHON|3.12",
        min_tls_version="1.2",
        ftps_state="Disabled",
        app_settings=[
            az.web.NameValuePairArgs(name="FUNCTIONS_WORKER_RUNTIME", value="python"),
            az.web.NameValuePairArgs(name="FUNCTIONS_EXTENSION_VERSION", value="~4"),
            az.web.NameValuePairArgs(name="AzureWebJobsStorage", value=storage_conn),
            az.web.NameValuePairArgs(name="IMAGES", value=storage_conn),
            az.web.NameValuePairArgs(
                name="TABLE_ENDPOINT",
                value=pulumi.Output.concat("https://", storage.name, ".table.core.windows.net")),
            az.web.NameValuePairArgs(name="TABLE_NAME", value="findings"),
            az.web.NameValuePairArgs(name="OPENAI_ENDPOINT", value=openai.properties.endpoint),
            az.web.NameValuePairArgs(name="OPENAI_DEPLOYMENT", value=openai_model),
            az.web.NameValuePairArgs(
                name="APPLICATIONINSIGHTS_CONNECTION_STRING",
                value=insights.connection_string),
        ],
    ),
)


def _assign(name: str, scope, role_id: str):
    return az.authorization.RoleAssignment(
        name,
        scope=scope,
        principal_id=app.identity.principal_id,
        principal_type="ServicePrincipal",
        role_definition_id=pulumi.Output.concat(
            "/subscriptions/", client.subscription_id,
            "/providers/Microsoft.Authorization/roleDefinitions/", role_id),
    )


_assign("table-access", storage.id, ROLE_TABLE_DATA_CONTRIBUTOR)
_assign("openai-access", openai.id, ROLE_COGNITIVE_OPENAI_USER)

pulumi.export("function_app", app.default_host_name)
pulumi.export("storage_account", storage.name)
pulumi.export("findings_url", pulumi.Output.concat("https://", app.default_host_name, "/api/findings"))
