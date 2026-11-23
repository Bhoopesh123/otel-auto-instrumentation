FROM grafana/grafana:12.1.1

ARG TARGETARCH
ARG INFINITY_VERSION=3.7.3

RUN set -eu; \
    archive=/tmp/infinity.zip; \
    url="https://github.com/grafana/grafana-infinity-datasource/releases/download/v${INFINITY_VERSION}/yesoreyeram-infinity-datasource-${INFINITY_VERSION}.linux_${TARGETARCH}.zip"; \
    for attempt in 1 2 3 4 5; do \
      wget -q -c -O "$archive" "$url" && break; \
    done; \
    unzip -t "$archive" >/dev/null; \
    mkdir -p "$GF_PATHS_PLUGINS"; \
    unzip -q "$archive" -d "$GF_PATHS_PLUGINS"; \
    rm "$archive"
