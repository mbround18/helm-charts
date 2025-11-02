# game-tools

A Helm **library chart** providing reusable templates and patterns for game server deployments on Kubernetes.

## Overview

Game servers have unique requirements compared to typical web applications: UDP traffic, direct port binding, persistent state, and often require host network mode for optimal connectivity. This library chart provides battle-tested templates that handle these complexities.

## Features

### NodePort Service Helper

Generates NodePort services with intelligent port negotiation:

- **Auto-assignment**: Kubernetes assigns from available pool when `nodePort: null`
- **Fixed ports**: Specify exact NodePort values for predictable connections
- **Sequential ports**: Automatically assigns adjacent ports when needed (e.g., query+1 for aux)
- **Multi-protocol**: Full UDP/TCP support with per-port configuration

### Reusable Patterns

- Service generation with proper labels and selectors
- Game server-optimized defaults
- Consistent template structure across game charts

## Usage

### 1. Add as Dependency

In your game server chart's `Chart.yaml`:

```yaml
apiVersion: v2
name: my-game-server
description: My awesome game server
type: application
version: 1.0.0

dependencies:
  - name: game-tools
    version: 0.1.0
    repository: file://../game-tools
```

### 2. Update Dependencies

```bash
helm dependency update charts/my-game-server
```

### 3. Use Templates

In your chart's `templates/service.yaml`:

```yaml
{{- $ports := list -}}
{{- range $name, $config := .Values.service.ports }}
{{- $ports = append $ports (dict "name" $name "port" $config.port "targetPort" $config.targetPort "protocol" $config.protocol "nodePort" $config.nodePort) }}
{{- end }}
{{- include "game-tools.service.nodeport" (dict "serviceName" (include "my-game.fullname" .) "ports" $ports "selectorLabels" (include "my-game.selectorLabels" .) "labels" (include "my-game.labels" .) "context" .) }}
```

## Templates

### game-tools.service.nodeport

Generates a NodePort Service for game servers.

#### Parameters

| Parameter        | Type   | Description                               |
| ---------------- | ------ | ----------------------------------------- |
| `serviceName`    | string | Name of the Service resource              |
| `ports`          | array  | List of port configurations (see below)   |
| `selectorLabels` | string | Pod selector labels as YAML string        |
| `labels`         | string | Service labels as YAML string             |
| `context`        | object | Root context (`.`) for template rendering |

#### Port Configuration

Each port in the `ports` array should have:

```yaml
- name: server # Port name (alphanumeric + hyphens)
  port: 7777 # Service port (what clients connect to)
  targetPort: 7777 # Container port (where pod is listening)
  protocol: UDP # Protocol: TCP or UDP
  nodePort: 30777 # NodePort (30000-32767), null for auto-assign
```

#### Example

```yaml
{{- $ports := list }}
{{- $ports = append $ports (dict "name" "game" "port" 7777 "targetPort" 7777 "protocol" "UDP" "nodePort" 30777) }}
{{- $ports = append $ports (dict "name" "query" "port" 27015 "targetPort" 27015 "protocol" "UDP" "nodePort" 30778) }}
{{- include "game-tools.service.nodeport" (dict
  "serviceName" "my-server"
  "ports" $ports
  "selectorLabels" (include "my-game.selectorLabels" . | fromYaml | toYaml)
  "labels" (include "my-game.labels" . | fromYaml | toYaml)
  "context" .
) }}
```

Generated output:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: my-server
  labels:
    helm.sh/chart: my-game-1.0.0
    app.kubernetes.io/name: my-game
    app.kubernetes.io/instance: my-release
    app.kubernetes.io/managed-by: Helm
spec:
  type: NodePort
  ports:
    - name: game
      port: 7777
      targetPort: 7777
      protocol: UDP
      nodePort: 30777
    - name: query
      port: 27015
      targetPort: 27015
      protocol: UDP
      nodePort: 30778
  selector:
    app.kubernetes.io/name: my-game
    app.kubernetes.io/instance: my-release
```

## Auto Port Negotiation

When `nodePort` is `null`, Kubernetes automatically assigns from the available pool:

```yaml
ports:
  - name: server
    port: 7777
    targetPort: 7777
    protocol: UDP
    nodePort: null # K8s assigns, e.g., 31234
```

**Benefits:**

- No port conflicts in multi-chart deployments
- Simplified configuration
- Kubernetes handles availability checking

**Trade-offs:**

- Port changes on service recreation
- Must query service to discover assigned port
- Players need to know the assigned NodePort

## Best Practices

### Use Host Network for Production

For best performance, most game servers should use `hostNetwork: true` instead of NodePort:

```yaml
spec:
  hostNetwork: true
  dnsPolicy: ClusterFirstWithHostNet
```

This bypasses NodePort overhead and allows direct port binding.

### NodePort for Development

Use NodePort mode for:

- Multi-server testing on same node
- Cloud environments without direct node access
- Load balancer integrations

### Label Consistency

Always include standard Kubernetes labels:

```yaml
labels:
  helm.sh/chart: { { include "my-game.chart" . } }
  app.kubernetes.io/name: { { include "my-game.name" . } }
  app.kubernetes.io/instance: { { .Release.Name } }
  app.kubernetes.io/version: { { .Chart.AppVersion | quote } }
  app.kubernetes.io/managed-by: { { .Release.Service } }
```

## Examples

### Valheim Server

```yaml
{{- $ports := list }}
{{- $ports = append $ports (dict "name" "game" "port" 2456 "targetPort" 2456 "protocol" "UDP" "nodePort" nil) }}
{{- $ports = append $ports (dict "name" "query" "port" 2457 "targetPort" 2457 "protocol" "UDP" "nodePort" nil) }}
{{- include "game-tools.service.nodeport" (dict "serviceName" "valheim" "ports" $ports "selectorLabels" (include "valheim.selectorLabels" .) "labels" (include "valheim.labels" .) "context" .) }}
```

### Palworld Server

```yaml
{{- $ports := list }}
{{- $ports = append $ports (dict "name" "game" "port" 8211 "targetPort" 8211 "protocol" "UDP" "nodePort" 30211) }}
{{- $ports = append $ports (dict "name" "rcon" "port" 25575 "targetPort" 25575 "protocol" "TCP" "nodePort" 30212) }}
{{- include "game-tools.service.nodeport" (dict "serviceName" "palworld" "ports" $ports "selectorLabels" (include "palworld.selectorLabels" .) "labels" (include "palworld.labels" .) "context" .) }}
```

### Vein Server

See the [Vein chart](../vein/README.md) for a complete example using game-tools.

## Contributing

To add new templates to game-tools:

1. Create template in `templates/_<name>.tpl`
2. Use `{{- define "game-tools.<name>" -}}` pattern
3. Document parameters and usage
4. Add examples to this README
5. Test with multiple game server charts

## Chart Information

- **Type**: library
- **Version**: 0.1.0
- **Kubernetes**: 1.19+
- **Helm**: 3.0+

## Related Charts

- [vein](../vein/README.md) - Vein survival horror game server
- [valheim](../valheim/README.md) - Valheim dedicated server
- [palworld](../palworld/README.md) - Palworld dedicated server
- [enshrouded](../enshrouded/README.md) - Enshrouded dedicated server
