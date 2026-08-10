FROM debian:bookworm AS build

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates && \
    update-ca-certificates

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      build-essential \
      autoconf \
      automake \
      libtool \
      pkg-config \
      git \
      libjansson-dev \
      libssl-dev \
      libcurl4-openssl-dev \
      libzmq3-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /src

RUN git clone --depth 1 https://github.com/ctubio/ckpool.git .

RUN ./autogen.sh && \
    ./configure && \
    make -j"$(nproc)"

FROM debian:bookworm-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates \
      libjansson4 \
      libssl3 \
      libcurl4 \
      libzmq5 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=build /src/src/ckpool /usr/local/bin/ckpool
COPY entrypoint.sh /usr/local/bin/curtis-ckpool-entrypoint

RUN chmod 0755 /usr/local/bin/curtis-ckpool-entrypoint

EXPOSE 3333

ENTRYPOINT ["/usr/local/bin/curtis-ckpool-entrypoint"]
