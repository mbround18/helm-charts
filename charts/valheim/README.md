# Valheim Helm Chart

A Helm chart for deploying a Valheim dedicated server on Kubernetes. This chart uses the [mbround18/valheim-docker](https://github.com/mbround18/valheim-docker) container image to run a fully-featured Valheim server with automatic updates, backups, and comprehensive configuration options.

## Features

- **Automatic Updates**: Configurable auto-update with player-aware pausing
- **Automatic Backups**: Scheduled backups with configurable retention policies
- **Persistent Storage**: Separate PVCs for game data, saves, and backups
- **Flexible Service Types**: Support for NodePort and LoadBalancer (MetalLB compatible)
- **Crossplay Support**: Optional crossplay enablement for PC and Console players
- **HTTP API**: Built-in HTTP server for server management and monitoring
- **Easy Configuration**: Environment-based configuration for all Valheim server settings

## Prerequisites

- Kubernetes 1.19+
- Helm 3.2.0+
- PersistentVolume provisioner support
- For LoadBalancer service type: MetalLB or cloud provider load balancer

## Quick Start

### Basic Installation

```bash
# Add repository
helm repo add mbround18 https://mbround18.github.io/helm-charts/
helm repo update

# Install with default values
helm install valheim mbround18/valheim
```

### With LoadBalancer (MetalLB)

```bash
helm install valheim mbround18/valheim \
  --set service.type=LoadBalancer \
  --set service.annotations."metallb\.io/loadBalancerIPs"=10.100.14.175
```

### With Custom Server Settings

```bash
helm install valheim mbround18/valheim \
  --set environment[0].name=NAME \
  --set environment[0].value="My Awesome Server" \
  --set environment[1].name=PASSWORD \
  --set environment[1].value="SuperSecret123" \
  --set environment[2].name=WORLD \
  --set environment[2].value="MyWorld"
```

## Configuration

### Core Values

| Parameter                     | Description                           | Default                      |
| ----------------------------- | ------------------------------------- | ---------------------------- |
| **Image**                     |                                       |                              |
| `image.registry`              | Container registry                    | `docker.io`                  |
| `image.repository`            | Valheim server image                  | `mbround18/valheim`          |
| `image.tag`                   | Image tag (overrides appVersion)      | `""` (uses Chart appVersion) |
| `image.pullPolicy`            | Image pull policy                     | `Always`                     |
| **Server Settings**           |                                       |                              |
| `environment[].name=NAME`     | Server name visible in browser        | `Valheim Docker`             |
| `environment[].name=PASSWORD` | Server password (required for public) | `Strong! Password @ Here`    |
| `environment[].name=WORLD`    | World name                            | `Dedicated`                  |
| `environment[].name=PUBLIC`   | List server publicly (0 or 1)         | `1`                          |
| `environment[].name=PORT`     | Main game port                        | `2456`                       |
| `GAMEPORT`                    | Base port for game (PORT uses this)   | `2456`                       |
| `HTTPPORT`                    | HTTP API port (YAML anchor)           | `8080`                       |
| `environment[].name=HTTP_PORT`| HTTP API port (environment variable)  | `8080`                       |
| `PUID`                        | Process user ID                       | `111`                        |
| `GUID`                        | Process group ID                      | `1000`                       |

### Update & Backup Configuration

| Parameter                                           | Description                               | Default           |
| --------------------------------------------------- | ----------------------------------------- | ----------------- |
| `environment[].name=AUTO_UPDATE`                    | Enable automatic updates (0 or 1)         | `1`               |
| `environment[].name=AUTO_UPDATE_SCHEDULE`           | Cron schedule for updates                 | `12 * * * *`      |
| `environment[].name=AUTO_UPDATE_PAUSE_WITH_PLAYERS` | Pause updates when players online         | `1`               |
| `environment[].name=UPDATE_ON_STARTUP`              | Update on server start (0 or 1)           | `1`               |
| `environment[].name=AUTO_BACKUP`                    | Enable automatic backups (0 or 1)         | `1`               |
| `environment[].name=AUTO_BACKUP_SCHEDULE`           | Cron schedule for backups                 | `*/15 * * * *`    |
| `environment[].name=AUTO_BACKUP_DAYS_TO_LIVE`       | Backup retention in days                  | `7`               |
| `environment[].name=AUTO_BACKUP_ON_SHUTDOWN`        | Backup on server shutdown (0 or 1)        | `1`               |
| `environment[].name=AUTO_BACKUP_ON_UPDATE`          | Backup before updates (0 or 1)            | `1`               |
| `environment[].name=AUTO_BACKUP_REMOVE_OLD`         | Remove old backups automatically (0 or 1) | `1`               |
| `environment[].name=ENABLE_CROSSPLAY`               | Enable crossplay (0 or 1)                 | `0`               |
| `environment[].name=TZ`                             | Timezone for logs and schedules           | `America/Chicago` |

### Service Configuration

| Parameter              | Description                             | Default         |
| ---------------------- | --------------------------------------- | --------------- |
| `service.type`         | Service type (NodePort or LoadBalancer) | `LoadBalancer`  |
| `service.nodePortGame` | Starting NodePort (if type=NodePort)    | `31232`         |
| `service.annotations`  | Service annotations (e.g., for MetalLB) | See values.yaml |

### Storage Configuration

| Parameter             | Description                | Default   |
| --------------------- | -------------------------- | --------- |
| `storageClassName`    | Storage class for all PVCs | `""`      |
| `deployment.pvc.name` | Game data PVC name         | `data`    |
| `deployment.pvc.size` | Game data PVC size         | `10Gi`    |
| `saves.pvc.name`      | Saves PVC name             | `saves`   |
| `saves.pvc.size`      | Saves PVC size             | `10Gi`    |
| `backup.pvc.name`     | Backups PVC name           | `backups` |
| `backup.pvc.size`     | Backups PVC size           | `10Gi`    |

### Resource Configuration

| Parameter                   | Description        | Default |
| --------------------------- | ------------------ | ------- |
| `resources.requests.cpu`    | CPU request        | `""`    |
| `resources.requests.memory` | Memory request     | `""`    |
| `resources.limits.cpu`      | CPU limit          | `""`    |
| `resources.limits.memory`   | Memory limit       | `""`    |
| `replicaCount`              | Number of replicas | `1`     |

## Storage Architecture

The chart creates **three separate PVCs** for better data organization and backup flexibility:

```text
┌─────────────────────────────────────────┐
│ data PVC (10Gi - default)               │
│ /home/steam/valheim/                    │
│ ├── valheim_server.x86_64               │
│ ├── server_exit.drp                     │
│ └── [game binaries...]                  │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ saves PVC (10Gi - default)              │
│ /home/steam/.config/unity3d/            │
│     IronGate/Valheim/                   │
│ ├── worlds_local/                       │
│ │   ├── Dedicated.db                    │
│ │   ├── Dedicated.fwl                   │
│ │   └── [world files...]                │
│ └── [character data...]                 │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ backups PVC (10Gi - default)            │
│ /home/steam/backups/                    │
│ ├── worlds-2025-01-13_120000.tar.gz    │
│ ├── worlds-2025-01-13_121500.tar.gz    │
│ └── [backup archives...]                │
└─────────────────────────────────────────┘
```

### Benefits

- **Targeted Backups**: Snapshot only saves (smaller, faster)
- **Independent Restore**: Restore saves without re-downloading game data
- **Flexible Storage Classes**: Use different storage tiers for each type
- **Clear Separation**: Game binaries, world data, and backups isolated

## Networking

### Service Types

#### LoadBalancer (Default)

Best for production deployments, especially with MetalLB:

```yaml
service:
  type: LoadBalancer
  annotations:
    metallb.io/loadBalancerIPs: 10.100.14.175
    # metallb.io/address-pool: mypool  # Optional: specific pool
```

**Ports exposed:**

- **2456/UDP**: Main game port
- **2457/UDP**: Query port
- **2458/UDP**: Additional game port
- **8080/TCP**: HTTP API (optional)

Players connect via: `<LOADBALANCER_IP>:2456`

#### NodePort

Alternative for environments without LoadBalancer support:

```yaml
service:
  type: NodePort
  nodePortGame: 31232 # Starting port (31232, 31233, 31234 will be used)
```

**Note**: Three consecutive NodePorts are required (31232, 31233, 31234 by default). Ensure range availability (30000-32767).

Players connect via: `<NODE_IP>:31232`

### MetalLB Configuration

For MetalLB users, configure IP assignment:

```yaml
service:
  type: LoadBalancer
  annotations:
    # Automatic IP from pool with autoassign: true
    metallb.io/loadBalancerIPs: 10.100.14.175

    # Or specify pool name if autoassign: false
    metallb.io/address-pool: valheim-pool
```

**Important**: The annotation namespace changed from `metallb.universe.tf/*` (older MetalLB versions) to `metallb.io/*` (newer versions). Use the appropriate namespace for your MetalLB version.

## Advanced Configuration

### Environment Variables

All environment variables are configured via the `environment` array. See [valheim-docker documentation](https://github.com/mbround18/valheim-docker) for complete reference.

**Example with multiple settings:**

```yaml
environment:
  - name: "NAME"
    value: "Epic Viking Server"
  - name: "PASSWORD"
    value: "Odin123!"
  - name: "WORLD"
    value: "Midgard"
  - name: "PUBLIC"
    value: "1"
  - name: "AUTO_UPDATE"
    value: "1"
  - name: "AUTO_UPDATE_SCHEDULE"
    value: "0 4 * * *" # 4 AM daily
  - name: "AUTO_BACKUP_SCHEDULE"
    value: "0 */6 * * *" # Every 6 hours
  - name: "AUTO_BACKUP_DAYS_TO_LIVE"
    value: "14"
  - name: "ENABLE_CROSSPLAY"
    value: "1"
  - name: "TZ"
    value: "Europe/London"
```

### Crossplay Configuration

Enable crossplay for PC and console players:

```yaml
environment:
  - name: "ENABLE_CROSSPLAY"
    value: "1"
```

**Important**: Crossplay was introduced in Valheim update 0.211.11. Ensure your `image.tag` is using a compatible version (3.1.0+).

### Resource Recommendations

Valheim servers have moderate resource requirements:

```yaml
resources:
  requests:
    cpu: 2000m
    memory: 2Gi
  limits:
    cpu: 4000m
    memory: 4Gi
```

| Players | CPU       | Memory | Notes         |
| ------- | --------- | ------ | ------------- |
| 1-5     | 1-2 cores | 2Gi    | Small server  |
| 5-10    | 2-3 cores | 3-4Gi  | Medium server |
| 10+     | 3-4 cores | 4-6Gi  | Large server  |

### Security Context

Configure pod and container security:

```yaml
podSecurityContext:
  fsGroup: 1000
  runAsUser: 1000
  runAsGroup: 1000

securityContext:
  allowPrivilegeEscalation: false
  capabilities:
    drop:
      - ALL
  readOnlyRootFilesystem: false # Valheim requires writable filesystem
```

### Node Affinity & Tolerations

Pin server to specific nodes:

```yaml
nodeSelector:
  valheim-server: "true"

affinity:
  nodeAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      nodeSelectorTerms:
        - matchExpressions:
            - key: kubernetes.io/hostname
              operator: In
              values:
                - worker-node-01

tolerations:
  - key: "dedicated"
    operator: "Equal"
    value: "gameserver"
    effect: "NoSchedule"
```

## Usage Examples

### Example 1: Basic Private Server

```yaml
# values.yaml
environment:
  - name: "NAME"
    value: "Private Server"
  - name: "PASSWORD"
    value: "FriendsOnly123"
  - name: "WORLD"
    value: "PrivateWorld"
  - name: "PUBLIC"
    value: "0" # Not listed publicly

service:
  type: LoadBalancer
  annotations:
    metallb.io/loadBalancerIPs: 192.168.1.100

resources:
  requests:
    cpu: 2000m
    memory: 2Gi
  limits:
    cpu: 4000m
    memory: 4Gi
```

### Example 2: Public Server with Crossplay

```yaml
environment:
  - name: "NAME"
    value: "Nordic Crossplay Adventures"
  - name: "PASSWORD"
    value: "" # Public server, no password
  - name: "WORLD"
    value: "CrossplayWorld"
  - name: "PUBLIC"
    value: "1"
  - name: "ENABLE_CROSSPLAY"
    value: "1"
  - name: "AUTO_UPDATE_SCHEDULE"
    value: "0 3 * * *" # 3 AM daily
  - name: "AUTO_BACKUP_SCHEDULE"
    value: "0 */4 * * *" # Every 4 hours

service:
  type: LoadBalancer

resources:
  requests:
    cpu: 3000m
    memory: 3Gi
  limits:
    cpu: 6000m
    memory: 6Gi
```

### Example 3: Development Server with Custom Storage

```yaml
environment:
  - name: "NAME"
    value: "Dev Server"
  - name: "WORLD"
    value: "TestWorld"
  - name: "PUBLIC"
    value: "0"
  - name: "AUTO_UPDATE"
    value: "0" # Disable auto-update
  - name: "AUTO_BACKUP"
    value: "0" # Disable auto-backup

service:
  type: NodePort
  nodePortGame: 31456

deployment:
  pvc:
    size: 5Gi

saves:
  pvc:
    size: 2Gi

backup:
  pvc:
    size: 2Gi

storageClassName: "fast-ssd"
```

## Backup and Restore

### Automatic Backups

The chart includes built-in automatic backup functionality:

```yaml
environment:
  - name: "AUTO_BACKUP"
    value: "1"
  - name: "AUTO_BACKUP_SCHEDULE"
    value: "*/15 * * * *" # Every 15 minutes
  - name: "AUTO_BACKUP_DAYS_TO_LIVE"
    value: "7" # Keep 7 days of backups
  - name: "AUTO_BACKUP_ON_SHUTDOWN"
    value: "1"
  - name: "AUTO_BACKUP_ON_UPDATE"
    value: "1"
  - name: "AUTO_BACKUP_REMOVE_OLD"
    value: "1"
```

Backups are stored in the dedicated backups PVC at `/home/steam/backups/`.

### Manual Backup

Create a manual backup:

```bash
kubectl exec -n <namespace> <pod-name> -- bash -c "cd /home/steam/backups && tar czf manual-backup-$(date +%Y%m%d-%H%M%S).tar.gz -C /home/steam/.config/unity3d/IronGate/Valheim worlds_local"
```

### Download Backups

```bash
# List backups
kubectl exec -n <namespace> <pod-name> -- ls -lh /home/steam/backups/

# Download a backup
kubectl cp <namespace>/<pod-name>:/home/steam/backups/worlds-2025-01-13_120000.tar.gz ./local-backup.tar.gz
```

### Restore from Backup

```bash
# Stop the server
kubectl scale deployment <release-name>-valheim --replicas=0 -n <namespace>

# Copy backup to pod (when scaled up)
kubectl scale deployment <release-name>-valheim --replicas=1 -n <namespace>
# Wait for pod to be ready
kubectl cp ./local-backup.tar.gz <namespace>/<pod-name>:/tmp/restore.tar.gz

# Restore the backup
kubectl exec -n <namespace> <pod-name> -- bash -c "cd /home/steam/.config/unity3d/IronGate/Valheim && tar xzf /tmp/restore.tar.gz"

# Restart the server
kubectl rollout restart deployment <release-name>-valheim -n <namespace>
```

## Monitoring

### View Server Logs

```bash
# Follow live logs
kubectl logs -f -n <namespace> <pod-name>

# View last 100 lines
kubectl logs -n <namespace> <pod-name> --tail=100

# Include timestamps
kubectl logs -n <namespace> <pod-name> --timestamps
```

### Access Server Console

```bash
# Shell access
kubectl exec -it -n <namespace> <pod-name> -- bash

# Check server status via HTTP API
kubectl exec -n <namespace> <pod-name> -- curl -s http://localhost:8080/status
```

### Check Resource Usage

```bash
# Pod resource usage
kubectl top pod -n <namespace> <pod-name>

# Detailed metrics
kubectl describe pod -n <namespace> <pod-name>
```

### Monitor Updates and Backups

```bash
# Check logs for update activity
kubectl logs -n <namespace> <pod-name> | grep -i "update"

# Check logs for backup activity
kubectl logs -n <namespace> <pod-name> | grep -i "backup"

# List backups
kubectl exec -n <namespace> <pod-name> -- ls -lh /home/steam/backups/
```

## Troubleshooting

### Server Not Appearing in Browser

1. **Check server is public:**

   ```yaml
   environment:
     - name: "PUBLIC"
       value: "1"
   ```

2. **Verify ports are accessible:**

   ```bash
   # Check service
   kubectl get svc -n <namespace>

   # Test connectivity (from outside cluster)
   nc -zvu <LOADBALANCER_IP> 2456
   nc -zvu <LOADBALANCER_IP> 2457
   ```

3. **Check firewall rules** on your network/router to allow UDP ports 2456-2458

4. **Review logs for errors:**
   ```bash
   kubectl logs -n <namespace> <pod-name> | grep -i error
   ```

### Cannot Connect to Server

**For LoadBalancer:**

```bash
# Get LoadBalancer IP
kubectl get svc -n <namespace>

# Ensure IP is assigned and not <pending>
# Connect using: <EXTERNAL-IP>:2456
```

**For NodePort:**

```bash
# Get NodePort
kubectl get svc -n <namespace>

# Connect using: <NODE-IP>:<NODE-PORT>
# Example: 192.168.1.50:31232
```

**Common issues:**

- Password mismatch (check PASSWORD environment variable)
- Ports blocked by firewall
- Wrong IP address or port
- Server still starting up (check logs)

### Slow First Startup

First startup downloads the full Valheim server (~1-2GB). This can take 10-30 minutes depending on your internet connection.

Monitor progress:

```bash
kubectl logs -f -n <namespace> <pod-name>
```

Look for: `Installing Valheim Dedicated Server` and download progress indicators.

### Crossplay Not Working

1. **Verify crossplay is enabled:**

   ```yaml
   environment:
     - name: "ENABLE_CROSSPLAY"
       value: "1"
   ```

2. **Check image version:**
   Crossplay requires Valheim 0.211.11+. Ensure you're using a recent image version:

   ```yaml
   image:
     tag: "3.1.0" # Or later
   ```

3. **Console players:** Ensure they're using the crossplay toggle in Valheim's network settings

### High Memory Usage

Valheim servers typically use 2-4Gi RAM. If experiencing OOM kills:

```bash
# Check current usage
kubectl top pod -n <namespace> <pod-name>

# Increase memory limits
helm upgrade <release-name> mbround18/valheim \
  --reuse-values \
  --set resources.limits.memory=6Gi
```

### World Not Persisting

Verify PVC mounts:

```bash
# Check PVCs are bound
kubectl get pvc -n <namespace>

# Verify mounts inside pod
kubectl exec -n <namespace> <pod-name> -- df -h
kubectl exec -n <namespace> <pod-name> -- ls -la /home/steam/.config/unity3d/IronGate/Valheim/worlds_local/
```

### Automatic Updates Not Working

Check update configuration:

```bash
# View update-related environment variables
kubectl describe pod -n <namespace> <pod-name> | grep -A 5 "Environment:"

# Check logs for update attempts
kubectl logs -n <namespace> <pod-name> | grep -i "update"
```

Ensure cron schedule is valid:

```yaml
environment:
  - name: "AUTO_UPDATE_SCHEDULE"
    value: "0 4 * * *" # Valid cron format: minute hour day month weekday
```

### Backup Issues

```bash
# Check backup PVC is mounted
kubectl exec -n <namespace> <pod-name> -- ls -la /home/steam/backups/

# Verify backup space
kubectl exec -n <namespace> <pod-name> -- df -h /home/steam/backups/

# Check backup logs
kubectl logs -n <namespace> <pod-name> | grep -i backup

# Manual test backup
kubectl exec -n <namespace> <pod-name> -- bash -c "cd /home/steam/backups && tar czf test-backup.tar.gz -C /home/steam/.config/unity3d/IronGate/Valheim worlds_local"
```

## Upgrading

### Upgrade the Chart

```bash
# Update repository
helm repo update

# Upgrade with existing values
helm upgrade <release-name> mbround18/valheim --reuse-values

# Upgrade with new values
helm upgrade <release-name> mbround18/valheim -f values.yaml
```

### Upgrade Valheim Version

The container handles Valheim updates automatically if `AUTO_UPDATE` is enabled. To manually trigger an update:

```bash
# Force update by setting UPDATE_ON_STARTUP
# Note: Find the correct array index by checking your current values
helm upgrade <release-name> mbround18/valheim \
  --reuse-values \
  --set environment[13].name=UPDATE_ON_STARTUP \
  --set environment[13].value=1

# Then restart the pod
kubectl rollout restart deployment <release-name>-valheim -n <namespace>
```

Or update the image tag:

```yaml
image:
  tag: "3.2.0" # New version
```

## Uninstalling

```bash
# Uninstall the release
helm uninstall <release-name> -n <namespace>

# PVCs are retained by default for data safety
# To view them:
kubectl get pvc -n <namespace>

# To delete PVCs (WARNING: This deletes all server data):
kubectl delete pvc <release-name>-data -n <namespace>
kubectl delete pvc <release-name>-saves -n <namespace>
kubectl delete pvc <release-name>-backups -n <namespace>
```

## Support

- **Chart Issues**: [GitHub Issues](https://github.com/mbround18/helm-charts/issues)
- **Container Issues**: [valheim-docker Issues](https://github.com/mbround18/valheim-docker/issues)
- **Valheim Game**: [Official Valheim Discord](https://discord.gg/valheim)

## License

This Helm chart is released under the Apache License 2.0. See the [LICENSE](../../LICENSE) file for details.

## References

- [Valheim Official Site](https://www.valheimgame.com/)
- [mbround18/valheim-docker](https://github.com/mbround18/valheim-docker)
- [Valheim Dedicated Server Guide](https://valheim.fandom.com/wiki/Dedicated_server)
