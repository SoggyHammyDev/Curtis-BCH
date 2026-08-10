FROM debian:bookworm-slim
ARG BCHN_VERSION=29.1.0
ARG BCHN_ARCH=x86_64-linux-gnu
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl xz-utils \
 && rm -rf /var/lib/apt/lists/* \
 && curl -fsSL "https://bitcoincashnode.org/downloads/bitcoin-cash-node-${BCHN_VERSION}/${BCHN_ARCH}/bitcoin-cash-node-${BCHN_VERSION}-${BCHN_ARCH}.tar.gz" -o /tmp/bchn.tgz \
 && tar -xzf /tmp/bchn.tgz -C /tmp \
 && install -m 0755 /tmp/bitcoin-cash-node-${BCHN_VERSION}/bin/bitcoind /usr/local/bin/bitcoind \
 && install -m 0755 /tmp/bitcoin-cash-node-${BCHN_VERSION}/bin/bitcoin-cli /usr/local/bin/bitcoin-cli \
 && rm -rf /tmp/*
COPY entrypoint.sh /usr/local/bin/curtis-bchn-entrypoint
RUN chmod 0755 /usr/local/bin/curtis-bchn-entrypoint
EXPOSE 28332 28333 28334
ENTRYPOINT ["/usr/local/bin/curtis-bchn-entrypoint"]
