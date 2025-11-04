# PVC Cleaning Guide

This guide explains how to clean Persistent Volume Claims (PVCs) for fresh installations or troubleshooting, covering StatefulSets, Deployments, and DaemonSets.

## Overview

When you need to clean a PVC (e.g., corrupted data, fresh install, troubleshooting), you must:

1. Scale down the workload to release the PVC
2. Mount the PVC to a temporary pod
3. Clean the PVC contents
4. Scale the workload back up

## Prerequisites

- `kubectl` access to the cluster
- Appropriate RBAC permissions for the namespace
- Knowledge of the PVC name and workload type

## StatefulSets

StatefulSets use `volumeClaimTemplates` and create PVCs with predictable names like `<pvc-name>-<statefulset-name>-<ordinal>`.

### Example: Cleaning a StatefulSet PVC

```bash
# 1. Scale down the StatefulSet
kubectl scale statefulset <statefulset-name> -n <namespace> --replicas=0

# 2. Wait for pods to terminate
kubectl wait --for=delete pod/<statefulset-name>-0 -n <namespace> --timeout=60s

# 3. Clean the PVC using a temporary pod
kubectl run pvc-cleaner --rm -i -n <namespace> --image=busybox:1.36 --overrides='
{
  "apiVersion": "v1",
  "spec": {
    "containers": [
      {
        "name": "pvc-cleaner",
        "image": "busybox:1.36",
        "command": ["sh", "-c", "rm -rf /data/* /data/.[!.]* /data/..?* 2>/dev/null || true; echo PVC cleaned"],
        "volumeMounts": [
          {
            "name": "data",
            "mountPath": "/data"
          }
        ]
      }
    ],
    "volumes": [
      {
        "name": "data",
        "persistentVolumeClaim": {
          "claimName": "<pvc-name>"
        }
      }
    ],
    "restartPolicy": "Never"
  }
}'

# 4. Scale back up
kubectl scale statefulset <statefulset-name> -n <namespace> --replicas=1
```

### Real Example: Vein Game Server

```bash
# Scale down
kubectl scale statefulset vein -n vein-server --replicas=0
kubectl wait --for=delete pod/vein-0 -n vein-server --timeout=60s

# Clean game-data PVC
kubectl run pvc-cleaner --rm -i -n vein-server --image=busybox:1.36 --overrides='
{
  "apiVersion": "v1",
  "spec": {
    "containers": [
      {
        "name": "pvc-cleaner",
        "image": "busybox:1.36",
        "command": ["sh", "-c", "rm -rf /data/* /data/.[!.]* /data/..?* 2>/dev/null || true; echo PVC cleaned"],
        "volumeMounts": [
          {
            "name": "game-data",
            "mountPath": "/data"
          }
        ]
      }
    ],
    "volumes": [
      {
        "name": "game-data",
        "persistentVolumeClaim": {
          "claimName": "game-data-vein-0"
        }
      }
    ],
    "restartPolicy": "Never"
  }
}'

# Scale back up
kubectl scale statefulset vein -n vein-server --replicas=1
```

## Deployments

Deployments typically reference PVCs directly by name.

### Example: Cleaning a Deployment PVC

```bash
# 1. Scale down the Deployment
kubectl scale deployment <deployment-name> -n <namespace> --replicas=0

# 2. Wait for pods to terminate
kubectl wait --for=delete pod -l app=<label> -n <namespace> --timeout=60s

# 3. Clean the PVC
kubectl run pvc-cleaner --rm -i -n <namespace> --image=busybox:1.36 --overrides='
{
  "apiVersion": "v1",
  "spec": {
    "containers": [
      {
        "name": "pvc-cleaner",
        "image": "busybox:1.36",
        "command": ["sh", "-c", "rm -rf /data/* /data/.[!.]* /data/..?* 2>/dev/null || true; echo PVC cleaned"],
        "volumeMounts": [
          {
            "name": "data",
            "mountPath": "/data"
          }
        ]
      }
    ],
    "volumes": [
      {
        "name": "data",
        "persistentVolumeClaim": {
          "claimName": "<pvc-name>"
        }
      }
    ],
    "restartPolicy": "Never"
  }
}'

# 4. Scale back up
kubectl scale deployment <deployment-name> -n <namespace> --replicas=1
```

## DaemonSets

DaemonSets run one pod per node and don't use replicas. You must cordon nodes or delete pods individually.

### Method 1: Cordon and Delete (Preferred)

```bash
# 1. Identify the node running the DaemonSet pod
NODE=$(kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.nodeName}')

# 2. Cordon the node (prevents scheduling)
kubectl cordon $NODE

# 3. Delete the DaemonSet pod
kubectl delete pod <pod-name> -n <namespace>

# 4. Clean the PVC
kubectl run pvc-cleaner --rm -i -n <namespace> --image=busybox:1.36 --overrides='
{
  "apiVersion": "v1",
  "spec": {
    "containers": [
      {
        "name": "pvc-cleaner",
        "image": "busybox:1.36",
        "command": ["sh", "-c", "rm -rf /data/* /data/.[!.]* /data/..?* 2>/dev/null || true; echo PVC cleaned"],
        "volumeMounts": [
          {
            "name": "data",
            "mountPath": "/data"
          }
        ]
      }
    ],
    "volumes": [
      {
        "name": "data",
        "persistentVolumeClaim": {
          "claimName": "<pvc-name>"
        }
      }
    ],
    "restartPolicy": "Never",
    "nodeName": "'"$NODE"'"
  }
}'

# 5. Uncordon the node to allow DaemonSet to reschedule
kubectl uncordon $NODE
```

### Method 2: Temporary Suspend (Kubernetes 1.21+)

```bash
# 1. Suspend the DaemonSet
kubectl patch daemonset <daemonset-name> -n <namespace> -p '{"spec":{"template":{"spec":{"nodeSelector":{"non-existing":"true"}}}}}'

# 2. Wait for pods to terminate
kubectl wait --for=delete pod -l app=<label> -n <namespace> --timeout=60s

# 3. Clean the PVC
kubectl run pvc-cleaner --rm -i -n <namespace> --image=busybox:1.36 --overrides='
{
  "apiVersion": "v1",
  "spec": {
    "containers": [
      {
        "name": "pvc-cleaner",
        "image": "busybox:1.36",
        "command": ["sh", "-c", "rm -rf /data/* /data/.[!.]* /data/..?* 2>/dev/null || true; echo PVC cleaned"],
        "volumeMounts": [
          {
            "name": "data",
            "mountPath": "/data"
          }
        ]
      }
    ],
    "volumes": [
      {
        "name": "data",
        "persistentVolumeClaim": {
          "claimName": "<pvc-name>"
        }
      }
    ],
    "restartPolicy": "Never"
  }
}'

# 4. Restore the DaemonSet
kubectl rollout undo daemonset <daemonset-name> -n <namespace>
```

## Cleaning Multiple PVCs

If you need to clean multiple PVCs simultaneously:

```bash
# Scale down
kubectl scale statefulset <name> -n <namespace> --replicas=0
kubectl wait --for=delete pod/<name>-0 -n <namespace> --timeout=60s

# Clean multiple PVCs in one pod
kubectl run pvc-cleaner --rm -i -n <namespace> --image=busybox:1.36 --overrides='
{
  "apiVersion": "v1",
  "spec": {
    "containers": [
      {
        "name": "pvc-cleaner",
        "image": "busybox:1.36",
        "command": ["sh", "-c", "rm -rf /data1/* /data1/.[!.]* /data1/..?* /data2/* /data2/.[!.]* /data2/..?* 2>/dev/null || true; echo All PVCs cleaned"],
        "volumeMounts": [
          {
            "name": "data1",
            "mountPath": "/data1"
          },
          {
            "name": "data2",
            "mountPath": "/data2"
          }
        ]
      }
    ],
    "volumes": [
      {
        "name": "data1",
        "persistentVolumeClaim": {
          "claimName": "<pvc-name-1>"
        }
      },
      {
        "name": "data2",
        "persistentVolumeClaim": {
          "claimName": "<pvc-name-2>"
        }
      }
    ],
    "restartPolicy": "Never"
  }
}'

# Scale back up
kubectl scale statefulset <name> -n <namespace> --replicas=1
```

## Selective Cleaning

To clean only specific directories or files:

```bash
kubectl run pvc-cleaner --rm -i -n <namespace> --image=busybox:1.36 --overrides='
{
  "apiVersion": "v1",
  "spec": {
    "containers": [
      {
        "name": "pvc-cleaner",
        "image": "busybox:1.36",
        "command": ["sh", "-c", "rm -rf /data/logs/* /data/cache/* && echo Specific directories cleaned"],
        "volumeMounts": [
          {
            "name": "data",
            "mountPath": "/data"
          }
        ]
      }
    ],
    "volumes": [
      {
        "name": "data",
        "persistentVolumeClaim": {
          "claimName": "<pvc-name>"
        }
      }
    ],
    "restartPolicy": "Never"
  }
}'
```

## Troubleshooting

### PVC is in use

If you get "PVC is in use" errors:

```bash
# Find all pods using the PVC
kubectl get pods --all-namespaces -o json | \
  jq -r '.items[] | select(.spec.volumes[]?.persistentVolumeClaim.claimName=="<pvc-name>") | .metadata.namespace + "/" + .metadata.name'

# Delete the pods
kubectl delete pod <pod-name> -n <namespace>
```

### Permission Denied

If the cleaner pod gets permission errors, you may need to run as root (not recommended for production):

```bash
# Modify the securityContext in the override JSON
"securityContext": {
  "runAsUser": 0
}
```

### PVC Not Found

Verify the PVC name:

```bash
# List PVCs in namespace
kubectl get pvc -n <namespace>

# For StatefulSets, PVC names follow the pattern:
# <volumeClaimTemplate-name>-<statefulset-name>-<ordinal>
# Example: game-data-vein-0
```

## Best Practices

1. **Always backup data** before cleaning PVCs
2. **Verify the PVC name** before running cleanup commands
3. **Use non-root containers** when possible (busybox:1.36 works well)
4. **Wait for pod termination** before cleaning to avoid conflicts
5. **Document the reason** for PVC cleanup in your runbooks
6. **Test in staging** before cleaning production PVCs
7. **Consider snapshots** if your storage provider supports them

## Alternative: PVC Snapshots

If your storage class supports snapshots, consider taking a snapshot before cleaning:

```bash
# Create VolumeSnapshot (requires VolumeSnapshot CRD)
kubectl create -f - <<EOF
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: <pvc-name>-snapshot
  namespace: <namespace>
spec:
  volumeSnapshotClassName: <snapshot-class>
  source:
    persistentVolumeClaimName: <pvc-name>
EOF

# Restore from snapshot by creating a new PVC
kubectl create -f - <<EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: <pvc-name>-restored
  namespace: <namespace>
spec:
  dataSource:
    name: <pvc-name>-snapshot
    kind: VolumeSnapshot
    apiGroup: snapshot.storage.k8s.io
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: <size>
EOF
```

## See Also

- [Kubernetes PVC Documentation](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
- [StatefulSet Documentation](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)
- [Volume Snapshots](https://kubernetes.io/docs/concepts/storage/volume-snapshots/)
