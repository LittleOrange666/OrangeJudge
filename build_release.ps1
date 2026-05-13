### build.ps1

if (-not $args[0]) {
    Write-Host "version is required for the release build" -ForegroundColor Red
    Write-Host "Usage: .\$($MyInvocation.MyCommand.Name) <version>"
    exit 1
}

$version = $args[0]
$imageName = "littleorange666/orange_judge"

Write-Host "Building version $version" -ForegroundColor Cyan
docker build . -t "${imageName}:$version"

if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker build for version $version failed!" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "Pushing version $version" -ForegroundColor Cyan
docker push "${imageName}:$version"

Write-Host "Building latest" -ForegroundColor Cyan
docker build . -t "${imageName}:latest"

if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker build for latest failed!" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "Pushing latest" -ForegroundColor Cyan
docker push "${imageName}:latest"

Write-Host "Successfully built and pushed version $version and latest." -ForegroundColor Green