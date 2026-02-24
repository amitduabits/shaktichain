param(
  [string]$EnvFile = "docker/.env.dev.example"
)

$ErrorActionPreference = "Stop"

docker compose --env-file $EnvFile --profile dev up --build
