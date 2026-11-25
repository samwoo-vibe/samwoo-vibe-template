$ErrorActionPreference = "Stop"

Push-Location frontend
try {
    npm run dev -- --host 127.0.0.1
}
finally {
    Pop-Location
}

