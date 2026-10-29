# syntax=docker/dockerfile:1.7

# Upstream publishes no image or binary of the standalone MCP server, so this
# builds it from the pinned commit of the mattermost-plugin-agents tag.
ARG MM_AGENTS_COMMIT=4722e85f1d76bd14584a8d728cc39af519da4a83

FROM --platform=$BUILDPLATFORM golang:1.26.2-trixie@sha256:4a7137ea573f79c86ae451ff05817ed762ef5597fcf732259e97abeb3108d873 AS build
ARG MM_AGENTS_COMMIT
ARG TARGETOS
ARG TARGETARCH
ADD https://github.com/mattermost/mattermost-plugin-agents.git#${MM_AGENTS_COMMIT} /src
WORKDIR /src
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=$TARGETOS GOARCH=$TARGETARCH \
    go build -trimpath -ldflags="-s -w" -o /out/mattermost-mcp-server ./mcpserver/cmd/main.go

FROM gcr.io/distroless/static-debian13:nonroot@sha256:18f4cc26c9ffa7f20a359298be7deadac5c607c8e03a02b8119f1a5fc2f82c99
COPY --from=build /out/mattermost-mcp-server /usr/local/bin/mattermost-mcp-server
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/mattermost-mcp-server"]
