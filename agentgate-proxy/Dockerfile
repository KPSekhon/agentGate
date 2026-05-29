FROM golang:1.22-alpine AS builder

WORKDIR /build
COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o agentgate-proxy ./cmd/proxy

FROM alpine:3.20
RUN apk add --no-cache ca-certificates
COPY --from=builder /build/agentgate-proxy /usr/local/bin/agentgate-proxy

EXPOSE 8443
USER nobody:nobody
ENTRYPOINT ["agentgate-proxy"]
