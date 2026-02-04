#!/usr/bin/env bash

set -euo pipefail

PORTAL_URL=${PORTAL_URL:-"https://portal-coloradocareassist-3e1a4bb34793.mac-miniapp.com"}
SALES_URL=${SALES_DASHBOARD_URL:-"https://careassist-tracker-0fcf2cecdb22.mac-miniapp.com"}
ACTIVITY_URL=${ACTIVITY_TRACKER_URL:-"https://cca-activity-tracker-6d9a1d8e3933.mac-miniapp.com"}
RECRUITER_URL=${RECRUITER_DASHBOARD_URL:-"https://caregiver-lead-tracker-9d0e6a8c7c20.mac-miniapp.com"}

function resolve_sales_bundle() {
  if [[ -n "${SALES_BUNDLE_PATH:-}" ]]; then
    echo "$SALES_BUNDLE_PATH"
    return 0
  fi

  local manifest="dashboards/sales/frontend/dist/index.html"
  if [[ -f "$manifest" ]]; then
    local bundle
    bundle=$(grep -o 'assets/index-[^"]*\.js' "$manifest" | head -n 1 || true)
    if [[ -n "$bundle" ]]; then
      echo "$bundle"
      return 0
    fi
  fi

  return 1
}

function check() {
  local name=$1
  local url=$2
  shift 2
  local allowed_codes=("$@")
  if [[ ${#allowed_codes[@]} -eq 0 ]]; then
    allowed_codes=("200")
  fi

  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" "$url" || echo "000")

  for expected in "${allowed_codes[@]}"; do
    if [[ "$code" == "$expected" ]]; then
      printf "✅ %-20s %s (%s)\n" "$name" "$url" "$code"
      return 0
    fi
  done

  printf "❌ %-20s %s (got %s, expected %s)\n" "$name" "$url" "$code" "${allowed_codes[*]}"
  return 1
}

function warmup() {
  local url=$1
  curl -s -o /dev/null "$url" || true
}

echo "Running smoke tests..."

# Wake sleeping dynos so health checks don't 503 on first hit
warmup "$SALES_URL/"
warmup "$ACTIVITY_URL/"
warmup "$RECRUITER_URL/"

check "Portal health"          "$PORTAL_URL/health" "200"
check "Portal marketing"       "$PORTAL_URL/marketing" "200" "302" "401"
check "Portal → Sales redirect" "$PORTAL_URL/sales" "302" "307" "401"
check "Sales health"           "$SALES_URL/health" "200"
check "Portal → Activity"      "$PORTAL_URL/activity-tracker" "302" "307" "401" "404"
check "Activity health"        "$ACTIVITY_URL/health" "200"
check "Recruiter landing"      "$RECRUITER_URL/" "200" "302" "307" "401" "404"
s_bundle=$(resolve_sales_bundle || true)
if [[ -n "$s_bundle" ]]; then
  check "Sales bundle"         "$SALES_URL/$s_bundle" "200"
else
  echo "⚠️ Sales bundle path unavailable (set SALES_BUNDLE_PATH env var to skip auto-detect)."
fi

echo "Smoke tests completed."

