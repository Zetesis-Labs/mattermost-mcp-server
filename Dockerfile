# syntax=docker/dockerfile:1.7

# Upstream publishes no image or binary of the standalone MCP server, so this
# builds it from the pinned commit of the mattermost-plugin-agents tag and applies
# read-only.patch, which leaves only the tools that retrieve data.
ARG MM_AGENTS_COMMIT=b24519a0a3cb960cf3ee1c6f68f54b3594f62c1d

FROM --platform=$BUILDPLATFORM golang:1.27.3-trixie@sha256:2336eda24930976591abea806d9b7d99eeae38238f19755c5deec02facdc1594 AS build
ARG MM_AGENTS_COMMIT
ARG TARGETOS
ARG TARGETARCH
ADD https://github.com/mattermost/mattermost-plugin-agents.git#${MM_AGENTS_COMMIT} /src
WORKDIR /src
COPY read-only.patch /tmp/read-only.patch
RUN git apply /tmp/read-only.patch
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=$TARGETOS GOARCH=$TARGETARCH \
    go build -trimpath -ldflags="-s -w" -o /out/mattermost-mcp-server ./mcpserver/cmd/main.go

FROM gcr.io/distroless/static-debian13:nonroot@sha256:18f4cc26c9ffa7f20a359298be7deadac5c607c8e03a02b8119f1a5fc2f82c99
COPY --from=build /out/mattermost-mcp-server /usr/local/bin/mattermost-mcp-server
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/mattermost-mcp-server"]
