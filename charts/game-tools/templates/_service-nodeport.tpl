{{/*
Create a NodePort service for game servers with auto port negotiation.
Usage:
{{- include "game-tools.service.nodeport" (dict "serviceName" "my-service" "ports" .Values.service.ports "selectorLabels" (include "mychart.selectorLabels" .) "labels" (include "mychart.labels" .) "context" .) }}

Parameters:
- serviceName: Name of the service
- ports: Array of port objects with fields: name, port, targetPort, protocol, nodePort (optional)
- selectorLabels: Selector labels as string (typically from selectorLabels helper)
- labels: Service labels as string (typically from labels helper)
- context: Root context (.)
*/}}
{{- define "game-tools.service.nodeport" -}}
apiVersion: v1
kind: Service
metadata:
  name: {{ .serviceName }}
  {{- if .labels }}
  labels:
{{ .labels | indent 4 }}
  {{- end }}
spec:
  type: NodePort
  ports:
  {{- range .ports }}
  - name: {{ .name }}
    port: {{ .port }}
    targetPort: {{ .targetPort }}
    protocol: {{ .protocol | default "TCP" }}
    {{- if .nodePort }}
    nodePort: {{ .nodePort }}
    {{- end }}
  {{- end }}
  selector:
{{ .selectorLabels | indent 4 }}
{{- end }}
