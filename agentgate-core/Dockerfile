FROM rust:1.78-slim AS builder

RUN apt-get update && apt-get install -y protobuf-compiler && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY Cargo.toml Cargo.lock ./
COPY proto ./proto
COPY build.rs ./

RUN mkdir src && echo "pub fn dummy() {}" > src/lib.rs && cargo build --release 2>/dev/null || true

COPY src ./src
RUN cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=builder /build/target/release/agentgate /usr/local/bin/agentgate

EXPOSE 50051
USER nobody:nobody
ENTRYPOINT ["agentgate"]
