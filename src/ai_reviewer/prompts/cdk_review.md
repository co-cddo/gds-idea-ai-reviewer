# CDK Infrastructure Review Standards

Target: `{repository}` / PR `#{pr_number}`

This document defines CDK infrastructure standards for GDS Idea projects. It serves as both a human-readable reference and the automated reviewer's criteria.

**Scope:** `app.py`, `config.py`, `cdk.json`, `cdk.context.json`, `stacks/**/*.py`, `lambda/**/*`, `app_src/Dockerfile` if CDK references it, any file importing `aws_cdk` or `aws_cdk_lib`, and `tests/unit/test_*_stack.py`.

**Out of scope:** `cdk.out/`, `.venv/`, `node_modules/`, `__pycache__/`, `*.lock`.

## 1. Configuration & Environment

### Use typed config objects, not raw context lookups

- Environment and application configuration must use typed config objects.
- For repositories using `gds-idea-app-kit`, config should come from `gds_idea_cdk_constructs`.
- Do not flag a missing local `config.py` when the repo imports and uses:
  - `AppConfig`
  - `DeploymentConfig`
  - `DeploymentEnvironment`
- `AppConfig.from_pyproject()` satisfies the application config standard.
- `DeploymentConfig(cdk_env)` satisfies the deployment config standard for real CDK deployments.
- Deployment environment is resolved from the CDK AWS account via `DeploymentConfig`, not by a separate raw CDK context selector.
- Use `dep_config.environment` for environment comparisons.
- Use `dep_config.environment.friendly_name` for tags, display names, stack IDs, and readable resource names.
- Do not introduce a separate environment selector such as `phase`, `stage`, `deployment_env`, or raw CDK context values.
- Do not duplicate account-to-environment mappings across stack code.
- Raw CDK context lookups must not be scattered through stack code.
- App-specific configuration in `cdk.json` is discouraged, even if wrapped in a typed model. Typed validation is better than raw dict access, but the preferred direction is to move app-specific values out of `cdk.json`.

**Bad:**

```python
# Fragile — no validation, string booleans, scattered everywhere
deploy_emails = app.node.try_get_context("deploy_ses_infrastructure").lower() == "true"
account = app.node.try_get_context("prod_account_number")
region = app.node.try_get_context("aws_region")
bucket_name = app.node.try_get_context("athena_bucket")
```

**Also bad — raw dict lookups with manual type casting:**

```python
# No type safety: a typo like "athenaQueryBucket" silently returns None and
# fails much later. The str() cast hides the missing-key problem until runtime.
environments_ctx = app.node.try_get_context("environments") or {}
env_cfg = environments_ctx.get("development")

athena_queries_bucket_name = str(env_cfg["athenaQueriesBucket"])
```

**Good — app-kit deployment config:**

```python
cfg = AppConfiguration()

app = cdk.App()

deployment_target = resolve_deployment_target()

cdk_env = cdk.Environment(
    account=deployment_target.account,
    region=deployment_target.region,
)

app_config = AppConfig.from_pyproject()
dep_config = DeploymentConfig(cdk_env)
```

**Good — tags from typed config:**

```python
Tags.of(app).add("Environment", dep_config.environment.friendly_name)
Tags.of(app).add("ManagedBy", "cdk")
Tags.of(app).add("Repository", cfg.tags.repository)
Tags.of(app).add("AppName", app_config.app_name)
Tags.of(app).add("Name", cfg.tags.display_name)
```

**Good — resolving the CDK deployment target from validated environment variables:**

```python
deployment_target = resolve_deployment_target()

cdk_env = cdk.Environment(
    account=deployment_target.account,
    region=deployment_target.region,
)
```

This is acceptable because:

- the account and region come from the CDK deployment environment;
- they are validated by `DeploymentTarget`;
- invalid or missing values raise a clear configuration error early;
- `DeploymentConfig(cdk_env)` then derives the deployment environment from the account ID.

### Use the shared app-kit config API when available

For app-kit repositories, prefer the shared library API rather than duplicating config models locally.

**Application config:**

```python
from gds_idea_cdk_constructs import AppConfig

app_config = AppConfig.from_pyproject()

app_name = app_config.app_name
framework = app_config.framework
health_check_path = app_config.health_check_path
```

**Deployment config:**

```python
from gds_idea_cdk_constructs import DeploymentConfig

dep_config = DeploymentConfig(cdk_env)

environment = dep_config.environment
environment_name = dep_config.environment.friendly_name

domain_name = dep_config.domain_name
vpc_id = dep_config.vpc_id
cluster_name = dep_config.cluster_name
user_pool_id = dep_config.user_pool_id
external_idp_name = dep_config.external_idp_name
waf_arn = dep_config.waf_arn
waf_big_upload_arn = dep_config.waf_big_upload_arn
log_bucket_name = dep_config.log_bucket_name
redirect_unauthorised_url = dep_config.redirect_unauthorised_url
```

### Use `DeploymentEnvironment` as the single environment model

- `DeploymentEnvironment` is the canonical environment model for app-kit repositories.
- Deployment environment is derived from the CDK AWS account via `DeploymentConfig(cdk_env)`.
- Use `dep_config.environment` for environment comparisons.
- Use `dep_config.environment.friendly_name` for tags, display names, stack IDs, and readable resource names.
- Do not introduce `phase` or any other separate environment selector.
- Do not use raw CDK context values to select the deployment environment.
- Do not duplicate account-to-environment mappings across app code, stack code, or tests.

**Good:**

```python
from gds_idea_cdk_constructs.config import DeploymentEnvironment

if dep_config.environment == DeploymentEnvironment.PRODUCTION:
    removal_policy = RemovalPolicy.RETAIN
else:
    removal_policy = RemovalPolicy.DESTROY
```

**Good:**

```python
environment_name = dep_config.environment.friendly_name
bucket_name = f"{app_config.app_name}-documents-{environment_name}"
```

**Bad:**

```python
if cdk_env.account == "588077357019":
    environment_name = "production"
else:
    environment_name = "development"
```

### Avoid live AWS API calls except shared deployment config initialisation

- Do not add arbitrary `boto3` calls in `app.py`, stacks, constructs, or tests.
- The approved app-kit exception is `DeploymentConfig(cdk_env)`, which fetches shared deployment configuration from AWS Systems Manager Parameter Store.
- This exception is allowed in real CDK app initialisation only.
- Unit tests must not use `DeploymentConfig(cdk_env)`.
- Unit tests must use `DeploymentConfig.from_dict(cdk_env, config)`.

**Bad in tests:**

```python
dep_config = DeploymentConfig(cdk_env)
```

**Good in tests:**

```python
dep_config = DeploymentConfig.from_dict(
    cdk_env,
    fake_deployment_config(account_id=cdk_env.account),
)
```

### Model structured config with nested sub-models, not flat blobs

- When per-environment config has repeated or grouped structure, model it with nested typed sub-models.
- Examples include:
  - dataset config;
  - Athena config;
  - per-bucket options;
  - Lambda settings;
  - notification settings.
- Sub-models give each logical group its own validation, defaults, and autocomplete.
- Config values should live in a dedicated config source loaded through the typed model:
  - a `config/` directory using TOML or YAML;
  - `pyproject.toml`;
  - the model's own defaults.
- New app-specific values should not be added to `cdk.json`.

**Good — nested, self-documenting config:**

```python
from pydantic import BaseModel, field_validator


class DatasetConfig(BaseModel):
    table_name: str
    s3_bucket_name: str
    s3_prefix: str
    csv_delimiter: str = ","
    csv_quote: str = '"'

    @field_validator("s3_bucket_name")
    @classmethod
    def _bucket_name_is_valid(cls, value: str) -> str:
        return validate_s3_bucket_name(value)

    @field_validator("s3_prefix")
    @classmethod
    def _s3_prefix_is_valid(cls, value: str) -> str:
        return validate_s3_prefix(value)


class AthenaConfig(BaseModel):
    database_name: str
    workgroup_name: str
    queries_bucket_name: str

    @field_validator("queries_bucket_name")
    @classmethod
    def _queries_bucket_name_is_valid(cls, value: str) -> str:
        return validate_s3_bucket_name(value)


class EnvironmentConfig(BaseModel):
    athena: AthenaConfig
    create_source_buckets: bool = False
    datasets: list[DatasetConfig]
```

### Validate every environment and every field with a known shape

- A single typed config model must validate both development and production.
- Adding a field for one environment and forgetting the other should fail in CI.
- Add validators for values with known formats, for example:
  - AWS account IDs must be 12 digits;
  - AWS regions must be from an allowed set;
  - S3 bucket names must satisfy AWS naming rules;
  - S3 prefixes must not be absolute paths or contain directory traversal;
  - KMS key ARNs must match the expected ARN format;
  - Glue database names must match AWS naming constraints.
- For app-kit repositories, deployment environment must be resolved via `DeploymentConfig(cdk_env)`.
- Do not duplicate account IDs, regions, or environment mappings across stacks.
- Use `DeploymentEnvironment` for environment comparisons.
- Use `dep_config.environment.friendly_name` for readable naming.

### Keep `cdk.json` limited to entrypoint and CDK feature flags

- `cdk.json` should contain only the CDK app entrypoint and CDK feature flags.
- App-specific config values should not be added to `cdk.json`.
- Examples of app-specific config that should be moved out of `cdk.json`:
  - table names;
  - bucket names;
  - dataset definitions;
  - Athena database names;
  - environment-specific blocks;
  - feature toggles;
  - account numbers;
  - ARNs.
- Loading `cdk.json` values through a typed model is better than raw dict access, but new or expanded app-specific config in `cdk.json` should still be flagged.
- Preferred homes for app-specific config are:
  - a dedicated `config/` directory using TOML or YAML;
  - `pyproject.toml`;
  - typed model defaults.

App-specific config must not be added to `cdk.json`.

If existing repositories already contain app-specific `cdk.json` context,
reviewers should flag PRs that:

- add new app-specific context keys;
- expand existing app-specific context blocks;
- introduce new dependencies on existing app-specific context;
- move additional environment-specific values into `cdk.json`.

Migration of existing legacy context should be handled as a separate improvement. Do not treat legacy context as a pattern to copy.

### Derive account IDs and ARNs from config, never hardcode them in stack code

- AWS account IDs and ARNs must come from typed config objects, typed enums, or shared config libraries.
- Do not hardcode account IDs or ARNs as string literals in stack code.
- It is acceptable for account IDs to live in a central typed enum such as `DeploymentEnvironment` in `gds_idea_cdk_constructs`.

**Bad:**

```python
resources=["arn:aws:kms:eu-west-2:588077357019:key/dc126e48-..."]
```

**Good:**

```python
resources=[
    f"arn:aws:kms:{dep_config.cdk_env.region}:"
    f"{DeploymentEnvironment.PRODUCTION.value}:key/{kms_key_id}"
]
```

**Good — prefer passing ARNs through typed config when possible:**

```python
resources=[environment_config.kms_key_arn]
```

## 2. Stack Structure

### Split stacks by bounded concern, not by convenience

- One focused stack per bounded concern, for example:
  - storage;
  - compute;
  - networking;
  - monitoring;
  - secrets;
  - data processing.
- Flag any single stack file exceeding roughly 300 lines as a candidate for splitting.
- Monolithic stacks make independent deployments harder and increase blast-radius risk.
- This is usually advisory unless the PR is making the stack significantly more monolithic.

**Bad:**

```python
class EverythingStack(Stack):
    # 600 lines: DynamoDB + Lambda + SQS + CloudWatch dashboard + alarms
    ...
```

**Good:**

```text
stacks/
  storage.py
  processing.py
  monitoring.py
```

### Pass typed config objects into every stack constructor

- Stacks should receive typed config objects rather than many loose scalar parameters.
- For app-kit repositories, pass both:
  - `app_config: AppConfig`
  - `dep_config: DeploymentConfig`
- Pass cross-stack resources explicitly as constructor arguments.
- Avoid constructors with long lists of scalar strings, booleans, or ARNs.

**Bad:**

```python
def __init__(
    self,
    scope,
    construct_id,
    app_name,
    domain_name,
    vpc_id,
    cluster_name,
    user_pool_id,
    waf_arn,
    log_bucket_name,
    environment_name,
    **kwargs,
):
    ...
```

**Good:**

```python
def __init__(
    self,
    scope,
    construct_id: str,
    *,
    app_config: AppConfig,
    dep_config: DeploymentConfig,
    **kwargs,
):
    super().__init__(scope, construct_id, **kwargs)

    app_name = app_config.app_name
    environment_name = dep_config.environment.friendly_name
```

### Keep `app.py` focused on app initialisation and stack wiring

- `app.py` should:
  - create `cdk.App()`;
  - resolve the deployment target;
  - construct `cdk.Environment`;
  - load typed config;
  - apply app-level tags;
  - instantiate stacks;
  - wire dependencies between stacks.
- `app.py` should not contain detailed resource definitions, IAM policy construction, or business logic.

**Good:**

```python
app = cdk.App()

deployment_target = resolve_deployment_target()

cdk_env = cdk.Environment(
    account=deployment_target.account,
    region=deployment_target.region,
)

app_config = AppConfig.from_pyproject()
dep_config = DeploymentConfig(cdk_env)

storage_stack = StorageStack(
    app,
    sid("StorageStack"),
    app_config=app_config,
    dep_config=dep_config,
    env=cdk_env,
)

processing_stack = ProcessingStack(
    app,
    sid("ProcessingStack"),
    app_config=app_config,
    dep_config=dep_config,
    storage=storage_stack,
    env=cdk_env,
)

processing_stack.add_dependency(storage_stack)
```

### Wire cross-stack references explicitly

- Cross-stack references must be passed as constructor parameters.
- Add explicit `.add_dependency()` calls in `app.py` when one stack relies on another.
- Do not use `Fn::ImportValue` for internal app stack wiring unless there is a clear cross-app or cross-repo reason.
- Do not reach into another stack's internals from arbitrary locations.

**Bad:**

```python
bucket_name = Fn.import_value("SharedBucketName")
```

**Good:**

```python
storage_stack = StorageStack(
    app,
    sid("StorageStack"),
    app_config=app_config,
    dep_config=dep_config,
    env=cdk_env,
)

processing_stack = ProcessingStack(
    app,
    sid("ProcessingStack"),
    app_config=app_config,
    dep_config=dep_config,
    storage=storage_stack,
    env=cdk_env,
)

processing_stack.add_dependency(storage_stack)
```

## 3. Directory Layout

### Separate infrastructure from application source

- Infrastructure should live at the repository root:
  - `app.py`
  - `config.py` if local config is needed
  - `cdk.json`
  - `stacks/`
- Application and function source code should live in dedicated subdirectories.
- Infrastructure and application code have different dependency trees, test suites, and deployment lifecycles.

**Recommended layout:**

```text
app.py
config.py
cdk.json
stacks/
  storage.py
  processing.py
  monitoring.py
lambda/
  webhook_receiver/
    handler.py
    Dockerfile
    requirements.txt
  upload_processor/
    handler.py
    Dockerfile
    pyproject.toml
app_src/
  Dockerfile
  main.py
  pyproject.toml
tests/
  unit/
    test_storage_stack.py
    test_processing_stack.py
```

### Put deployed application source in `app_src/`

- If the repo deploys an application such as a web app, API, Streamlit app, Dash app, or FastAPI app, its source should live in `app_src/`.
- Do not mix deployed application source into the repository root alongside CDK infrastructure files.
- A separate `app_src/` keeps application dependencies and infrastructure dependencies distinct.

### Give each Lambda function its own subfolder

- Lambda source code must live in a `lambda/` directory with one subfolder per Lambda function.
- Each subfolder should contain:
  - handler source;
  - a Dockerfile when image-based deployment is used;
  - a dependency manifest such as `requirements.txt` or `pyproject.toml`.
- The subfolder name should match how the Lambda function is referenced in CDK.
- One folder per function keeps each Lambda self-contained and buildable in isolation.

**Good:**

```text
lambda/
  upload_processor/
    handler.py
    Dockerfile
    requirements.txt
  notification_sender/
    handler.py
    Dockerfile
    pyproject.toml
```

### Use structured logging in Lambda handlers, not `print()`

- Lambda handler code must use Python's `logging` module instead of `print()` statements.
- Each handler should include logging for key execution points, for example:
  - event received;
  - major decision made;
  - downstream call started or completed;
  - processing completed;
  - error details before raising.
- This applies to Lambda handler code only.
- `print()` statements are acceptable in CDK infrastructure code for surfacing synth/deploy-time debugging output.

**Bad:**

```python
def handler(event, context):
    print(f"Processing event: {json.dumps(event)}")
    result = process(event)
    print(f"Result: {result}")
    return result
```

**Good:**

```python
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    logger.info("Received event with %d records", len(event.get("Records", [])))
    result = process(event)
    logger.info("Processing complete")
    return result
```

## 4. IAM Permissions

### Prefer `.grant_*()` methods over manual `PolicyStatement`s

- S3 buckets, DynamoDB tables, Secrets Manager secrets, SSM parameters, SQS queues, SNS topics, and other CDK resources often support `.grant_*()` methods.
- Prefer `.grant_*()` methods where available.
- These methods scope permissions to the target resource and manage CDK dependency ordering.
- Manual `PolicyStatement`s are allowed when:
  - there is no suitable grant helper;
  - condition keys are required;
  - the permission is for a service API rather than a specific resource;
  - cross-account access requires custom policy structure;
  - an imported resource does not support the required grant behaviour.
- Manual statements must still be scoped as narrowly as possible.

**Bad:**

```python
lambda_role.add_to_policy(iam.PolicyStatement(
    actions=["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
    resources=[f"arn:aws:s3:::{bucket_name}", f"arn:aws:s3:::{bucket_name}/*"],
))
```

**Good:**

```python
data_bucket.grant_read_write(lambda_function)
```

### Require `sid` and justification for any wildcard resource

- `resources=["*"]` is only permitted when the AWS action genuinely has no useful resource-level ARN support, or when scoping is not possible for the specific service action.
- Any wildcard resource statement must include:
  - a `sid=` parameter naming the permission's purpose;
  - an inline comment explaining why scoping is not possible.
- Overly broad permissions are a security risk and violate least privilege.
- The `sid` makes the policy auditable in the IAM console.
- The comment prevents future developers from assuming the wildcard was accidental or lazy.

**Bad:**

```python
role.add_to_policy(iam.PolicyStatement(
    actions=["bedrock:InvokeModel"],
    resources=["*"],
))
```

**Good:**

```python
role.add_to_policy(iam.PolicyStatement(
    sid="InvokeBedrock",
    actions=[
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream",
    ],
    resources=["*"],  # Bedrock model invocation is not scoped to project-owned resources here
))
```

### Keep IAM logic inside stacks or shared IAM helpers, not in `app.py`

- `app.py` should only wire stacks together and set top-level config.
- Permission-granting logic belongs inside:
  - stacks;
  - constructs;
  - shared helper modules such as `stacks/shared/iam.py`.
- Do not let `app.py` become a dumping ground for policy details.

**Bad — IAM logic in `app.py`:**

```python
storage_stack = StorageStack(app, sid("StorageStack"), app_config=app_config, dep_config=dep_config, env=cdk_env)
processing_stack = ProcessingStack(app, sid("ProcessingStack"), app_config=app_config, dep_config=dep_config, env=cdk_env)

processing_stack.lambda_function.add_to_role_policy(iam.PolicyStatement(
    actions=["s3:GetObject", "s3:PutObject"],
    resources=[storage_stack.bucket.bucket_arn + "/*"],
))
```

**Good — permissions encapsulated inside the stack that needs them:**

```python
storage_stack = StorageStack(
    app,
    sid("StorageStack"),
    app_config=app_config,
    dep_config=dep_config,
    env=cdk_env,
)

processing_stack = ProcessingStack(
    app,
    sid("ProcessingStack"),
    app_config=app_config,
    dep_config=dep_config,
    storage=storage_stack,
    env=cdk_env,
)

processing_stack.add_dependency(storage_stack)
```

```python
class ProcessingStack(Stack):
    def __init__(
        self,
        scope,
        construct_id: str,
        *,
        app_config: AppConfig,
        dep_config: DeploymentConfig,
        storage: StorageStack,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        self.lambda_function = _lambda.DockerImageFunction(...)

        storage.bucket.grant_read_write(self.lambda_function)
        storage.table.grant_read_write_data(self.lambda_function)
        grant_bedrock_invoke(self.lambda_function)
```

```python
def grant_bedrock_invoke(grantee: IGrantable) -> None:
    grantee.grant_principal.add_to_principal_policy(iam.PolicyStatement(
        sid="InvokeBedrock",
        actions=[
            "bedrock:InvokeModel",
            "bedrock:InvokeModelWithResponseStream",
        ],
        resources=["*"],  # Bedrock model invocation is not scoped to project-owned resources here
    ))
```

## 5. Naming Conventions

### Use a consistent construct ID pattern

- Stack IDs and top-level construct IDs should follow a consistent project pattern.
- Construct ID consistency improves readability and makes generated resources easier to understand.
- Do not require renaming existing construct IDs unless the PR is already creating new resources or the migration impact has been considered.
- Changing construct IDs can change CloudFormation logical IDs and may cause resource replacement.

### Suffix physical resource names with the deployment environment

- Physical resource names such as `bucket_name`, `function_name`, `role_name`, and `log_group_name` must include an environment suffix when deploying multiple environments to shared AWS accounts.
- For app-kit repositories, derive the suffix from typed deployment config.
- Use `dep_config.environment.friendly_name` for environment suffixes.
- Do not introduce a separate environment naming system.

**Bad:**

```python
function_name = "evidence-base-upload-processor"
```

**Good — using `DeploymentConfig`:**

```python
environment_name = dep_config.environment.friendly_name

function_name = f"{app_config.app_name}-upload-processor-{environment_name}"
```

### Derive stack IDs from a single consistent pattern

- Stack IDs should be generated from a single helper or consistent pattern.
- For app-kit repositories, use:
  - `app_config.app_name`
  - `dep_config.environment.friendly_name`
- Do not hardcode inconsistent stack IDs across `app.py`.

**Bad:**

```python
StorageStack(app, "StorageStack", app_config=app_config, dep_config=dep_config, env=cdk_env)
ProcessingStack(app, "ai-pqs-ProcessingStack", app_config=app_config, dep_config=dep_config, env=cdk_env)
SecretsStack(app, "my-app-secrets-stack-production", app_config=app_config, dep_config=dep_config, env=cdk_env)
```

**Good:**

```python
class StackId:
    """Generate consistent CDK stack IDs."""

    def __init__(self, app_name: str, environment_name: str):
        self.app_name = app_name
        self.environment_name = environment_name

    @classmethod
    def from_config(
        cls,
        *,
        app_config: AppConfig,
        dep_config: DeploymentConfig,
    ) -> "StackId":
        return cls(
            app_name=app_config.app_name,
            environment_name=dep_config.environment.friendly_name,
        )

    def __call__(self, stack_name: str) -> str:
        return f"{self.app_name}-{stack_name}-{self.environment_name}"
```

```python
sid = StackId.from_config(
    app_config=app_config,
    dep_config=dep_config,
)

storage_stack = StorageStack(
    app,
    sid("StorageStack"),
    app_config=app_config,
    dep_config=dep_config,
    env=cdk_env,
)

processing_stack = ProcessingStack(
    app,
    sid("ProcessingStack"),
    app_config=app_config,
    dep_config=dep_config,
    storage=storage_stack,
    env=cdk_env,
)

processing_stack.add_dependency(storage_stack)
```

## 6. Tagging

### Apply two tiers of tags: app-level and per-resource

- Apply app-level tags in `app.py` using `Tags.of(app).add(...)`.
- Apply per-resource or per-stack tags inside stacks.
- Tags are required for cost allocation, security auditing, ownership, and operational support.

**Required app-level tags:**

- `Environment`
- `ManagedBy`
- `Repository`
- `AppName`

**Recommended app-level tag:**

- `Name`

**Required per-resource or per-stack tags where applicable:**

- `ResourceType`
- `Service`

**Bad:**

```python
Tags.of(app).add("Repository", "TBA")
```

**Good:**

```python
Tags.of(app).add("Environment", dep_config.environment.friendly_name)
Tags.of(app).add("ManagedBy", "cdk")
Tags.of(app).add("Repository", cfg.tags.repository)
Tags.of(app).add("AppName", app_config.app_name)
Tags.of(app).add("Name", cfg.tags.display_name)
```

```python
Tags.of(self).add("ResourceType", "DynamoDB")
Tags.of(self).add("Service", "Storage")
```

### Flag placeholder tag values

- Placeholder tag values must be resolved before merging.
- Flag values such as:
  - `"TBA"`
  - `"TODO"`
  - `"changeme"`
  - `"unknown"`
  - `"placeholder"`
  - empty strings.

## 7. Removal Policy

### Set an explicit removal policy on every stateful resource

- Every stateful resource must have an explicit removal policy.
- Stateful resources include:
  - DynamoDB tables;
  - S3 data buckets;
  - RDS instances;
  - OpenSearch domains;
  - EFS file systems;
  - persistent queues where message retention matters;
  - secrets where deletion would break recovery.
- CDK defaults vary by resource type and CDK version.
- Relying on defaults can cause unpredictable behaviour during stack deletion or replacement.

### Retain source-of-truth data, destroy only transient resources

- Source-of-truth application data must use `RemovalPolicy.RETAIN`, or environment-conditional retention.
- Production source-of-truth data must be retained.
- Development-only transient resources may use `RemovalPolicy.DESTROY` with clear intent.
- Transient or regenerable resources include:
  - upload staging buckets;
  - caches;
  - temporary processing queues;
  - generated artefact buckets;
  - log groups, where retention is explicitly managed.

**Bad:**

```python
table = dynamodb.Table(
    self,
    "PapersTable",
    removal_policy=RemovalPolicy.DESTROY,
)
```

**Good:**

```python
removal_policy = (
    RemovalPolicy.DESTROY
    if dep_config.environment == DeploymentEnvironment.DEVELOPMENT
    else RemovalPolicy.RETAIN
)

table = dynamodb.Table(
    self,
    "PapersTable",
    partition_key=dynamodb.Attribute(
        name="pk",
        type=dynamodb.AttributeType.STRING,
    ),
    removal_policy=removal_policy,
    point_in_time_recovery=True,
)
```

### Enable recovery features for important stateful data

- DynamoDB tables containing source-of-truth data should enable point-in-time recovery.
- S3 buckets containing source-of-truth data should usually enable versioning.
- RDS instances containing source-of-truth data should use backups and deletion protection where appropriate.

**Good:**

```python
table = dynamodb.Table(
    self,
    "PapersTable",
    partition_key=dynamodb.Attribute(
        name="pk",
        type=dynamodb.AttributeType.STRING,
    ),
    removal_policy=RemovalPolicy.RETAIN,
    point_in_time_recovery=True,
)
```

```python
bucket = s3.Bucket(
    self,
    "DocumentsBucket",
    versioned=True,
    removal_policy=RemovalPolicy.RETAIN,
)
```

## 8. Testing

### Cover IAM permissions, tags, and removal policy at minimum

- CDK apps should have unit tests using `aws_cdk.assertions`.
- Tests should verify at minimum:
  - IAM roles have the expected managed policies and permission statements;
  - wildcard permissions are justified where they exist;
  - tags are applied as expected;
  - stateful resources have explicit removal policies;
  - production source-of-truth resources are retained;
  - development transient resources are destroyed only when intended.
- Avoid brittle full-template snapshot tests.
- Prefer partial assertions using:
  - `assertions.Match.object_like(...)`
  - `assertions.Match.array_with(...)`
  - `assertions.Match.string_like_regexp(...)`

### Do not call live AWS APIs in unit tests

`DeploymentConfig(cdk_env)` fetches config from AWS Systems Manager Parameter Store using `boto3`.

That is acceptable in real CDK app initialisation, but unit tests must not call it.

Use `DeploymentConfig.from_dict(cdk_env, config)` in tests.

**Test helper config:**

```python
def fake_deployment_config(account_id: str) -> dict[str, str]:
    return {
        "domain_name": "https://example.test",
        "vpc_id": "vpc-1234567890abcdef0",
        "ecs_arn": f"arn:aws:ecs:eu-west-2:{account_id}:cluster/test-cluster",
        "cognito_user_pool_id": "eu-west-2_example",
        "waf_arn": (
            f"arn:aws:wafv2:eu-west-2:{account_id}:regional/webacl/test/test"
        ),
        "waf_big_upload_arn": (
            f"arn:aws:wafv2:eu-west-2:{account_id}:regional/webacl/test-big-upload/test"
        ),
        "logs_bucket_name": "test-logs-bucket",
    }
```

**Test fixtures for development and production:**

```python
import aws_cdk as cdk
import pytest
from aws_cdk import assertions

from gds_idea_cdk_constructs import AppConfig, DeploymentConfig
from gds_idea_cdk_constructs.config import DeploymentEnvironment

from stacks.storage import StorageStack


def fake_deployment_config(account_id: str) -> dict[str, str]:
    return {
        "domain_name": "https://example.test",
        "vpc_id": "vpc-1234567890abcdef0",
        "ecs_arn": f"arn:aws:ecs:eu-west-2:{account_id}:cluster/test-cluster",
        "cognito_user_pool_id": "eu-west-2_example",
        "waf_arn": (
            f"arn:aws:wafv2:eu-west-2:{account_id}:regional/webacl/test/test"
        ),
        "waf_big_upload_arn": (
            f"arn:aws:wafv2:eu-west-2:{account_id}:regional/webacl/test-big-upload/test"
        ),
        "logs_bucket_name": "test-logs-bucket",
    }


@pytest.fixture
def app_config() -> AppConfig:
    return AppConfig(
        app_name="test-app",
        framework="fastapi",
        health_check_path="/health",
    )


@pytest.fixture
def dev_dep_config() -> DeploymentConfig:
    cdk_env = cdk.Environment(
        account=DeploymentEnvironment.DEVELOPMENT.value,
        region="eu-west-2",
    )

    return DeploymentConfig.from_dict(
        cdk_env,
        fake_deployment_config(account_id=DeploymentEnvironment.DEVELOPMENT.value),
    )


@pytest.fixture
def prod_dep_config() -> DeploymentConfig:
    cdk_env = cdk.Environment(
        account=DeploymentEnvironment.PRODUCTION.value,
        region="eu-west-2",
    )

    return DeploymentConfig.from_dict(
        cdk_env,
        fake_deployment_config(account_id=DeploymentEnvironment.PRODUCTION.value),
    )


@pytest.fixture
def dev_template(
    app_config: AppConfig,
    dev_dep_config: DeploymentConfig,
):
    app = cdk.App()

    stack = StorageStack(
        app,
        "TestStorageDevelopment",
        app_config=app_config,
        dep_config=dev_dep_config,
        env=dev_dep_config.cdk_env,
    )

    return assertions.Template.from_stack(stack)


@pytest.fixture
def prod_template(
    app_config: AppConfig,
    prod_dep_config: DeploymentConfig,
):
    app = cdk.App()

    stack = StorageStack(
        app,
        "TestStorageProduction",
        app_config=app_config,
        dep_config=prod_dep_config,
        env=prod_dep_config.cdk_env,
    )

    return assertions.Template.from_stack(stack)
```

### Validate deployment config for every real environment

```python
import aws_cdk as cdk
import pytest

from gds_idea_cdk_constructs import DeploymentConfig
from gds_idea_cdk_constructs.config import DeploymentEnvironment


def fake_deployment_config(account_id: str) -> dict[str, str]:
    return {
        "domain_name": "https://example.test",
        "vpc_id": "vpc-1234567890abcdef0",
        "ecs_arn": f"arn:aws:ecs:eu-west-2:{account_id}:cluster/test-cluster",
        "cognito_user_pool_id": "eu-west-2_example",
        "waf_arn": (
            f"arn:aws:wafv2:eu-west-2:{account_id}:regional/webacl/test/test"
        ),
        "waf_big_upload_arn": (
            f"arn:aws:wafv2:eu-west-2:{account_id}:regional/webacl/test-big-upload/test"
        ),
        "logs_bucket_name": "test-logs-bucket",
    }


@pytest.mark.parametrize(
    "environment",
    [
        DeploymentEnvironment.DEVELOPMENT,
        DeploymentEnvironment.PRODUCTION,
    ],
)
def test_deployment_config_is_valid_for_environment(
    environment: DeploymentEnvironment,
):
    cdk_env = cdk.Environment(
        account=environment.value,
        region="eu-west-2",
    )

    dep_config = DeploymentConfig.from_dict(
        cdk_env,
        fake_deployment_config(account_id=environment.value),
    )

    assert dep_config.environment == environment
    assert dep_config.cdk_env.account == environment.value
    assert dep_config.cdk_env.region == "eu-west-2"
```

### Test IAM scoping

```python
def test_lambda_role_has_scoped_secret_access(dev_template):
    dev_template.has_resource_properties(
        "AWS::IAM::Policy",
        {
            "PolicyDocument": {
                "Statement": assertions.Match.array_with([
                    assertions.Match.object_like({
                        "Action": assertions.Match.array_with([
                            "secretsmanager:GetSecretValue",
                        ]),
                        "Resource": assertions.Match.string_like_regexp(
                            r"arn:aws:secretsmanager:.*"
                        ),
                    }),
                ]),
            },
        },
    )
```

### Test tags

```python
def test_table_has_resource_type_tag(dev_template):
    dev_template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "Tags": assertions.Match.array_with([
                assertions.Match.object_like({
                    "Key": "ResourceType",
                    "Value": "DynamoDB",
                }),
            ]),
        },
    )
```

### Test removal policy

```python
def test_table_is_retained_in_production(prod_template):
    prod_template.has_resource(
        "AWS::DynamoDB::Table",
        {
            "DeletionPolicy": "Retain",
            "UpdateReplacePolicy": "Retain",
        },
    )


def test_table_is_destroyed_in_development(dev_template):
    dev_template.has_resource(
        "AWS::DynamoDB::Table",
        {
            "DeletionPolicy": "Delete",
            "UpdateReplacePolicy": "Delete",
        },
    )
```

### Mock AWS calls in tests

- Unit tests must not call real AWS APIs.
- Unit tests must not depend on AWS credentials or network access.
- Use `DeploymentConfig.from_dict(cdk_env, config)` for app-kit deployment config.
- Mock any application code that would call AWS services.
- Do not run `boto3.client(...)` or `boto3.resource(...)` in unit tests unless fully mocked.

## 9. Review Severity

### Blocking issues

The reviewer should treat these as blocking unless the PR includes a clear, reviewed justification:

- hardcoded AWS account IDs or ARNs in stack code;
- app-specific config newly added to `cdk.json`;
- raw context lookups scattered through stacks;
- wildcard IAM resources without `sid` and justification;
- missing explicit removal policy on stateful resources;
- production source-of-truth data configured for deletion;
- unit tests that call live AWS APIs;
- arbitrary new `boto3` calls in `app.py`, stacks, constructs, or tests;
- unresolved merge conflict markers;
- committed `cdk.out/`;
- placeholder production tags;
- Lambda handler `print()` statements;
- template-managed workflow files modified locally.

### Advisory issues

The reviewer should treat these as maintainability feedback unless the PR makes the issue materially worse:

- a stack file exceeding roughly 300 lines;
- stack boundaries that could be split more cleanly;
- legacy app-specific config already present in `cdk.json`;
- existing application source not yet moved to `app_src/`;
- existing construct IDs that do not match the preferred naming pattern;
- missing convenience helpers for repeated naming patterns;
- opportunities to replace manual IAM statements with `.grant_*()` helpers.

## 10. Anti-Patterns to Flag

- Hardcoded AWS account IDs or ARNs as string literals in stack code.
- App-specific config values added to `cdk.json`.
- Raw CDK context lookups scattered through `app.py` or stack files.
- Raw dict lookups with manual type casting instead of typed model validation.
- Config accessed through string keys throughout stack code instead of typed attributes.
- Environment mappings duplicated across multiple files.
- Stack constructors taking many loose scalar config values instead of typed config objects.
- Unit tests that instantiate `DeploymentConfig(cdk_env)` and therefore call AWS Systems Manager Parameter Store.
- Live ad hoc `boto3` calls in stacks or tests.
- Application config mixed into infrastructure code instead of a typed config source.
- New or expanded app-specific `cdk.json` context blocks, even if later validated by a typed model.
- Hardcoded physical resource names without an environment suffix.
- Missing `.add_dependency()` calls between stacks with cross-stack dependencies.
- IAM permission logic dumped into `app.py`.
- Manual IAM policies where a suitable `.grant_*()` helper exists.
- `resources=["*"]` without a `sid` and inline justification.
- Stateful resources without explicit removal policies.
- Source-of-truth data configured with unconditional `RemovalPolicy.DESTROY`.
- Lambda source not in its own subfolder under `lambda/`.
- Application source mixed into the repository root instead of `app_src/`.
- `print()` statements in Lambda handler code.
- Unresolved merge conflict markers:
  - `<<<<<<<`
  - `=======`
  - `>>>>>>>`
- `cdk.out/` committed to git.
- Template-managed workflow files modified locally:
  - `.github/workflows/ci_cd_cdk_app.yml`
  - `.github/workflows/ci_pr_cdk_app.yml`

## 11. Do Not Flag

- Repositories using `gds-idea-app-kit` that import `AppConfig` and `DeploymentConfig` from `gds_idea_cdk_constructs` instead of defining a local `config.py`.
- `AppConfig.from_pyproject()` for app-kit application config.
- `DeploymentConfig(cdk_env)` in real CDK app initialisation.
- `DeploymentConfig.from_dict(cdk_env, config)` in tests.
- `dep_config.environment` for environment comparisons.
- `dep_config.environment.friendly_name` for tags, display names, stack IDs, and readable resource names.
- `resolve_deployment_target()` when it validates `CDK_DEFAULT_ACCOUNT` and `CDK_DEFAULT_REGION` before constructing `cdk.Environment`.
- Account IDs centralised in a typed shared enum such as `DeploymentEnvironment`.
- CDK feature flags in `cdk.json`.
- `cdk.context.json` cache entries generated by the CDK CLI.
- Formatting issues already handled by ruff or other linters.
- Valid architectural choices that differ from personal preference.
- Existing app-specific `cdk.json` config when the PR does not add to it or depend on it in a new way.
- Typed config models reading from:
  - `config/` TOML or YAML files;
  - `pyproject.toml`;
  - model defaults.
- `print()` statements in CDK infrastructure code such as `app.py` or `stacks/**/*.py` when used for synth/deploy-time terminal output.
- Manual IAM `PolicyStatement`s when there is no suitable `.grant_*()` helper, provided the policy is scoped, justified, and auditable.

## 12. Expected App-Kit Pattern Summary

For app-kit repositories, the expected app initialisation pattern is:

```python
cfg = AppConfiguration()

app = cdk.App()

deployment_target = resolve_deployment_target()

cdk_env = cdk.Environment(
    account=deployment_target.account,
    region=deployment_target.region,
)

app_config = AppConfig.from_pyproject()
dep_config = DeploymentConfig(cdk_env)

Tags.of(app).add("Environment", dep_config.environment.friendly_name)
Tags.of(app).add("ManagedBy", "cdk")
Tags.of(app).add("Repository", cfg.tags.repository)
Tags.of(app).add("AppName", app_config.app_name)
Tags.of(app).add("Name", cfg.tags.display_name)
```

Stacks should receive typed config:

```python
storage_stack = StorageStack(
    app,
    sid("StorageStack"),
    app_config=app_config,
    dep_config=dep_config,
    env=cdk_env,
)
```

Stacks with dependencies should receive cross-stack references explicitly:

```python
processing_stack = ProcessingStack(
    app,
    sid("ProcessingStack"),
    app_config=app_config,
    dep_config=dep_config,
    storage=storage_stack,
    env=cdk_env,
)

processing_stack.add_dependency(storage_stack)
```

Unit tests should use `DeploymentConfig.from_dict(...)`:

```python
cdk_env = cdk.Environment(
    account=DeploymentEnvironment.DEVELOPMENT.value,
    region="eu-west-2",
)

dep_config = DeploymentConfig.from_dict(
    cdk_env,
    fake_deployment_config(account_id=DeploymentEnvironment.DEVELOPMENT.value),
)
```

The reviewer should not ask for a local config model when these shared constructs are used.