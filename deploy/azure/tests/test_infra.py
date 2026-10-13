"""Infrastructure tests: run the real Pulumi program with mocked Azure calls (no account needed)
and assert on the resources and security-relevant properties it would create."""
import importlib.util
from pathlib import Path

import pulumi
import pytest

INFRA = Path(__file__).resolve().parent.parent / "infra" / "__main__.py"
CREATED: list[tuple[str, str, dict]] = []


class Mocks(pulumi.runtime.Mocks):
    def new_resource(self, args: pulumi.runtime.MockResourceArgs):
        CREATED.append((args.typ, args.name, dict(args.inputs)))
        outputs = dict(args.inputs)
        outputs.setdefault("name", args.name)  # auto-named resources get a name from Azure
        if args.typ.endswith("web:WebApp"):
            outputs["identity"] = {"principalId": "pid-123", "type": "SystemAssigned"}
            outputs["defaultHostName"] = "drishti-func.azurewebsites.net"
        if args.typ.endswith("cognitiveservices:Account"):
            outputs["properties"] = {**outputs.get("properties", {}),
                                     "endpoint": "https://drishti.openai.azure.com/"}
        if args.typ.endswith("applicationinsights:Component"):
            outputs["connectionString"] = "InstrumentationKey=00000000"
        return [args.name + "_id", outputs]

    def call(self, args: pulumi.runtime.MockCallArgs):
        if "getClientConfig" in args.token:
            return {"subscriptionId": "sub-1", "tenantId": "t", "clientId": "c", "objectId": "o"}
        if "listStorageAccountKeys" in args.token:
            return {"keys": [{"keyName": "key1", "value": "k", "permissions": "FULL"}]}
        return {}


@pytest.fixture(scope="module")
def resources():
    pulumi.runtime.set_mocks(Mocks(), project="drishti-azure", stack="test", preview=False)

    @pulumi.runtime.test  # runs the program, then waits for all (async) resource registrations
    def load():
        spec = importlib.util.spec_from_file_location("infra_main", INFRA)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

    load()
    return CREATED


def _of(resources, suffix):
    return [(n, i) for t, n, i in resources if t.endswith(suffix)]


def test_storage_is_private_https_only_tls12(resources):
    (_, s), = _of(resources, "storage:StorageAccount")
    assert s["enableHttpsTrafficOnly"] is True
    assert s["minimumTlsVersion"] == "TLS1_2"
    assert s["allowBlobPublicAccess"] is False
    (_, c), = _of(resources, "storage:BlobContainer")
    assert c["publicAccess"] == "None" and c["containerName"] == "images"
    (_, t), = _of(resources, "storage:Table")
    assert t["tableName"] == "findings"


def test_openai_has_key_auth_disabled_and_a_vision_model(resources):
    (_, a), = _of(resources, "cognitiveservices:Account")
    assert a["kind"] == "OpenAI" and a["properties"]["disableLocalAuth"] is True
    (_, d), = _of(resources, "cognitiveservices:Deployment")
    assert d["properties"]["model"]["name"] == "gpt-4o-mini"


def test_function_app_is_https_only_with_managed_identity(resources):
    (_, app), = _of(resources, "web:WebApp")
    assert app["httpsOnly"] is True and app["identity"]["type"] == "SystemAssigned"
    assert app["siteConfig"]["minTlsVersion"] == "1.2" and app["siteConfig"]["ftpsState"] == "Disabled"
    assert app["siteConfig"]["linuxFxVersion"] == "PYTHON|3.12"
    names = {s["name"] for s in app["siteConfig"]["appSettings"]}
    assert {"AzureWebJobsStorage", "IMAGES", "TABLE_ENDPOINT", "OPENAI_ENDPOINT",
            "OPENAI_DEPLOYMENT"} <= names


def test_role_assignments_are_two_specific_built_in_roles(resources):
    roles = _of(resources, "authorization:RoleAssignment")
    assert len(roles) == 2
    texts = " ".join(str(i["roleDefinitionId"]) for _, i in roles)
    assert "0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3" in texts  # Storage Table Data Contributor
    assert "5e0bd9bd-7b93-4f28-af87-19fc36ad61bd" in texts  # Cognitive Services OpenAI User
    assert all(i["principalType"] == "ServicePrincipal" for _, i in roles)
