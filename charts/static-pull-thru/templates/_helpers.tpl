{{/* Common helpers for static-pull-thru chart */}}
{{- define "static-pull-thru.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end }}

{{- define "static-pull-thru.fullname" -}}
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

{{- define "static-pull-thru.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "static-pull-thru.labels" -}}
helm.sh/chart: {{ include "static-pull-thru.chart" . }}
{{ include "static-pull-thru.selectorLabels" . }}
{{- include "gitops-tools.argocd.labels" (dict "context" .) }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "static-pull-thru.selectorLabels" -}}
app.kubernetes.io/name: {{ include "static-pull-thru.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/* Headers shared by every proxied location. */}}
{{- define "static-pull-thru.proxyHeaders" -}}
proxy_http_version 1.1;
proxy_set_header Host {{ default "$host" .Values.upstream.hostHeader }};
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection $connection_upgrade;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $forwarded_proto;
proxy_set_header X-Forwarded-Host $host;
proxy_connect_timeout {{ .Values.upstream.connectTimeout }};
{{- end }}
