#!/bin/sh
set -eu
case "${OTEL_SDK_DISABLED:-false}" in
  [Tt][Rr][Uu][Ee]) exec python app.py ;;
  *) exec opentelemetry-instrument python app.py ;;
esac
