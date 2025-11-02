# Vein Helm Chart

A Helm chart for deploying a Vein dedicated game server on Kubernetes. Vein is a survival horror multiplayer game inspired by Project Zomboid and DayZ, featuring realistic survival mechanics, base building, and persistent worlds.

## Features

- **Host Network Mode**: Direct binding to node ports (7777, 27015, 27016) for optimal connectivity
- **Separate PVCs**: Game data and save files stored on independent volumes for easier backups
- **Secure by Default**: Requires Kubernetes secrets for password management
- **Non-Root Security**: Runs as UID/GID 1000:1000 with seccomp RuntimeDefault
- **Symlinked Saves**: Save files automatically symlinked from separate PVC to game directory
- **Resource Management**: Pre-configured for Vein's high memory requirements (9-12Gi typical)

## Prerequisites

- Kubernetes 1.19+
- Helm 3.2.0+
- PersistentVolume provisioner support (default uses Longhorn)
- A Kubernetes secret with server passwords

## Quick Start

### 1. Create Namespace

```bash
kubectl create namespace vein-server
```

### 2. Create Secret

```bash
kubectl create secret generic vein-passwords \
  --from-literal=SERVER_PASSWORD=your-server-password \
  --from-literal=ADMIN_PASSWORD=your-admin-password \
  --namespace vein-server
```

### 3. Install Chart

```bash
# Add repository
helm repo add mbround18 https://mbround18.github.io/helm-charts/
helm repo update

# Install with custom values
helm install vein mbround18/vein \
  --namespace vein-server \
  --set existingSecret.name=vein-passwords \
  --set env.SERVER_NAME="My Vein Server" \
  --set env.MAX_PLAYERS="16" \
  --set env.STEAM_GSLT="your-gslt-token"
```

### 4. Get Connection Info

```bash
# Get node IP
kubectl get nodes -o wide

# Your server will be accessible at:
# Game Port: <NODE_IP>:7777 (UDP)
# Query Port: <NODE_IP>:27015 (UDP)
```

## Uninstalling the Chart

```bash
helm uninstall vein --namespace vein-server
```

## Configuration

### Key Values

| Parameter                            | Description                            | Default                 |
| ------------------------------------ | -------------------------------------- | ----------------------- |
| **Image**                            |                                        |                         |
| `image.repository`                   | Vein server image                      | `mbround18/vein-docker` |
| `image.tag`                          | Image tag                              | `v0.0.1`                |
| `image.pullPolicy`                   | Image pull policy                      | `IfNotPresent`          |
| **Server Settings**                  |                                        |                         |
| `env.SERVER_NAME`                    | Server name visible in browser         | `Vein Server`           |
| `env.MAX_PLAYERS`                    | Maximum concurrent players             | `16`                    |
| `env.SERVER_PORT`                    | Game server port (UDP)                 | `7777`                  |
| `env.QUERY_PORT`                     | Query port (UDP)                       | `27015`                 |
| `env.SERVER_PUBLIC`                  | List server publicly                   | `true`                  |
| `env.STEAM_GSLT`                     | Steam Game Server Login Token          | `""`                    |
| `env.ADMIN_STEAM_IDS`                | Admin Steam IDs (comma-separated)      | `""`                    |
| `env.SUPERADMIN_STEAM_IDS`           | Superadmin Steam IDs (comma-separated) | `""`                    |
| **Authentication**                   |                                        |                         |
| `existingSecret.name`                | Secret name for passwords (required)   | `""`                    |
| `existingSecret.keys.serverPassword` | Secret key for server password         | `SERVER_PASSWORD`       |
| `existingSecret.keys.adminPassword`  | Secret key for admin password          | `ADMIN_PASSWORD`        |
| **Networking**                       |                                        |                         |
| `service.type`                       | Service type                           | `NodePort`              |
| `service.bindToNode`                 | Use host network mode                  | `true`                  |
| **Storage**                          |                                        |                         |
| `storage.game.size`                  | Game data PVC size                     | `20Gi`                  |
| `storage.game.storageClassName`      | Storage class for game data            | `longhorn`              |
| `storage.saves.size`                 | Saves data PVC size                    | `5Gi`                   |
| `storage.saves.enabled`              | Enable separate saves PVC              | `true`                  |
| **Resources**                        |                                        |                         |
| `resources.requests.cpu`             | CPU request                            | `2000m`                 |
| `resources.requests.memory`          | Memory request                         | `4Gi`                   |
| `resources.limits.cpu`               | CPU limit                              | `4000m`                 |
| `resources.limits.memory`            | Memory limit                           | `12Gi`                  |

### Using Secret (Required)

Create a secret with passwords before installing:

```bash
kubectl create secret generic vein-passwords \
  --from-literal=SERVER_PASSWORD=mysecretpass \
  --from-literal=ADMIN_PASSWORD=myadminpass \
  --namespace vein-server
```

Then configure values:

```yaml
existingSecret:
  name: vein-passwords
  keys:
    serverPassword: SERVER_PASSWORD
    adminPassword: ADMIN_PASSWORD
```

**Important**: Passwords are required via secret. If `existingSecret.name` is empty, the server will start without password protection.

### Storage Configuration

The chart uses a **dual-PVC architecture** with symlinked saves for optimal backup workflows:

#### Architecture

```text
┌─────────────────────────────────────────┐
│ game-data PVC (20Gi)                    │
│ /home/steam/vein/                       │
│ ├── Vein/                               │
│ │   ├── Binaries/                       │
│ │   ├── Content/                        │
│ │   └── Saved/                          │
│ │       └── SaveGames/ ─────────┐       │
│ └── [game files...]             │       │
└─────────────────────────────────┼───────┘
                                  │ symlink
┌─────────────────────────────────┼───────┐
│ saves-data PVC (5Gi)            │       │
│ /home/steam/saves/ <────────────┘       │
│ ├── World1/                             │
│ ├── World2/                             │
│ └── [save files...]                     │
└─────────────────────────────────────────┘
```

#### Benefits

- **Independent Backups**: Snapshot saves (5Gi) separately from game data (20Gi)
- **Faster Recovery**: Restore just saves without re-downloading 14GB game
- **Easy Migration**: Move saves between servers/clusters independently
- **Cost Efficient**: Different storage classes for hot (saves) vs cold (game) data

#### Single Volume Mode

To use a single PVC for both game and saves:

```yaml
storage:
  game:
    enabled: true
    size: 25Gi
  saves:
    enabled: false # Disables separate saves PVC
```

### Networking Configuration

#### Host Network Mode (Default, Recommended)

Uses `hostNetwork: true` to bind directly to node ports without NAT overhead:

```yaml
service:
  bindToNode: true # Default
```

**Pros:**

- Direct port mapping (7777, 27015, 27016)
- No NAT/firewall complexity
- Best performance for game traffic
- Players connect via `<NODE_IP>:7777`

**Cons:**

- One server per node (port conflict)
- Requires node firewall rules

#### NodePort Mode

Standard Kubernetes NodePort service (requires `bindToNode: false`):

```yaml
service:
  bindToNode: false
  ports:
    server:
      nodePort: 31808 # Or null for auto-assign
    query:
      nodePort: 31809
    aux:
      nodePort: null # Auto becomes 31810 if query is 31809
```

**Use Cases:**

- Multiple servers per node
- Using load balancers
- Cloud provider integrations

**Note**: Players must connect via the NodePort (e.g., `<NODE_IP>:31808` instead of `7777`)

### Steam Configuration

#### Game Server Login Token (GSLT)

Required for public servers. Obtain from [Steam Game Server Account Management](https://steamcommunity.com/dev/managegameservers):

```yaml
env:
  STEAM_GSLT: "YOUR_TOKEN_HERE"
  SERVER_PUBLIC: "true"
```

#### Admin Configuration

Set admin permissions using Steam IDs:

```yaml
env:
  # Regular admins - can kick, ban, manage server
  ADMIN_STEAM_IDS: "76561198012345678,76561198087654321"

  # Superadmins - full control including admin management
  SUPERADMIN_STEAM_IDS: "76561198012345678"
```

To find your Steam ID: Visit [steamid.io](https://steamid.io/) and enter your profile URL.

## Advanced Configuration

### Environment Variables

All environment variables from the [vein-docker container](https://github.com/mbround18/vein-docker) are supported:

```yaml
env:
  # Steam Configuration
  STEAM_USERNAME: "anonymous"
  STEAM_PASSWORD: ""
  APP_ID: "2131400"

  # Server Configuration
  SERVER_NAME: "My Vein Server"
  MAX_PLAYERS: "16"
  SERVER_PORT: "7777"
  QUERY_PORT: "27015"
  SERVER_PUBLIC: "true"
  BIND_ADDR: "0.0.0.0"

  # Updates
  UPDATE_ON_START: "true"
  VALIDATE: "false"

  # Game Settings
  INI_ENABLE: "true"
```

### Security Context

The chart runs with hardened security by default:

```yaml
podSecurityContext:
  runAsNonRoot: true
  runAsUser: 1000
  runAsGroup: 1000
  fsGroup: 1000
  seccompProfile:
    type: RuntimeDefault

securityContext:
  allowPrivilegeEscalation: false
  capabilities:
    drop: [ALL]
  readOnlyRootFilesystem: false # Game requires writable filesystem
```

### Node Affinity

Pin the server to specific nodes:

```yaml
nodeSelector:
  vein-server: "true"

affinity:
  nodeAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      nodeSelectorTerms:
        - matchExpressions:
            - key: kubernetes.io/hostname
              operator: In
              values:
                - node-01

tolerations:
  - key: "dedicated"
    operator: "Equal"
    value: "gameserver"
    effect: "NoSchedule"
```

## Performance Tuning

### Resource Requirements

Default resource allocation:

```yaml
resources:
  requests:
    cpu: 2000m
    memory: 4Gi
  limits:
    cpu: 4000m
    memory: 12Gi
```

**Important**: Vein servers are memory-intensive and typically consume **9-12Gi RAM idle**, increasing with player count.

#### Recommended Sizing

| Players | CPU      | Memory  | Notes                   |
| ------- | -------- | ------- | ----------------------- |
| 1-8     | 2 cores  | 8-12Gi  | Small server            |
| 8-16    | 4 cores  | 12-16Gi | Medium server (default) |
| 16+     | 6+ cores | 16-24Gi | Large server            |

### Initial Download

The first pod startup downloads ~14GB of game files. This can take 10-30 minutes depending on:

- Network speed to Steam servers
- Storage I/O performance
- `UPDATE_ON_START` and `VALIDATE` settings

Monitor progress:

```bash
kubectl logs -f vein-0 -n vein-server
```

Look for: `Update state (0x61) downloading, progress: XX.XX%`

### Persistent Performance

After initial setup:

- **Startup Time**: 30-60 seconds
- **Save Interval**: Autosaves every 60 seconds (configurable via Game.ini)
- **Network Usage**: ~100KB/s per player

## Troubleshooting

### Server Not Visible in Browser

1. **Check GSLT**: Ensure `STEAM_GSLT` is set and valid
2. **Verify Ports**: Confirm UDP ports 7777 and 27015 are accessible
3. **Firewall**: Check node firewall allows UDP traffic
4. **Public Setting**: Ensure `SERVER_PUBLIC: "true"`

```bash
# Test connectivity from outside cluster
nc -u -v <NODE_IP> 7777
nc -u -v <NODE_IP> 27015
```

### High Memory Usage

Normal - Vein uses 9-12Gi idle. If pod is OOMKilled:

```bash
# Increase memory limits
helm upgrade vein mbround18/vein \
  --namespace vein-server \
  --reuse-values \
  --set resources.limits.memory=16Gi
```

### Save Files Not Persisting

Check symlink creation in init container:

```bash
kubectl logs vein-0 -n vein-server -c create-symlink
```

Verify PVC mounts:

```bash
kubectl exec vein-0 -n vein-server -- ls -la /home/steam/vein/Vein/Saved/
kubectl exec vein-0 -n vein-server -- ls -la /home/steam/saves/
```

### Connection Refused / Timeout

**Host Network Mode** (default):

- Ensure only one vein pod per node (ports conflict)
- Check node firewall: `sudo ufw allow 7777/udp && sudo ufw allow 27015/udp`
- Verify pod is on expected node: `kubectl get pods -o wide -n vein-server`

**NodePort Mode**:

- Connect using NodePort, not 7777: `kubectl get svc vein -n vein-server`
- Use the high port (30000-32767) shown in `PORT(S)` column

## Backup and Restore

### Backup Saves

```bash
# Using Velero
velero backup create vein-saves \
  --include-namespaces vein-server \
  --selector app.kubernetes.io/name=vein

# Manual backup
kubectl exec vein-0 -n vein-server -- tar czf - /home/steam/saves \
  | gzip > vein-saves-$(date +%Y%m%d).tar.gz
```

### Restore Saves

```bash
# Stop server
kubectl scale statefulset vein -n vein-server --replicas=0

# Restore from backup
kubectl exec vein-0 -n vein-server -- tar xzf - -C / < vein-saves-20251102.tar.gz

# Start server
kubectl scale statefulset vein -n vein-server --replicas=1
```

## Monitoring

### View Logs

```bash
# Follow server logs
kubectl logs -f vein-0 -n vein-server

# View last 100 lines
kubectl logs vein-0 -n vein-server --tail=100

# Include timestamps
kubectl logs vein-0 -n vein-server --timestamps
```

### Server Console

Access the running container:

```bash
kubectl exec -it vein-0 -n vein-server -- bash
```

### Resource Usage

```bash
kubectl top pod vein-0 -n vein-server
```
