[CmdletBinding()]
param(
    [switch]$WriteStatement
)

$ErrorActionPreference = 'Stop'

$projectDirectory = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $projectDirectory '.env'

if (-not (Test-Path -LiteralPath $envPath)) {
    throw 'No existe .env. Copie .env.example como .env y configure sus credenciales.'
}

$envValues = Get-Content -LiteralPath $envPath -Raw |
    ConvertFrom-StringData

$requiredVariables = @(
    'LRSQL_API_KEY',
    'LRSQL_API_SECRET',
    'LRSQL_BIND_ADDRESS',
    'LRSQL_HTTP_PORT'
)

foreach ($variable in $requiredVariables) {
    if ([string]::IsNullOrWhiteSpace($envValues[$variable])) {
        throw "Falta la variable $variable en .env."
    }
}

$baseUrl = "http://$($envValues.LRSQL_BIND_ADDRESS):$($envValues.LRSQL_HTTP_PORT)"
$basicValue = [Convert]::ToBase64String(
    [Text.Encoding]::UTF8.GetBytes(
        "$($envValues.LRSQL_API_KEY):$($envValues.LRSQL_API_SECRET)"
    )
)
$headers = @{
    Authorization              = "Basic $basicValue"
    'X-Experience-API-Version' = '2.0.0'
}

$adminResponse = Invoke-WebRequest `
    -Uri "$baseUrl/admin" `
    -UseBasicParsing `
    -TimeoutSec 15

$aboutResponse = Invoke-RestMethod `
    -Uri "$baseUrl/xapi/about" `
    -Headers $headers `
    -TimeoutSec 15

[PSCustomObject]@{
    Check          = 'Lectura'
    AdminStatus    = $adminResponse.StatusCode
    XapiVersions   = $aboutResponse.version -join ', '
    Result         = 'OK'
}

if ($WriteStatement) {
    $statement = [ordered]@{
        actor  = [ordered]@{
            objectType = 'Agent'
            name       = 'Smoke test SQL LRS'
            mbox       = 'mailto:smoke-test@yet-lab.local'
        }
        verb   = [ordered]@{
            id      = 'http://adlnet.gov/expapi/verbs/experienced'
            display = @{ 'es-CL' = 'probó' }
        }
        object = [ordered]@{
            objectType = 'Activity'
            id         = 'urn:yet-lab:smoke-test'
            definition = @{
                name = @{ 'es-CL' = 'Prueba automatizada SQL LRS' }
            }
        }
    }

    $createdIds = Invoke-RestMethod `
        -Method Post `
        -Uri "$baseUrl/xapi/statements" `
        -Headers $headers `
        -ContentType 'application/json' `
        -Body ($statement | ConvertTo-Json -Depth 10 -Compress) `
        -TimeoutSec 15

    $statementId = [string]$createdIds[0]
    $storedStatement = Invoke-RestMethod `
        -Method Get `
        -Uri "$baseUrl/xapi/statements?statementId=$statementId" `
        -Headers $headers `
        -TimeoutSec 15

    if ($statementId -ne [string]$storedStatement.id) {
        throw 'El identificador leído no coincide con el Statement creado.'
    }

    [PSCustomObject]@{
        Check       = 'Escritura y lectura'
        StatementId = $statementId
        Result      = 'OK'
    }
}
