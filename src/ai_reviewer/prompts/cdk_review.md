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
- The one acceptable raw context lookup is `phase` (or an equivalent single
  selector) — it gates entry into the typed config system. It's validated
  immediately, and everything else (account number, region, resource names)
  is derived from that single value.
- If the repo uses `gds-idea-app-kit`, config should come from
  `gds_idea_cdk_constructs` — do not flag "missing local config.py" in that
  case; the shared library's `AppConfig`/`DeploymentConfig` already satisfy
  this standard.

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

**Good — import from shared library (preferred for app-kit repos):**
```python
from gds_idea_cdk_constructs import AppConfig, DeploymentConfig

app_config = AppConfig.from_pyproject()
dep_config = DeploymentConfig(cdk_env)  # environment derived from AWS account ID
```

**Good — local Pydantic BaseModel (when building config from scratch):**
```python
# config.py
from enum import Enum
from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings


class DeploymentEnvironment(Enum):
    DEVELOPMENT = "992382722318"
    PRODUCTION = "588077357019"


class AppConfig(BaseSettings):
    phase: Literal["dev", "prod"]
    project: str = "my-app"

    @computed_field
    @property
    def account_number(self) -> str:
        env = DeploymentEnvironment.DEVELOPMENT if self.phase == "dev" else DeploymentEnvironment.PRODUCTION
        return env.value

    @computed_field
    @property
    def region(self) -> str:
        return "eu-west-2"

    def resource_name(self, resource: str) -> str:
        return f"{{self.project}}-{{resource}}-{{self.phase}}"
```

```python
# app.py
app = cdk.App()
phase = app.node.try_get_context("phase") or "dev"  # single permitted context lookup
config = AppConfig(phase=phase)  # everything else derived from here
env = cdk.Environment(account=config.account_number, region=config.region)
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

**Good — nested, self-documenting config:**
```python
# config.py
from pydantic import BaseModel


class DatasetConfig(BaseModel):
    table_name: str
    s3_bucket_name: str
    s3_prefix: str
    csv_delimiter: str = ","
    csv_quote: str = '"'


class EnvironmentConfig(BaseModel):
    aws_account: str
    aws_region: str = "eu-west-2"
    glue_database_name: str
    athena_workgroup_name: str
    athena_queries_bucket: str
    create_source_buckets: bool = False
    datasets: list[DatasetConfig]
```

### Enforce environment parity and validate individual fields

- A single config model must define **both** `dev` and `prod` so nothing lets
  one environment gain or lose a field the other doesn't have. Adding a field
  to one environment and forgetting the other is a common, silent divergence.
- Add per-field validators for values with a known shape (e.g. AWS account IDs
  must be 12 digits, bucket names non-empty, regions from an allowed set) so
  invalid config fails fast at synth time with a clear error, not at
  CloudFormation deploy or container runtime.
- Prefer resolving the environment from the deployment context over duplicating
  account IDs/regions in config. Where the shared library exposes it (e.g.
  `dep_config.environment.short_name` returning `"dev"`/`"prod"`), use it
  directly rather than a hand-rolled `friendly_name` translation.

**Good — field-level validation with a clear, early failure:**
```python
from pydantic import BaseModel, field_validator


class EnvironmentConfig(BaseModel):
    aws_account: str

    @field_validator("aws_account")
    @classmethod
    def _account_is_twelve_digits(cls, value: str) -> str:
        if not (value.isdigit() and len(value) == 12):
            raise ValueError(f"aws_account must be 12 digits, got {{value!r}}")
        return value
```

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

- AWS account IDs and ARNs must come from config objects or enums (e.g.
  `DeploymentEnvironment.PRODUCTION.value`), never as hardcoded string literals.
- Hardcoded account IDs create duplication, are easy to get wrong in
  copy-paste, and make it impossible to deploy to a new account without a
  repo-wide find-and-replace.

**Bad:**
```python
resources=["arn:aws:kms:eu-west-2:588077357019:key/dc126e48-..."]
```

**Good:**
```python
resources=[f"arn:aws:kms:{{config.region}}:{{DeploymentEnvironment.PRODUCTION.value}}:key/{{config.kms_key_id}}"]
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
        grant_bedrock_invoke(self.lambda_function)  # shared helper
```

```python
# stacks/shared/iam.py — DRY helper for repeated permission patterns
def grant_bedrock_invoke(grantee: _lambda.Function) -> None:
    """Grant Bedrock model invocation. Uses resources=* because
    Bedrock InvokeModel has no resource-level ARN support."""
    grantee.add_to_role_policy(iam.PolicyStatement(
        sid="InvokeBedrock",
        actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
        resources=["*"],  # No resource-level ARN support for these actions
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

**Good — using the config helper method:**
```python
function_name=config.resource_name("upload-processor")
# produces: "my-app-upload-processor-dev"
```

**Good — explicit f-string (same result, more visible):**
```python
function_name=f"{{config.project}}-upload-processor-{{config.phase}}"
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
StorageStack(app, "StorageStack", config=config, env=env)                     # no prefix, no phase
ProcessingStack(app, "ai-pqs-ProcessingStack", config=config, env=env)        # prefix but no phase
SecretsStack(app, f"{{project}}-secrets-stack-{{phase}}", config=config, env=env)  # kebab-case, different style
```

**Good — a single `StackId` helper enforces the pattern:**
```python
# config.py
class StackId:
    """Generates consistent CDK stack IDs from config."""

    def __init__(self, project: str, phase: str):
        self.project = project
        self.phase = phase

    @classmethod
    def from_config(cls, config: AppConfig) -> "StackId":
        return cls(project=config.project, phase=config.phase)

    def __call__(self, stack_name: str) -> str:
        return f"{{self.project}}-{{stack_name}}-{{self.phase}}"
```

```python
# app.py
app = cdk.App()
phase = app.node.try_get_context("phase") or "dev"
config = AppConfig(phase=phase)
sid = StackId.from_config(config)
env = cdk.Environment(account=config.account_number, region=config.region)

# Every stack ID is now guaranteed consistent: "ai-pqs-StorageStack-dev"
storage = StorageStack(app, sid("StorageStack"), config=config, env=env)
secrets = SecretsStack(app, sid("SecretsStack"), config=config, env=env)
processing = ProcessingStack(app, sid("ProcessingStack"), config=config, env=env)
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
removal = RemovalPolicy.DESTROY if config.phase == "dev" else RemovalPolicy.RETAIN
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


@pytest.mark.parametrize("phase", ["dev", "prod"])
def test_environment_config_is_valid(phase: str):
    # Construction raises pydantic.ValidationError if any field is missing,
    # mistyped, or fails a field validator — so a passing test proves both
    # environments satisfy the same model.
    config = AppConfig(phase=phase)
    assert config.account_number.isdigit()
```

**Example test patterns:**

```python
# Fixtures: instantiate the stack per environment using AppConfig
# (no real AWS calls, no hardcoded account IDs)
@pytest.fixture
def dev_template():
    app = cdk.App()
    config = AppConfig(phase="dev")
    stack = StorageStack(app, "TestStorage", config=config,
                         env=cdk.Environment(account=config.account_number, region=config.region))
    return assertions.Template.from_stack(stack)

@pytest.fixture
def prod_template():
    app = cdk.App()
    config = AppConfig(phase="prod")
    stack = StorageStack(app, "TestStorage", config=config,
                         env=cdk.Environment(account=config.account_number, region=config.region))
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

- Tests must use `AppConfig(phase="dev")` (or `DeploymentConfig.from_dict()`
  for shared-library repos) — never call real AWS APIs during testing.

## 9. Anti-Patterns to Flag

- **Hardcoded AWS account IDs or ARNs** as string literals in stack code
- **App-specific config values in `cdk.json`** context block (table names,
  bucket names, feature toggles)
- **Raw dict/context lookups with manual type casting** (`str(env_cfg["key"])`,
  `... or {}` fallbacks) instead of loading through a typed model
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
