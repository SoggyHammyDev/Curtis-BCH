FROM debian:bookworm AS build

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates curl build-essential autoconf automake libtool pkg-config \
      libssl-dev libjansson-dev libzmq3-dev \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src

RUN curl -fL \
    https://github.com/skaisser/ckpool/archive/refs/tags/v1.0.0-stable.tar.gz \
    -o /tmp/ckpool.tar.gz \
    && tar -xzf /tmp/ckpool.tar.gz --strip-components=1 -C /src \
    && rm -f /tmp/ckpool.tar.gz

RUN ./autogen.sh && ./configure && make -j"$(nproc)"

FROM debian:bookworm-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates libssl3 libjansson4 libzmq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /src/src/ckpool /usr/local/bin/ckpool
COPY entrypoint.sh /usr/local/bin/curtis-ckpool-entrypoint
RUN chmod 0755 /usr/local/bin/curtis-ckpool-entrypoint

EXPOSE 3333
ENTRYPOINT ["/usr/local/bin/curtis-ckpool-entrypoint"]
