#!/bin/bash
# WellSky FHIR API Integration Test Runner
# Quick script to run integration tests with different configurations

set -e

echo "=========================================="
echo "WellSky FHIR API Integration Test Runner"
echo "=========================================="
echo ""

# Check if credentials are set
if [ -z "$WELLSKY_CLIENT_ID" ]; then
    echo "⚠️  No credentials found - will run in MOCK MODE"
    echo ""
    echo "To test with real API, set:"
    echo "  export WELLSKY_CLIENT_ID=your-client-id"
    echo "  export WELLSKY_CLIENT_SECRET=your-client-secret"
    echo "  export WELLSKY_AGENCY_ID=your-agency-id"
    echo "  export WELLSKY_ENVIRONMENT=sandbox"
    echo ""
    read -p "Continue with mock mode? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Change to project directory
cd "$(dirname "$0")/.."

# Run tests
echo ""
echo "Running integration tests..."
echo ""

python3 tests/test_wellsky_integration.py

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo ""
    echo "✅ Tests completed successfully!"
else
    echo ""
    echo "❌ Tests failed - see errors above"
fi

exit $exit_code
