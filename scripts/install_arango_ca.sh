#!/usr/bin/env bash
set -euo pipefail

# Install Arango Cloud CA chain (leaf + Let's Encrypt R13 + ISRG Root X1) into a local bundle.
# The leaf cert can be provided via:
#   - ARANGO_LEAF_CERT_PATH (path to PEM), or
#   - ARANGO_LEAF_CERT_B64 (base64 PEM) in .env.local (sourced if present)
# Private keys are NOT needed for TLS verification and should not be stored here.
#
# Usage:
#   ./scripts/install_arango_ca.sh [--system]
#     --system   install to /usr/local/share/ca-certificates/arango-ca-bundle.crt and update trust (requires sudo)
# Resulting bundle path (local): ./arango-ca-bundle.crt

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE="${ROOT}/arango-ca-bundle.crt"
SYSTEM_INSTALL="${1:-}"

# Load optional env values
if [[ -f "${ROOT}/.env.local" ]]; then
  # shellcheck disable=SC1091
  source "${ROOT}/.env.local"
fi

LEAF_PATH="${ARANGO_LEAF_CERT_PATH:-}"
LEAF_B64="${ARANGO_LEAF_CERT_B64:-}"

tmp_leaf=""
if [[ -z "${LEAF_PATH}" && -n "${LEAF_B64}" ]]; then
  tmp_leaf="$(mktemp)"
  echo "${LEAF_B64}" | base64 -d > "${tmp_leaf}"
  LEAF_PATH="${tmp_leaf}"
fi

if [[ -z "${LEAF_PATH}" || ! -f "${LEAF_PATH}" ]]; then
  echo "Leaf certificate not found. Set ARANGO_LEAF_CERT_PATH or ARANGO_LEAF_CERT_B64 in .env.local."
  exit 1
fi

echo "Building CA bundle at ${BUNDLE}..."
cat "${LEAF_PATH}" > "${BUNDLE}"
cat >> "${BUNDLE}" <<'EOF'
# Let's Encrypt R13 intermediate
-----BEGIN CERTIFICATE-----
MIIFBTCCAu2gAwIBAgIQWgDyEtjUtIDzkkFX6imDBTANBgkqhkiG9w0BAQsFADBP
MQswCQYDVQQGEwJVUzEpMCcGA1UEChMgSW50ZXJuZXQgU2VjdXJpdHkgUmVzZWFy
Y2ggR3JvdXAxFTATBgNVBAMTDElTUkcgUm9vdCBYMTAeFw0yNDAzMTMwMDAwMDBa
Fw0yNzAzMTIyMzU5NTlaMDMxCzAJBgNVBAYTAlVTMRYwFAYDVQQKEw1MZXQncyBF
bmNyeXB0MQwwCgYDVQQDEwNSMTMwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEK
AoIBAQClZ3CN0FaBZBUXYc25BtStGZCMJlA3mBZjklTb2cyEBZPs0+wIG6BgUUNI
fSvHSJaetC3ancgnO1ehn6vw1g7UDjDKb5ux0daknTI+WE41b0VYaHEX/D7YXYKg
L7JRbLAaXbhZzjVlyIuhrxA3/+OcXcJJFzT/jCuLjfC8cSyTDB0FxLrHzarJXnzR
yQH3nAP2/Apd9Np75tt2QnDr9E0i2gB3b9bJXxf92nUupVcM9upctuBzpWjPoXTi
dYJ+EJ/B9aLrAek4sQpEzNPCifVJNYIKNLMc6YjCR06CDgo28EdPivEpBHXazeGa
XP9enZiVuppD0EqiFwUBBDDTMrOPAgMBAAGjgfgwgfUwDgYDVR0PAQH/BAQDAgGG
MB0GA1UdJQQWMBQGCCsGAQUFBwMCBggrBgEFBQcDATASBgNVHRMBAf8ECDAGAQH/
AgEAMB0GA1UdDgQWBBTnq58PLDOgU9NeT3jIsoQOO9aSMzAfBgNVHSMEGDAWgBR5
tFnme7bl5AFzgAiIyBpY9umbbjAyBggrBgEFBQcBAQQmMCQwIgYIKwYBBQUHMAKG
Fmh0dHA6Ly94MS5pLmxlbmNyLm9yZy8wEwYDVR0gBAwwCjAIBgZngQwBAgEwJwYD
VR0fBCAwHjAcoBqgGIYWaHR0cDovL3gxLmMubGVuY3Iub3JnLzANBgkqhkiG9w0B
AQsFAAOCAgEAUTdYUqEimzW7TbrOypLqCfL7VOwYf/Q79OH5cHLCZeggfQhDconl
k7Kgh8b0vi+/XuWu7CN8n/UPeg1vo3G+taXirrytthQinAHGwc/UdbOygJa9zuBc
VyqoH3CXTXDInT+8a+c3aEVMJ2St+pSn4ed+WkDp8ijsijvEyFwE47hulW0Ltzjg
9fOV5Pmrg/zxWbRuL+k0DBDHEJennCsAen7c35Pmx7jpmJ/HtgRhcnz0yjSBvyIw
6L1QIupkCv2SBODT/xDD3gfQQyKv6roV4G2EhfEyAsWpmojxjCUCGiyg97FvDtm/
NK2LSc9lybKxB73I2+P2G3CaWpvvpAiHCVu30jW8GCxKdfhsXtnIy2imskQqVZ2m
0Pmxobb28Tucr7xBK7CtwvPrb79os7u2XP3O5f9b/H66GNyRrglRXlrYjI1oGYL/
f4I1n/Sgusda6WvA6C190kxjU15Y12mHU4+BxyR9cx2hhGS9fAjMZKJss28qxvz6
Axu4CaDmRNZpK/pQrXF17yXCXkmEWgvSOEZy6Z9pcbLIVEGckV/iVeq0AOo2pkg9
p4QRIy0tK2diRENLSF2KysFwbY6B26BFeFs3v1sYVRhFW9nLkOrQVporCS0KyZmf
wVD89qSTlnctLcZnIavjKsKUu1nA1iU0yYMdYepKR7lWbnwhdx3ewok=
-----END CERTIFICATE-----
# ISRG Root X1
-----BEGIN CERTIFICATE-----
MIIFazCCA1OgAwIBAgIRAIIQz7DSQONZRGPgu2OCiwAwDQYJKoZIhvcNAQELBQAw
TzELMAkGA1UEBhMCVVMxKTAnBgNVBAoTIEludGVybmV0IFNlY3VyaXR5IFJlc2Vh
cmNoIEdyb3VwMRUwEwYDVQQDEwxJU1JHIFJvb3QgWDEwHhcNMTYwNjA5MDAwMDAw
WhcNMzEwNjA4MTUwMDAwWjBP
MQswCQYDVQQGEwJVUzEpMCcGA1UEChMgSW50ZXJuZXQgU2VjdXJpdHkgUmVzZWFy
Y2ggR3JvdXAxFTATBgNVBAMTDElTUkcgUm9vdCBYMTA0
DQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAN0pAxdX3j
AhmTZuZVYEWr02yWMNh+NopnfjIku1Kpqo4Zx4TZkqEd
ZB3/y5cFBN/4Q9buFdFfkWE1QDMktcyOk/PPswIS8zH
qM1OKL4fAQj0UA0hCbbTHs0OFgRz9Yb
lmq7/9kBnn8Ic7Cjtqo0GXxgnIUB4k
z7L0jGlBA13GDMSZ
luMrD9FAUPWj
 9U81zZbTuN928+sM
cU
cm/DlujdAlrV
q
 ym0X jfOOLmN1gx/PcO
G1XS
Q/i6cOLl3Myq9  nfjD0uaVzz/Ibok
+x0Oi86smpr
qDYXgZ6
  cqQ==
-----END CERTIFICATE-----
EOF

echo "Bundle written. Local path: ${BUNDLE}"
echo "Set ARANGO_VERIFY=${BUNDLE} to use it."

if [[ "${SYSTEM_INSTALL}" == "--system" ]]; then
  echo "Installing bundle into system trust (requires sudo)..."
  sudo cp "${BUNDLE}" /usr/local/share/ca-certificates/arango-ca-bundle.crt
  sudo update-ca-certificates
  echo "System trust updated. Set ARANGO_VERIFY=/usr/local/share/ca-certificates/arango-ca-bundle.crt"
fi

if [[ -n "${tmp_leaf}" ]]; then
  rm -f "${tmp_leaf}"
fi
