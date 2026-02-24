param(
  [string]$EnvFile = "docker/.env.dev.example"
)

$ErrorActionPreference = "Stop"

docker compose --env-file $EnvFile --profile test up --build --abort-on-container-exit --exit-code-from all-tests-pass all-tests-pass
