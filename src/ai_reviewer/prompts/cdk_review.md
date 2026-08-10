# CDK Infrastructure Review Standards

Target: {repository} / PR #{pr_number}

This document defines CDK infrastructure standards for gds-idea projects. It
serves as both a human-readable reference and the automated reviewer's criteria.

**Scope:** `app.py`, `config.py`, `cdk.json`, `cdk.context.json`, `stacks/**/*.py`,
`lambda/**/*`, `app_src/Dockerfile` (if CDK references it), any file importing
`aws_cdk`/`aws_cdk_lib`, `tests/unit/test_*_stack.py`.

**Out of scope:** `cdk.out/`, `.venv/`, `node_modules/`, `__pycache__/`, `*.lock`.

## 1. Configuration & Environment

### Use typed config objects, not raw context lookups

- Environment config must use typed config objects (e.g. `AppConfig`,
  `DeploymentConfig`, Pydantic `BaseSettings`) — not raw `cdk.json` context
  lookups scattered through stack code.
- Untyped context lookups (`self.node.try_get_context("thing")`) return
  `Optional[str]`, have no validation, and crash at synth time with cryptic
  errors on typos.
- Account resolution needs no context lookups at all: `DeploymentConfig`
  (from `gds_idea_cdk_constructs`) resolves the environment directly from the
  AWS account of the IAM role calling `cdk deploy`/`cdk synth`. Flag any
  `try_get_context("phase")` or similar pattern used purely to select an
  account number — it is unnecessary indirection.
- All gds-idea repos must use `gds_idea_cdk_constructs` for this — do not
  flag "missing local config.py" when the shared library's
  `AppConfig`/`DeploymentConfig` already satisfy this standard. It depends
  only on `aws_cdk` and `boto3`, so pulling it in does not require the full
  `gds-idea-app-kit`.

**Bad:**
```python
# Fragile — no validation, string booleans, scattered everywhere
phase = app.node.try_get_context("phase")
deploy_emails = app.node.try_get_context("deploy_ses_infrastructure").lower() == "true"
account = app.node.try_get_context("prod_account_number")
```

**Also bad — raw dict lookups with manual type casting:**
```python
# No type safety: a typo like "athenaQueryBucket" silently returns None and
# fails much later. The str() cast hides the missing-key problem until runtime.
environments_ctx = app.node.try_get_context("environments") or {{}}
env_cfg = environments_ctx.get(deployment_env)
athena_queries_bucket_name = str(env_cfg["athenaQueriesBucket"])
```

**Good — use `gds_idea_cdk_constructs` (required for all gds-idea repos):**
```python
from gds_idea_cdk_constructs import AppConfig, DeploymentConfig, DeploymentEnvironment

app_config = AppConfig.from_pyproject()
dep_config = DeploymentConfig(cdk_env)  # resolves environment from the AWS account of the calling IAM role
```

```python
# app.py
import os

import aws_cdk as cdk
from gds_idea_cdk_constructs import AppConfig, DeploymentConfig

app = cdk.App()
app_config = AppConfig.from_pyproject()
cdk_env = cdk.Environment(
    account=os.environ["CDK_DEFAULT_ACCOUNT"],
    region=os.environ.get("CDK_DEFAULT_REGION", "eu-west-2"),
)
dep_config = DeploymentConfig(cdk_env)  # environment resolved from the calling role
```

### Model structured config with nested sub-models, not flat blobs

- When per-environment config has repeated or grouped structure (a list of
  datasets, a block of Athena settings, per-bucket options), model it with
  nested Pydantic sub-models (e.g. `DatasetConfig` inside `EnvironmentConfig`)
  rather than a flat bag of loosely related strings.
- Sub-models give each logical group its own validation, defaults, and
  autocomplete, and make the available configuration discoverable by reading
  the model instead of hunting through `cdk.json` for every `.get()` call.
- Config values must live in a dedicated config source loaded **through** the
  typed model — a `config/` directory (TOML/YAML), `pyproject.toml`, or the
  model's own defaults — **not** in `cdk.json`. The aim is to move config out of
  `cdk.json` entirely; treat any new app-specific values added to `cdk.json` as
  something to flag, even when they are later read via a typed wrapper.

**Good — nested, self-documenting config keyed by environment:**
```python
# config.py
from pydantic import BaseModel, field_validator


class DatasetConfig(BaseModel):
    table_name: str
    s3_bucket_name: str
    s3_prefix: str
    csv_delimiter: str = ","
    csv_quote: str = '"'


class EnvironmentConfig(BaseModel):
    environment: str  # "dev" or "prod" — passed in from DeploymentEnvironment.short_name
    glue_database_name: str
    athena_workgroup_name: str
    athena_queries_bucket: str
    create_source_buckets: bool = False
    datasets: list[DatasetConfig]

    @field_validator("datasets")
    @classmethod
    def _datasets_not_empty(cls, value: list[DatasetConfig]) -> list[DatasetConfig]:
        if not value:
            raise ValueError("At least one dataset must be configured")
        return value
```

```python
# app.py — DeploymentEnvironment resolves *which* environment; EnvironmentConfig
# holds the app-specific values *for* that environment. Keep the two separate:
# EnvironmentConfig never has an aws_account/aws_region field of its own.
from gds_idea_cdk_constructs import DeploymentEnvironment
from config import EnvironmentConfig

environment = DeploymentEnvironment.from_cdk_env(cdk_env)

env_config = EnvironmentConfig(
    environment=environment.short_name,
    glue_database_name=f"my-app-db-{{environment.short_name}}",
    athena_workgroup_name=f"my-app-wg-{{environment.short_name}}",
    athena_queries_bucket=f"my-app-athena-queries-{{environment.short_name}}",
    datasets=[...],
)
```

### Enforce environment parity and validate individual fields

- When the repo defines per-environment app-specific config (e.g. dataset
  lists, workgroup names, bucket names), a single model must be used to
  construct the config for **every** environment so nothing lets one
  environment gain or lose a field the other doesn't have. Adding a field for
  one environment and forgetting the other is a common, silent divergence.
- Add per-field validators for values with a known shape (e.g. bucket names
  non-empty, a datasets list that must contain at least one entry, workgroup
  names matching an expected pattern) so invalid config fails fast at synth
  time with a clear error, not at CloudFormation deploy or container runtime.
  See the `_datasets_not_empty` validator above for an example.
- Never validate or duplicate AWS account IDs/regions in this model — that is
  `DeploymentEnvironment`'s job. Use `dep_config.environment.short_name` (or
  `DeploymentEnvironment.from_cdk_env(cdk_env).short_name`) as the selector
  passed into the app-specific config, rather than a hand-rolled
  `friendly_name` translation or a locally re-validated account number.

### Keep cdk.json limited to entrypoint and feature flags

- `cdk.json` must contain ONLY the app entrypoint and CDK feature flags. The
  standing aim is to move away from `cdk.json` for configuration as far as
  possible — it should not grow new app-specific keys.
- No app-specific config values (table names, bucket names, account numbers,
  feature toggles, dataset definitions, environment blocks) belong there. These
  belong in a typed config model sourced from a `config/` directory (TOML/YAML),
  `pyproject.toml`, or the model's own defaults.
- Flag any PR that **adds to or extends** an app-specific config block in
  `cdk.json` (e.g. `context.environments`), and treat migrating existing values
  out as the preferred direction rather than leaving them in place.
- `cdk.json` is not validated at synth time, has no type safety, and is harder
  to review in PRs because it sits alongside ~60 lines of boilerplate flags.

### Derive account IDs and ARNs from config, never hardcode them

- AWS account IDs and ARNs must come from `DeploymentEnvironment` (imported
  from `gds_idea_cdk_constructs`) or other config objects, never as hardcoded
  string literals.
- Hardcoded account IDs create duplication, are easy to get wrong in
  copy-paste, and make it impossible to deploy to a new account without a
  repo-wide find-and-replace.

**Bad:**
```python
resources=["arn:aws:kms:eu-west-2:588077357019:key/dc126e48-..."]
```

**Good — cross-account ARN reference (e.g. a KMS key shared from prod):**
```python
from gds_idea_cdk_constructs import DeploymentEnvironment

resources=[
    f"arn:aws:kms:{{dep_config.cdk_env.region}}:{{DeploymentEnvironment.PRODUCTION.value}}:key/{{config.kms_key_id}}"
]
```

## 2. Stack Structure

### Split stacks by bounded concern, not by convenience

- One focused stack per bounded concern (storage, compute, networking,
  monitoring, secrets).
- Flag any single stack file exceeding ~300 lines as a candidate for splitting.
- Monolithic stacks make independent deployments impossible (a typo in a
  monitoring alarm forces redeployment of your database table) and create
  blast-radius risk.

**Bad:**
```python
class EverythingStack(Stack):
    # 600 lines: DynamoDB + Lambda + SQS + CloudWatch dashboard + alarms
```

**Good:**
```
stacks/
  storage.py           # DynamoDB tables, S3 buckets
  processing.py        # Lambda + SQS queue
  monitoring.py        # CloudWatch dashboard + alarms
```

### Pass a typed config object into every stack constructor

- Stacks must take a typed config object as a constructor keyword argument
  rather than many loose scalar parameters.
- A stack taking 10+ individual string kwargs makes it easy to transpose
  arguments and provides no IDE autocomplete.

**Bad:**
```python
def __init__(self, scope, id, project, phase, table_name, bucket_name,
             domain_name, vpc_id, cluster_name, region, account, **kwargs):
```

**Good:**
```python
def __init__(self, scope, construct_id, *, config: AppConfig,
             deployment_config: DeploymentConfig, **kwargs):
```

### Wire cross-stack references explicitly

- Cross-stack references must be passed as constructor parameters with
  explicit `.add_dependency()` calls in `app.py`, not via `Fn::ImportValue`
  or by reaching into another stack's internals.

## 3. Directory Layout

### Separate infrastructure from application source

- Infrastructure (`app.py`, `stacks/`, `config.py`, `cdk.json`) lives at repo
  root. Application/function source code lives in dedicated subdirectories.
- A consistent layout means any developer (or AI reviewer) can navigate the
  repo without reading documentation, and prevents infrastructure concerns
  leaking into application code.

```
app.py              # CDK entrypoint — stack instantiation and wiring only
config.py           # Typed config objects (or imported from shared library)
cdk.json            # App entrypoint + CDK feature flags ONLY
stacks/             # One file per stack (infrastructure definitions)
  storage.py
  processing.py
lambda/             # Lambda function source code
  webhook_receiver/ # Subfolder name matches function reference in CDK
    handler.py
    Dockerfile
    requirements.txt  # or pyproject.toml for Lambda's own deps
  upload_processor/
    handler.py
    Dockerfile
    pyproject.toml
app_src/            # Application source (convention for deployed apps e.g. FastAPI, Streamlit)
  Dockerfile
  main.py
  pyproject.toml
tests/
  unit/             # CDK assertion tests (Template.from_stack)
```

### Put deployed application source in app_src/

- If the repo deploys an application (web app, API), its source must live in
  an `app_src/` folder — not mixed into the root alongside CDK infrastructure
  files.
- Infrastructure and application code have different dependency trees,
  different test suites, and different deployment lifecycles. Mixing them
  creates confusion about which `pyproject.toml` manages which dependencies.

### Give each Lambda function its own subfolder

- Lambda source code must live in a `lambda/` directory with one subfolder
  per Lambda function.
- Each subfolder should contain the handler source, a Dockerfile, and a
  dependency manifest (`requirements.txt` or `pyproject.toml`).
- The subfolder name should match how the Lambda function is referenced in CDK.
- One folder per function makes it trivial to find the source for any Lambda
  defined in a stack, and keeps each Lambda self-contained and buildable in
  isolation.

### Use structured logging in Lambda handlers, not print()

- Lambda handler code must use Python's `logging` module instead of
  `print()` statements.
- Each handler should include at least one or two logging statements that
  track what's happening during execution (e.g. receiving an event, a key
  decision point, completion) — the exact number and placement beyond that
  minimum is left to the author's judgement.
- This applies to Lambda handler code only. `print()` statements are
  acceptable in CDK stack/infrastructure code for surfacing debugging output
  during synth/deploy (see Anti-Patterns).
- `print()` output is unstructured and harder to filter/query in CloudWatch
  Logs Insights; `logging` supports log levels and integrates automatically
  with CloudWatch once deployed.

**Bad:**
```python
def handler(event, context):
    print(f"Processing event: {{json.dumps(event)}}")
    result = process(event)
    print(f"Result: {{result}}")
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

### Use .grant_*() methods over manual PolicyStatements

- S3 buckets, DynamoDB tables, Secrets Manager secrets, SSM parameters, SQS
  queues, and SNS topics all support `.grant_*()` methods.
- These methods automatically scope permissions to the specific resource ARN
  and manage CDK dependency ordering.
- Manual `PolicyStatement` construction is verbose, error-prone (ARN typos),
  and misses the automatic dependency wiring that `.grant_*()` provides.

**Bad:**
```python
lambda_role.add_to_policy(iam.PolicyStatement(
    actions=["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
    resources=[f"arn:aws:s3:::{{bucket_name}}", f"arn:aws:s3:::{{bucket_name}}/*"],
))
```

**Good:**
```python
data_bucket.grant_read_write(lambda_role)
```

### Require sid and justification for any wildcard resource

- `resources=["*"]` is only permitted when the AWS action genuinely has no
  resource-level ARN support.
- Must include a `sid=` parameter naming the permission's purpose.
- Must include an inline comment explaining why scoping is not possible.
- Overly broad permissions are a security risk and violate least-privilege.
  The `sid` makes the policy auditable in the IAM console; the comment
  prevents future developers from assuming it was laziness.

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
    actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
    resources=["*"],  # Bedrock InvokeModel has no resource-level ARN support
))
```

### Keep IAM logic inside stacks, not in app.py

- `app.py` should only wire stacks together and set top-level config.
- Permission-granting logic belongs inside stacks, constructs, or a shared
  helper module (e.g. `stacks/shared/iam.py`) — not in `app.py`.
- When IAM logic lives in `app.py`, it becomes a dumping ground that grows
  indefinitely, mixes permission concerns with stack orchestration, and makes
  it hard to find where a role's permissions are defined.
- Moving raw `PolicyStatement` blocks out of `app.py` into a standalone
  file is only half the improvement. A 100-line file of ungrouped policy
  statements is still hard to audit and reuse. Shared IAM helpers must be
  named functions that describe their intent (e.g. `grant_bedrock_invoke()`,
  `grant_read_athena()`) — each taking a `grantee` parameter and
  encapsulating one logical permission concern. This makes permissions
  self-documenting, composable, and easy to grep for when auditing access.

**Bad — IAM logic dumped in `app.py`:**
```python
# app.py — mixing stack wiring with permission details
storage_stack = StorageStack(app, "StorageStack", config=config, env=env)
processing_stack = ProcessingStack(app, "ProcessingStack", config=config, env=env)

# This doesn't belong here — app.py now has to know which specific actions
# the Lambda needs on which specific resources
processing_stack.lambda_function.add_to_role_policy(iam.PolicyStatement(
    actions=["s3:GetObject", "s3:PutObject"],
    resources=[storage_stack.bucket.bucket_arn + "/*"],
))
processing_stack.lambda_function.add_to_role_policy(iam.PolicyStatement(
    actions=["dynamodb:Query", "dynamodb:PutItem"],
    resources=[storage_stack.table.table_arn],
))
```

**Still bad — raw statements just relocated to another file:**
```python
# stacks/shared/iam.py — a wall of ungrouped PolicyStatements
def add_all_permissions(lambda_function):
    """This is just the app.py slop relocated — no abstraction, no names."""
    lambda_function.add_to_role_policy(iam.PolicyStatement(
        actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
        resources=["*"],
    ))
    lambda_function.add_to_role_policy(iam.PolicyStatement(
        actions=["athena:StartQueryExecution", "athena:GetQueryExecution", "athena:GetQueryResults"],
        resources=["*"],
    ))
    lambda_function.add_to_role_policy(iam.PolicyStatement(
        actions=["s3:GetObject", "s3:PutObject"],
        resources=[...],
    ))
    # ... 80 more lines of the same
```

**Good — permissions encapsulated inside the stack that owns the resource:**
```python
# app.py — just wiring, no IAM details
storage_stack = StorageStack(app, "StorageStack", config=config, env=env)
processing_stack = ProcessingStack(app, "ProcessingStack", config=config,
                                    storage=storage_stack, env=env)
processing_stack.add_dependency(storage_stack)
```

```python
# stacks/processing.py — owns its own permissions
class ProcessingStack(Stack):
    def __init__(self, scope, construct_id, *, config: AppConfig,
                 storage: StorageStack, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        self.lambda_function = _lambda.DockerImageFunction(...)

        # Permissions live with the resource that needs them
        storage.bucket.grant_read_write(self.lambda_function)
        storage.table.grant_read_write_data(self.lambda_function)
        grant_bedrock_invoke(self.lambda_function)  # shared helper, named by intent
```

**Good — named helpers, one logical concern each, generic `grantee` parameter:**
```python
# stacks/shared/iam.py — each function is one auditable permission grant
def grant_bedrock_invoke(grantee: iam.IGrantable) -> None:
    """Grant Bedrock model invocation. Uses resources=* because
    Bedrock InvokeModel has no resource-level ARN support."""
    grantee.grant_principal.add_to_principal_policy(iam.PolicyStatement(
        sid="InvokeBedrock",
        actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
        resources=["*"],  # No resource-level ARN support for these actions
    ))


def grant_read_athena(grantee: iam.IGrantable, *, workgroup_arn: str) -> None:
    """Grant read-only Athena query access scoped to a workgroup."""
    grantee.grant_principal.add_to_principal_policy(iam.PolicyStatement(
        sid="ReadAthena",
        actions=["athena:StartQueryExecution", "athena:GetQueryExecution", "athena:GetQueryResults"],
        resources=[workgroup_arn],
    ))
```

## 5. Naming Conventions

### Use a consistent construct ID prefix pattern

- Construct IDs (the second positional argument to any CDK construct) must
  follow a consistent `{{project}}-{{PascalCaseResource}}` pattern.

### Suffix physical resource names with the environment

- Physical resource names (bucket_name, function_name, role_name, etc.) must
  include an environment/phase suffix when deploying to a shared AWS account:
  `{{project}}-{{resource}}-{{phase}}`.
- Without an environment suffix, deploying both dev and prod to the same
  account causes name collisions.

**Bad:**
```python
function_name="evidence-base-upload-processor"  # No env suffix — will collide
```

**Good — explicit f-string using shared-library primitives:**
```python
from gds_idea_cdk_constructs import AppConfig, DeploymentConfig

app_config = AppConfig.from_pyproject()
dep_config = DeploymentConfig(cdk_env)

function_name = f"{{app_config.app_name}}-upload-processor-{{dep_config.environment.short_name}}"
# produces: "my-app-upload-processor-dev"
```

### Derive stack IDs from a single consistent pattern

- Stack IDs should be derived from a consistent utility or pattern (e.g.
  `f"{{app_name}}-{{StackName}}-{{phase}}"` or a `StackId` helper), not
  ad-hoc strings that vary in style across `app.py`.
- Without a shared utility, each stack instantiation risks a different
  convention (no prefix, no phase, different casing), and renaming the
  project or phase requires a repo-wide find-and-replace instead of a
  one-line change.

**Bad — inconsistent, ad-hoc stack IDs:**
```python
# Each stack picks a different convention
StorageStack(app, "StorageStack", app_config=app_config, deployment_config=dep_config, env=cdk_env)                     # no prefix, no phase
ProcessingStack(app, "ai-pqs-ProcessingStack", app_config=app_config, deployment_config=dep_config, env=cdk_env)        # prefix but no phase
SecretsStack(app, f"{{project}}-secrets-stack-{{phase}}", app_config=app_config, deployment_config=dep_config, env=cdk_env)  # kebab-case, different style
```

**Good — a single `StackId` helper enforces the pattern:**
```python
# stacks/shared/stack_id.py
from gds_idea_cdk_constructs import AppConfig, DeploymentConfig


class StackId:
    """Generates consistent CDK stack IDs from config."""

    def __init__(self, project: str, phase: str):
        self.project = project
        self.phase = phase

    @classmethod
    def from_config(cls, app_config: AppConfig, dep_config: DeploymentConfig) -> "StackId":
        return cls(project=app_config.app_name, phase=dep_config.environment.short_name)

    def __call__(self, stack_name: str) -> str:
        return f"{{self.project}}-{{stack_name}}-{{self.phase}}"
```

```python
# app.py
import os

import aws_cdk as cdk
from gds_idea_cdk_constructs import AppConfig, DeploymentConfig

app = cdk.App()
app_config = AppConfig.from_pyproject()
cdk_env = cdk.Environment(
    account=os.environ["CDK_DEFAULT_ACCOUNT"],
    region=os.environ.get("CDK_DEFAULT_REGION", "eu-west-2"),
)
dep_config = DeploymentConfig(cdk_env)  # environment resolved from the calling role
sid = StackId.from_config(app_config, dep_config)

# Every stack ID is now guaranteed consistent: "ai-pqs-StorageStack-dev"
storage = StorageStack(app, sid("StorageStack"), app_config=app_config, deployment_config=dep_config, env=cdk_env)
secrets = SecretsStack(app, sid("SecretsStack"), app_config=app_config, deployment_config=dep_config, env=cdk_env)
processing = ProcessingStack(app, sid("ProcessingStack"), app_config=app_config, deployment_config=dep_config, env=cdk_env)
```

## 6. Tagging

### Apply two tiers of tags: app-level and per-resource

- **App-level** (via `Tags.of(app).add(...)` in `app.py`): `Environment`,
  `ManagedBy`, `Repository`, `AppName`.
- **Per-resource** (within stacks): `ResourceType`, `Service`.
- Tags are the primary mechanism for cost allocation, security auditing, and
  resource ownership. Missing tags mean unattributed costs and orphaned
  resources that nobody knows who owns.

**Bad:**
```python
Tags.of(app).add("Repository", "TBA")  # Placeholder shipped to production
```

**Good:**
```python
Tags.of(app).add("Repository", "co-cddo/my-project")
Tags.of(self).add("ResourceType", "DynamoDB")
Tags.of(self).add("Service", "Storage")
```

### Flag placeholder tag values

- Placeholder tag values (e.g. `"TBA"`, `"TODO"`, `"changeme"`) must be
  resolved before merging.

## 7. Removal Policy

### Set an explicit removal policy on every stateful resource

- Every stateful resource (DynamoDB tables, S3 data buckets, RDS instances,
  Elasticsearch domains) must have an explicit `removal_policy` set.
- CDK's default removal policy varies by resource type and CDK version —
  relying on the default means unpredictable behaviour. Being explicit
  prevents accidental data loss on `cdk destroy`.

### Retain source-of-truth data, destroy only transient resources

- Source-of-truth application data must use `RemovalPolicy.RETAIN` (or
  phase-conditional: `RETAIN` in prod, `DESTROY` in dev).
- Transient or regenerable resources (upload staging buckets, log groups,
  caches) may use `RemovalPolicy.DESTROY` with a clear justification.

**Bad:**
```python
# Production paper database — DESTROY means cdk destroy deletes all data
table = dynamodb.Table(self, "PapersTable", ...,
    removal_policy=RemovalPolicy.DESTROY)
```

**Good:**
```python
from gds_idea_cdk_constructs import DeploymentEnvironment

removal = (
    RemovalPolicy.DESTROY if dep_config.environment == DeploymentEnvironment.DEVELOPMENT else RemovalPolicy.RETAIN
)
table = dynamodb.Table(self, "PapersTable", ...,
    removal_policy=removal,
    point_in_time_recovery=True)
```

## 8. Testing

### Cover IAM permissions, tags, and removal policy at minimum

- CDK apps should have unit tests using `aws_cdk.assertions` that verify at
  minimum:
  - IAM roles have the expected managed policies and permission statements
  - Tags are applied as expected
  - Removal policies are phase-conditional on stateful resources (DynamoDB
    tables, S3 data buckets, RDS instances) — `RETAIN` in prod, `DESTROY` in dev
- Without CDK tests, the only verification is `cdk synth` (checks syntax, not
  behaviour) or manual inspection of `cdk diff` output. Assertion tests catch
  regressions before they reach deployment.

### Validate every environment's config on every PR

- When the repo defines a typed config model, add a test that instantiates the
  model for **each** environment (`dev` and `prod`) so invalid or divergent
  config fails in CI, not at deploy time.
- This guards environment parity (both environments must satisfy the same
  model) and exercises any per-field validators, satisfying the "invalid config
  fails fast with a clear error" bar.

**Example config-validation test:**
```python
import pytest

from config import DatasetConfig, EnvironmentConfig


@pytest.mark.parametrize("environment", ["dev", "prod"])
def test_environment_config_is_valid(environment: str):
    # Construction raises pydantic.ValidationError if any field is missing,
    # mistyped, or fails a field validator — so a passing test proves both
    # environments satisfy the same model.
    env_config = EnvironmentConfig(
        environment=environment,
        glue_database_name=f"my-app-db-{{environment}}",
        athena_workgroup_name=f"my-app-wg-{{environment}}",
        athena_queries_bucket=f"my-app-athena-queries-{{environment}}",
        datasets=[DatasetConfig(table_name="papers", s3_bucket_name=f"my-app-papers-{{environment}}", s3_prefix="raw/")],
    )
    assert env_config.environment == environment
```

**Example test patterns:**

```python
# Fixtures: instantiate the stack per environment using DeploymentEnvironment
# (no real AWS calls, no hardcoded account IDs)
from gds_idea_cdk_constructs import DeploymentEnvironment


@pytest.fixture
def dev_template():
    app = cdk.App()
    cdk_env = cdk.Environment(account=DeploymentEnvironment.DEVELOPMENT.value, region="eu-west-2")
    stack = StorageStack(app, "TestStorage", env=cdk_env)
    return assertions.Template.from_stack(stack)


@pytest.fixture
def prod_template():
    app = cdk.App()
    cdk_env = cdk.Environment(account=DeploymentEnvironment.PRODUCTION.value, region="eu-west-2")
    stack = StorageStack(app, "TestStorage", env=cdk_env)
    return assertions.Template.from_stack(stack)

# Test IAM scoping
def test_lambda_role_has_scoped_permissions(dev_template):
    dev_template.has_resource_properties("AWS::IAM::Policy", {{
        "PolicyDocument": {{
            "Statement": assertions.Match.array_with([
                assertions.Match.object_like({{
                    "Action": "secretsmanager:GetSecretValue",
                    "Resource": assertions.Match.string_like_regexp(r"arn:aws:secretsmanager:.*"),
                }})
            ])
        }}
    }})

# Test tags
def test_table_has_resource_type_tag(dev_template):
    dev_template.has_resource_properties("AWS::DynamoDB::Table", {{
        "Tags": assertions.Match.array_with([
            assertions.Match.object_like({{"Key": "ResourceType", "Value": "DynamoDB"}}),
        ]),
    }})

# Test removal policy is phase-conditional (applies to any stateful
# resource — DynamoDB, S3, RDS, etc.)
def test_table_is_retained_in_prod(prod_template):
    prod_template.has_resource("AWS::DynamoDB::Table", {{
        "DeletionPolicy": "Retain",
        "UpdateReplacePolicy": "Retain",
    }})

def test_table_is_destroyed_in_dev(dev_template):
    dev_template.has_resource("AWS::DynamoDB::Table", {{
        "DeletionPolicy": "Delete",
        "UpdateReplacePolicy": "Delete",
    }})
```

### Mock AWS calls in tests — never hit real infrastructure

- Tests must use `DeploymentEnvironment.DEVELOPMENT.value` /
  `DeploymentEnvironment.PRODUCTION.value` (from `gds_idea_cdk_constructs`) to
  set the CDK Environment account, or `DeploymentConfig.from_dict()` for
  repos that also need Parameter Store-backed config — never call real AWS
  APIs during testing.

## 9. Anti-Patterns to Flag

- **Hardcoded AWS account IDs or ARNs** as string literals in stack code
- **Defining a local `DeploymentEnvironment` enum with hardcoded account IDs**
  — `DeploymentConfig` and `DeploymentEnvironment` from `gds_idea_cdk_constructs`
  resolve the environment from the calling IAM role automatically; duplicating
  account IDs locally is redundant and creates drift risk
- **App-specific config values in `cdk.json`** context block (table names,
  bucket names, feature toggles)
- **Raw dict/context lookups with manual type casting** (`str(env_cfg["key"])`,
  `... or {{}}` fallbacks) instead of loading through a typed model
- **Config accessed via string keys** scattered across `app.py`/stacks rather
  than typed attribute access with autocomplete
- **Environment config that isn't validated for both `dev` and `prod`** by the
  same model (silent shape divergence between environments)
- **Live AWS API calls at synth time** (boto3 calls in `app.py` that make
  `cdk synth` dependent on credentials/network)
- **Unresolved merge conflict markers** (`<<<<<<<`, `=======`, `>>>>>>>`)
- **`cdk.out/` committed to git** (should be in `.gitignore`)
- **No `.add_dependency()` calls** between stacks that have cross-stack
  references
- **Application code mixed into root level** instead of `app_src/` or `lambda/`
- **Lambda source not in its own subfolder** under `lambda/`
- **`print()` statements in Lambda handler code** — must use `logging`
  instead (see Directory Layout for the full standard)
- **Template-managed workflow files modified locally**
  (`.github/workflows/ci_cd_cdk_app.yml`, `ci_pr_cdk_app.yml` are managed by
  `gds-idea-app-kit` and must not be edited directly)
- **IAM permissions relocated but not refactored** — moving raw
  `PolicyStatement` blocks out of `app.py` into a `permissions.py`/`iam.py`
  file without grouping them into named, single-purpose helper functions
  (e.g. `grant_bedrock_invoke()`, `grant_read_athena()`) is only a partial fix

### Do NOT flag

- CDK feature flags in `cdk.json` (boilerplate, not custom code)
- `cdk.context.json` cache entries (auto-generated by CDK CLI)
- Formatting issues already handled by ruff or other linters
- Choices that are valid but different from a personal preference (e.g.
  separate accounts per environment vs. shared account with phase suffix —
  both are valid)
- A typed config model reading from `config/` (TOML/YAML), `pyproject.toml`, or
  its own defaults — these are the preferred homes; do not insist config move to
  yet another location once it is already out of `cdk.json` and typed
- **`print()` statements in stack/infrastructure code** (`app.py`,
  `stacks/**/*.py`) — these are acceptable for surfacing synth/deploy-time
  debugging output in the terminal; only Lambda handler code requires
  `logging`
