#!/usr/bin/env bash
# Pediatric Medication Prescriber Launch Script
# Starts both the Belgian Recip-e Mock Server and the Streamlit Clinical App

set -e

echo "👶 Starting Pediatric Prescriber Environment..."

# Ensure we are inside nix-shell or execute within it
if [ -z "$IN_NIX_SHELL" ]; then
    echo "⚡ Launching via nix-shell..."
    exec nix-shell --run "$0 $@"
fi

# 1. Start UHMEP / Recip-e Mock Server if not already running on port 8000
if ! nc -z localhost 8000 2>/dev/null; then
    echo "🏥 Starting Belgian UHMEP / Recip-e FHIR Mock Server on port 8000..."
    python "Case_Info/2. Pediatric Prescriber/server.py" --port 8000 &
    MOCK_PID=$!
    sleep 2
    echo "✅ Mock Server running with PID $MOCK_PID"
else
    echo "ℹ️ Mock Server already running on port 8000."
fi

# 2. Start Streamlit Application
echo "🚀 Starting Pediatric Prescriber Streamlit App on port 8501..."
streamlit run app.py --server.port 8501 --server.headless false
