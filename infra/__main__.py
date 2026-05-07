from __future__ import annotations

import uuid

import pulumi
from pulumi import Config, Output, ResourceOptions
from pulumi_azure_native import (
    app,
    authorization,
    containerregistry,
    insights,
    keyvault,
    managedidentity,
    operationalinsights,
    resources,
    storage,
)
from pulumi_azure_native.authorization import RoleAssignment


config = Config()
env_name = config.get("environment") or "dev"
location = config.get("location") or "eastus"
region_abbr = config.get("regionAbbr") or "eus"
sequence = config.get("sequence") or "001"
app_version = config.get("appVersion") or "0.2.2"
image_tag = config.get("containerImageTag") or app_version
image_name = f"aari-nexus-azure:{image_tag}"

owner = config.get("owner") or "aari"
cost_center = config.get("costCenter") or "r-and-d"
data_classification = config.get("dataClassification") or "internal"
project = config.get("project") or "aari-nexus"
workload = config.get("workload") or "telegram-bot-backend"

telegram_bot_token = config.require_secret("telegramBotToken")
azure_openai_endpoint = config.require_secret("azureOpenAiEndpoint")
azure_openai_api_key = config.require_secret("azureOpenAiApiKey")
azure_openai_deployment = config.require_secret("azureOpenAiDeployment")
azure_openai_api_version = config.require_secret("azureOpenAiApiVersion")

client_config = authorization.get_client_config()


def resource_name(prefix: str) -> str:
    return f"{prefix}-aari-nexus-{env_name}-{region_abbr}-{sequence}"


def compact_name(prefix: str) -> str:
    return f"{prefix}aarinexus{env_name}{region_abbr}{sequence}"


def role_definition_id(role_guid: str) -> Output[str]:
    return Output.concat(
        "/subscriptions/",
        client_config.subscription_id,
        "/providers/Microsoft.Authorization/roleDefinitions/",
        role_guid,
    )


def deterministic_guid(*parts: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "::".join(parts)))


tags = {
    "org": "aari",
    "workload": workload,
    "environment": env_name,
    "owner": owner,
    "costCenter": cost_center,
    "dataClassification": data_classification,
    "managedBy": "pulumi",
    "project": project,
}

acr_pull_role = "7f951dda-4ed3-4680-a7ca-43fe172d538d"
key_vault_secrets_user_role = "4633458b-17de-408a-b874-0445c86b69e6"
storage_blob_data_contributor_role = "ba92f5b4-2d11-453d-a403-e96b0029c9fe"

resource_group = resources.ResourceGroup(
    resource_name("rg"),
    resource_group_name=resource_name("rg"),
    location=location,
    tags=tags,
)

workspace = operationalinsights.Workspace(
    resource_name("law"),
    workspace_name=resource_name("law"),
    resource_group_name=resource_group.name,
    location=location,
    retention_in_days=30,
    sku=operationalinsights.WorkspaceSkuArgs(name="PerGB2018"),
    tags=tags,
)

app_insights = insights.Component(
    resource_name("appi"),
    resource_name_=resource_name("appi"),
    resource_group_name=resource_group.name,
    location=location,
    application_type="web",
    kind="web",
    workspace_resource_id=workspace.id,
    tags=tags,
)

acr = containerregistry.Registry(
    compact_name("acr"),
    registry_name=compact_name("acr"),
    resource_group_name=resource_group.name,
    location=location,
    admin_user_enabled=False,
    sku=containerregistry.SkuArgs(name="Basic"),
    tags=tags,
)

storage_account = storage.StorageAccount(
    compact_name("st"),
    account_name=compact_name("st"),
    resource_group_name=resource_group.name,
    location=location,
    sku=storage.SkuArgs(name=storage.SkuName.STANDARD_LRS),
    kind=storage.Kind.STORAGE_V2,
    allow_blob_public_access=False,
    allow_shared_key_access=False,
    minimum_tls_version=storage.MinimumTlsVersion.TLS1_2,
    enable_https_traffic_only=True,
    tags=tags,
)

blob_container = storage.BlobContainer(
    "artifacts",
    resource_group_name=resource_group.name,
    account_name=storage_account.name,
    container_name="artifacts",
    public_access=storage.PublicAccess.NONE,
)

identity = managedidentity.UserAssignedIdentity(
    resource_name("id"),
    resource_group_name=resource_group.name,
    resource_name_=resource_name("id"),
    location=location,
    tags=tags,
)

vault = keyvault.Vault(
    resource_name("k"),
    vault_name=resource_name("k"),
    resource_group_name=resource_group.name,
    location=location,
    properties=keyvault.VaultPropertiesArgs(
        tenant_id=client_config.tenant_id,
        sku=keyvault.SkuArgs(family="A", name=keyvault.SkuName.STANDARD),
        enable_rbac_authorization=True,
        access_policies=[],
        public_network_access="Enabled",
    ),
    tags=tags,
)

telegram_secret = keyvault.Secret(
    "telegramBotTokenSecret",
    resource_group_name=resource_group.name,
    vault_name=vault.name,
    secret_name="telegram-bot-token",
    properties=keyvault.SecretPropertiesArgs(value=telegram_bot_token),
    tags=tags,
)

openai_endpoint_secret = keyvault.Secret(
    "azureOpenAiEndpointSecret",
    resource_group_name=resource_group.name,
    vault_name=vault.name,
    secret_name="azure-openai-endpoint",
    properties=keyvault.SecretPropertiesArgs(value=azure_openai_endpoint),
    tags=tags,
)

openai_api_key_secret = keyvault.Secret(
    "azureOpenAiApiKeySecret",
    resource_group_name=resource_group.name,
    vault_name=vault.name,
    secret_name="azure-openai-api-key",
    properties=keyvault.SecretPropertiesArgs(value=azure_openai_api_key),
    tags=tags,
)

openai_deployment_secret = keyvault.Secret(
    "azureOpenAiDeploymentSecret",
    resource_group_name=resource_group.name,
    vault_name=vault.name,
    secret_name="azure-openai-deployment",
    properties=keyvault.SecretPropertiesArgs(value=azure_openai_deployment),
    tags=tags,
)

openai_api_version_secret = keyvault.Secret(
    "azureOpenAiApiVersionSecret",
    resource_group_name=resource_group.name,
    vault_name=vault.name,
    secret_name="azure-openai-api-version",
    properties=keyvault.SecretPropertiesArgs(value=azure_openai_api_version),
    tags=tags,
)

identity_principal_id = identity.principal_id

acr_pull_assignment = RoleAssignment(
    "acrPullAssignment",
    principal_id=identity_principal_id,
    principal_type=authorization.PrincipalType.SERVICE_PRINCIPAL,
    role_assignment_name=deterministic_guid("acr-pull", compact_name("acr"), env_name, region_abbr, sequence),
    role_definition_id=role_definition_id(acr_pull_role),
    scope=acr.id,
    description="Allow the Nexus managed identity to pull images from ACR.",
)

kv_secrets_assignment = RoleAssignment(
    "keyVaultSecretsUserAssignment",
    principal_id=identity_principal_id,
    principal_type=authorization.PrincipalType.SERVICE_PRINCIPAL,
    role_assignment_name=deterministic_guid("kv-secrets-user", resource_name("k"), env_name, region_abbr, sequence),
    role_definition_id=role_definition_id(key_vault_secrets_user_role),
    scope=vault.id,
    description="Allow the Nexus managed identity to read Key Vault secrets.",
)

blob_data_assignment = RoleAssignment(
    "storageBlobDataContributorAssignment",
    principal_id=identity_principal_id,
    principal_type=authorization.PrincipalType.SERVICE_PRINCIPAL,
    role_assignment_name=deterministic_guid("blob-data-contributor", compact_name("st"), env_name, region_abbr, sequence),
    role_definition_id=role_definition_id(storage_blob_data_contributor_role),
    scope=storage_account.id,
    description="Allow the Nexus managed identity to write artifact metadata to Blob Storage.",
)

shared_keys = Output.all(resource_group.name, workspace.name).apply(
    lambda args: operationalinsights.get_shared_keys_output(
        resource_group_name=args[0],
        workspace_name=args[1],
    )
)

environment = app.ManagedEnvironment(
    resource_name("cae"),
    environment_name=resource_name("cae"),
    resource_group_name=resource_group.name,
    location=location,
    app_logs_configuration=app.AppLogsConfigurationArgs(
        destination="log-analytics",
        log_analytics_configuration=app.LogAnalyticsConfigurationArgs(
            customer_id=workspace.customer_id,
            shared_key=shared_keys.apply(lambda keys: keys.primary_shared_key),
        ),
    ),
    tags=tags,
)

image_ref = Output.concat(acr.login_server, "/", image_name)
storage_account_url = Output.concat("https://", storage_account.name, ".blob.core.windows.net")

container_app = app.ContainerApp(
    resource_name("ca"),
    container_app_name=resource_name("ca"),
    resource_group_name=resource_group.name,
    location=location,
    managed_environment_id=environment.id,
    configuration=app.ConfigurationArgs(
        ingress=app.IngressArgs(
            external=True,
            target_port=8000,
            transport="auto",
        ),
        registries=[
            app.RegistryCredentialsArgs(
                server=acr.login_server,
                identity=identity.id,
            )
        ],
    ),
    template=app.TemplateArgs(
        containers=[
            app.ContainerArgs(
                name="nexus",
                image=image_ref,
                env=[
                    app.EnvironmentVarArgs(name="AZURE_STORAGE_ACCOUNT_URL", value=storage_account_url),
                    app.EnvironmentVarArgs(name="AZURE_STORAGE_CONTAINER", value="artifacts"),
                    app.EnvironmentVarArgs(name="APPLICATIONINSIGHTS_CONNECTION_STRING", value=app_insights.connection_string),
                    app.EnvironmentVarArgs(name="AZURE_CLIENT_ID", value=identity.client_id),
                    app.EnvironmentVarArgs(name="AZURE_KEY_VAULT_URI", value=vault.properties.vault_uri),
                    app.EnvironmentVarArgs(name="AZURE_REGION", value=location),
                    app.EnvironmentVarArgs(name="APP_ENV", value=env_name),
                    app.EnvironmentVarArgs(name="APP_VERSION", value=app_version),
                ],
                resources=app.ContainerResourcesArgs(cpu=0.5, memory="1Gi"),
                probes=[
                    app.ContainerAppProbeArgs(
                        type="Liveness",
                        http_get=app.ContainerAppProbeHttpGetArgs(path="/healthz", port=8000),
                        initial_delay_seconds=10,
                        period_seconds=30,
                    )
                ],
            )
        ],
        scale=app.ScaleArgs(
            min_replicas=1,
            max_replicas=1,
        ),
    ),
    identity=app.ManagedServiceIdentityArgs(
        type=app.ManagedServiceIdentityType.USER_ASSIGNED,
        user_assigned_identities=[identity.id],
    ),
    tags=tags,
    opts=ResourceOptions(depends_on=[acr_pull_assignment, kv_secrets_assignment, blob_data_assignment]),
)

pulumi.export("resourceGroupName", resource_group.name)
pulumi.export("containerRegistryLoginServer", acr.login_server)
pulumi.export("containerAppName", container_app.name)
pulumi.export(
    "containerAppUrl",
    Output.concat("https://", container_app.configuration.apply(lambda c: c.ingress.fqdn if c and c.ingress else "")),
)
pulumi.export("keyVaultUri", vault.properties.vault_uri)
pulumi.export("storageAccountName", storage_account.name)
pulumi.export("applicationInsightsName", app_insights.name)
