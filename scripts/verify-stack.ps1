<#
.SYNOPSIS
  Verifies the Docker and Kubernetes deployments of the Payment & Notification Engine.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\scripts\verify-stack.ps1
#>
param(
    [string]$Namespace = "payment-engine",
    [int]$DockerBackendPort = 5000,
    [int]$DockerFrontendPort = 8081,
    [int]$BackendNodePort = 30500,
    [int]$FrontendNodePort = 30080
)

$script:failures = 0

function Test-Endpoint([string]$Name, [string]$Url) {
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
        Write-Host ("[PASS] {0,-28} {1} -> HTTP {2}" -f $Name, $Url, $r.StatusCode) -ForegroundColor Green
    } catch {
        Write-Host ("[FAIL] {0,-28} {1} -> {2}" -f $Name, $Url, $_.Exception.Message) -ForegroundColor Red
        $script:failures++
    }
}

Write-Host "`n=== Docker containers ===" -ForegroundColor Cyan
docker ps --filter "name=payment-" --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"

Write-Host "`n=== Docker images ===" -ForegroundColor Cyan
docker images --filter "reference=payment-*" --format "table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.CreatedSince}}"

Write-Host "`n=== Kubernetes ($Namespace) ===" -ForegroundColor Cyan
kubectl get deploy,pods,svc -n $Namespace -o wide

Write-Host "`n=== Endpoint checks ===" -ForegroundColor Cyan
Test-Endpoint "Docker backend /health"     "http://localhost:$DockerBackendPort/health"
Test-Endpoint "Docker frontend /healthz"   "http://localhost:$DockerFrontendPort/healthz"
Test-Endpoint "K8s backend NodePort"       "http://localhost:$BackendNodePort/health"
Test-Endpoint "K8s frontend NodePort"      "http://localhost:$FrontendNodePort/healthz"
Test-Endpoint "K8s frontend -> backend"    "http://localhost:$FrontendNodePort/backend-health"

Write-Host "`n=== End-to-end payment via K8s frontend ===" -ForegroundColor Cyan
try {
    $body = @{ payer = "Verifier"; payee = "Merchant"; amount = 250.75; currency = "INR"; method = "UPI" } | ConvertTo-Json
    $res = Invoke-RestMethod -Method Post -Uri "http://localhost:$FrontendNodePort/api/payments" -ContentType "application/json" -Body $body -TimeoutSec 5
    Write-Host "[PASS] Payment $($res.payment.id) $($res.payment.status)" -ForegroundColor Green
    Write-Host "       Notification: $($res.notification.message)"
} catch {
    Write-Host "[FAIL] POST /api/payments -> $($_.Exception.Message)" -ForegroundColor Red
    $script:failures++
}

Write-Host ""
if ($script:failures -eq 0) {
    Write-Host "ALL CHECKS PASSED" -ForegroundColor Green
    exit 0
} else {
    Write-Host "$script:failures CHECK(S) FAILED" -ForegroundColor Red
    exit 1
}
