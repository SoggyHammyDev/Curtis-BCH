FROM debian:bookworm AS build

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      build-essential \
      yasm \
      autoconf \
      automake \
      libtool \
      libzmq3-dev && \
    update-ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /src

RUN curl -fL \
    https://github.com/ctubio/ckpool/archive/refs/heads/master.tar.gz \
    -o /tmp/ckpool.tar.gz && \
    tar -xzf /tmp/ckpool.tar.gz --strip-components=1 -C /src && \
    rm -f /tmp/ckpool.tar.gz

RUN ./autogen.sh && \
    CFLAGS="-O2 -fcommon" ./configure --without-ckdb && \
    make -j"$(nproc)"

FROM debian:bookworm-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates \
      libzmq5 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=build /src/src/ckpool /usr/local/bin/ckpool
COPY entrypoint.sh /usr/local/bin/curtis-ckpool-entrypoint

RUN chmod 0755 /usr/local/bin/curtis-ckpool-entrypoint

EXPOSE 3333

ENTRYPOINT ["/usr/local/bin/curtis-ckpool-entrypoint"]
