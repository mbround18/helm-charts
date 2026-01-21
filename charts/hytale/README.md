# Hytale

Helm chart to deploy the Hytale dedicated server using the mbround18/hytale image.

## Ports

- Server: UDP 5520 (configurable via `endpoint.serverPort` and `SERVER_PORT`)
- Remote console: TCP 7000 (configurable via `endpoint.consolePort` and `REMOTE_CONSOLE_PORT`)

## Persistence

Mounts `/data` for downloads, logs, credentials, and server files.

## Notes

On first boot, the server prints a device login URL/code in the logs. Complete the login to authenticate.

## Configuration & Options

For the complete set of environment variables, CLI flags, networking, and hosting recipes, see the upstream [server-hosting guide](https://github.com/mbround18/hytale/blob/main/docs/guides/server-hosting.md).
