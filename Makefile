.PHONY: all build test clean rust-build go-build python-test rust-test go-test serve

all: build test

# ── Build ───────────────────────────────────────────────
build: rust-build go-build

rust-build:
	cd agentgate-core && cargo build --release

go-build:
	cd agentgate-proxy && go build -ldflags="-s -w" -o bin/agentgate-proxy ./cmd/proxy

# ── Test ────────────────────────────────────────────────
test: rust-test go-test python-test

rust-test:
	cd agentgate-core && cargo test

go-test:
	cd agentgate-proxy && go test ./... -v

python-test:
	cd backend && python -m pytest ../tests/ -v

# ── Run ─────────────────────────────────────────────────
serve-core:
	cd agentgate-core && cargo run -- serve --policy-dir ../policies

serve-proxy:
	cd agentgate-proxy && go run ./cmd/proxy

serve-backend:
	cd backend && uvicorn main:app --reload --port 8000

serve-dashboard:
	cd dashboard && npm run dev

# ── Lint ────────────────────────────────────────────────
lint: rust-lint go-lint

rust-lint:
	cd agentgate-core && cargo clippy -- -D warnings

go-lint:
	cd agentgate-proxy && go vet ./...

# ── Docker ──────────────────────────────────────────────
docker-core:
	docker build -t agentgate-core:latest -f agentgate-core/Dockerfile agentgate-core/

docker-proxy:
	docker build -t agentgate-proxy:latest -f agentgate-proxy/Dockerfile agentgate-proxy/

# ── Clean ───────────────────────────────────────────────
clean:
	cd agentgate-core && cargo clean
	cd agentgate-proxy && rm -rf bin/
