{{/*
Return the .Values.secrets.password object or an empty dict for safe lookup in templates.
Usage:
  {{- $pw := include "syncthing.password" . | fromJson }}
*/}}
{{- define "syncthing.password" -}}
{{- $pw := (index (default dict .Values.secrets) "password") -}}
{{- if $pw }}{{ $pw | toJson }}{{ else }}{{ dict | toJson }}{{ end }}
{{- end }}
{{/* Common helpers for syncthing chart */}}
{{- define "syncthing.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end }}

{{- define "syncthing.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "syncthing.labels" -}}
helm.sh/chart: {{ include "syncthing.chart" . }}
{{ include "syncthing.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "syncthing.selectorLabels" -}}
app.kubernetes.io/name: {{ include "syncthing.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "syncthing.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- /* Generate basic Istio http route for merge helper */ -}}
{{- define "syncthing.istioHttpRoute" -}}
- name: "syncthing-web"
  match:
    - uri:
        prefix: /
  route:
    - destination:
        host: {{ printf "%s.%s.svc.cluster.local" (default (include "syncthing.fullname" .) "syncthing") .Release.Namespace }}
        port:
          number: {{ .Values.service.port }}
{{- end }}

{{- define "syncthing.ingressPaths" -}}
- path: /
  pathType: Prefix
  backend:
    service:
      name: {{ include "syncthing.fullname" . }}
      port:
        number: {{ .Values.service.port }}
{{- end }}

