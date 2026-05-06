from __future__ import annotations

import pulumi
from pulumi import Config, Output
from pulumi_azure_native import app, authorization, containerregistry, insights, keyvault, operationalinsights, resources, storage


config = Config()
location = config.get("location") or "eastus"
app_version = config.get("appVersion") or "0.1.0"
image_name = config.get("containerImageName") or "aari-nexus-azure:dev"

telegram_bot_token = config.require_secret("telegramBotToken")
azure_openai_endpoint = config.require_secret("azureOpenAiEndpoint")
azure_openai_api_key = config.require_secret("azureOpenAiApiKey")
azure_openai_deployment = config.require_secret("azureOpenAiDeployment")
azure_openai_api_version = config.require_secret("azureOpenAiApiVersion")

tags = {
    "org": "aari",
    "managed_by": "pulumi",
    "service": "aari-nexus-azure",
    "environment": "dev",
}

resource_group = resources.ResourceGroup(
    "aari-nexus-rg",
    location=location,
    tags=tags,
)

workspace = operationalinsights.Workspace(
    "aari-nexus-law",
    resource_group_name=resource_group.name,
    location=location,
    retention_in_days=30,
    sku=operationalinsights.WorkspaceSkuArgs(name="PerGB2018"),
    tags=tags,
)

app_insights = insights.Component(
    "aari-nexus-ai",
    resource_group_name=resource_group.name,
    location=location,
    application_type="web",
    kind="web",
    workspace_resource_id=workspace.id,
    tags=tags,
)

acr = containerregistry.Registry(
    "aariNexusAcr",
    resource_group_name=resource_group.name,
    location=location,
    admin_user_enabled=True,
    sku=containerregistry.SkuArgs(name="Basic"),
    tags=tags,
)

storage_account = storage.StorageAccount(
    "aarinexusstorage",
    resource_group_name=resource_group.name,
    location=location,
    sku=storage.SkuArgs(name=storage.SkuName.STANDARD_LRS),
    kind=storage.Kind.STORAGE_V2,
    allow_blob_public_access=False,
    minimum_tls_version=storage.MinimumTlsVersion.TLS1_2,
    tags=tags,
)

blob_container = storage.BlobContainer(
    "artifacts",
    resource_group_name=resource_group.name,
    account_name=storage_account.name,
    container_name="artifacts",
    public_access=storage.PublicAccess.NONE,
)

client_config = authorization.get_client_config()

vault = keyvault.Vault(
    "aari-nexus-kv",
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

shared_keys = operationalinsights.get_shared_keys_output(
    resource_group_name=resource_group.name,
    workspace_name=workspace.name,
)

environment = app.ManagedEnvironment(
    "aari-nexus-env",
    resource_group_name=resource_group.name,
    location=location,
    app_logs_configuration=app.AppLogsConfigurationArgs(
        destination="log-analytics",
        log_analytics_configuration=app.LogAnalyticsConfigurationArgs(
            customer_id=workspace.customer_id,
            shared_key=shared_keys.primary_shared_key,
        ),
    ),
    tags=tags,
)

acr_credentials = containerregistry.list_registry_credentials_output(
    resource_group_name=resource_group.name,
    registry_name=acr.name,
)

acr_password = acr_credentials.passwords.apply(
    lambda passwords: passwords[0]["value"] if passwords else None
)

storage_keys = storage.list_storage_account_keys_output(
    account_name=storage_account.name,
    resource_group_name=resource_group.name,
)

storage_connection_string = Output.all(storage_account.name, storage_keys.keys).apply(
    lambda args: (
        f"DefaultEndpointsProtocol=https;AccountName={args[0]};"
        f"AccountKey={args[1][0]['value']};EndpointSuffix=core.windows.net"
    )
)

image_ref = Output.concat(acr.login_server, "/", image_name)

container_app = app.ContainerApp(
    "aari-nexus-app",
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
                username=acr_credentials.username,
                password_secret_ref="acr-password",
            )
        ],
        secrets=[
            app.SecretArgs(name="acr-password", value=acr_password),
            app.SecretArgs(name="telegram-bot-token", value=telegram_bot_token),
            app.SecretArgs(name="azure-openai-endpoint", value=azure_openai_endpoint),
            app.SecretArgs(name="azure-openai-api-key", value=azure_openai_api_key),
            app.SecretArgs(name="azure-openai-deployment", value=azure_openai_deployment),
            app.SecretArgs(name="azure-openai-api-version", value=azure_openai_api_version),
            app.SecretArgs(name="azure-storage-connection-string", value=storage_connection_string),
            app.SecretArgs(name="app-insights-connection-string", value=app_insights.connection_string),
        ],
    ),
    template=app.TemplateArgs(
        containers=[
            app.ContainerArgs(
                name="nexus",
                image=image_ref,
                env=[
                    app.EnvironmentVarArgs(name="TELEGRAM_BOT_TOKEN", secret_ref="telegram-bot-token"),
                    app.EnvironmentVarArgs(name="AZURE_OPENAI_ENDPOINT", secret_ref="azure-openai-endpoint"),
                    app.EnvironmentVarArgs(name="AZURE_OPENAI_API_KEY", secret_ref="azure-openai-api-key"),
                    app.EnvironmentVarArgs(name="AZURE_OPENAI_DEPLOYMENT", secret_ref="azure-openai-deployment"),
                    app.EnvironmentVarArgs(name="AZURE_OPENAI_API_VERSION", secret_ref="azure-openai-api-version"),
                    app.EnvironmentVarArgs(name="AZURE_STORAGE_CONNECTION_STRING", secret_ref="azure-storage-connection-string"),
                    app.EnvironmentVarArgs(name="APPLICATIONINSIGHTS_CONNECTION_STRING", secret_ref="app-insights-connection-string"),
                    app.EnvironmentVarArgs(name="AZURE_STORAGE_CONTAINER", value="artifacts"),
                    app.EnvironmentVarArgs(name="AZURE_KEY_VAULT_URI", value=vault.properties.vault_uri),
                    app.EnvironmentVarArgs(name="AZURE_REGION", value=location),
                    app.EnvironmentVarArgs(name="APP_ENV", value="dev"),
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
    identity=app.ManagedServiceIdentityArgs(type=app.ManagedServiceIdentityType.SYSTEM_ASSIGNED),
    tags=tags,
)

pulumi.export("resourceGroupName", resource_group.name)
pulumi.export("containerRegistryLoginServer", acr.login_server)
pulumi.export("containerAppName", container_app.name)
pulumi.export("containerAppUrl", Output.concat("https://", container_app.configuration.apply(lambda c: c.ingress.fqdn if c and c.ingress else "")))
pulumi.export("keyVaultUri", vault.properties.vault_uri)
pulumi.export("storageAccountName", storage_account.name)
pulumi.export("applicationInsightsName", app_insights.name)
