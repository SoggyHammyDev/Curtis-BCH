FROM debian:bookworm-slim

ARG BCHN_VERSION=29.1.0
ARG BCHN_ARCH=x86_64-linux-gnu

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fL \
      "https://github.com/bitcoin-cash-node/bitcoin-cash-node/releases/download/v${BCHN_VERSION}/bitcoin-cash-node-${BCHN_VERSION}-${BCHN_ARCH}.tar.gz" \
      -o /tmp/bchn.tar.gz \
    && tar -xzf /tmp/bchn.tar.gz -C /tmp \
    && install -m 0755 "/tmp/bitcoin-cash-node-${BCHN_VERSION}/bin/bitcoind" /usr/local/bin/bitcoind \
    && install -m 0755 "/tmp/bitcoin-cash-node-${BCHN_VERSION}/bin/bitcoin-cli" /usr/local/bin/bitcoin-cli \
    && rm -rf /tmp/*

COPY entrypoint.sh /usr/local/bin/curtis-bchn-entrypoint
RUN chmod 0755 /usr/local/bin/curtis-bchn-entrypoint

EXPOSE 28332 28333 28334
ENTRYPOINT ["/usr/local/bin/curtis-bchn-entrypoint"]
