param(
  [string]$EnvFile = "docker/.env.prod.example"
)

$ErrorActionPreference = "Stop"

docker compose --env-file $EnvFile --profile prod up -d --build
