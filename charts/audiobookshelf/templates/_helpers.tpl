{{/* Common helpers for audiobookshelf chart */}}
{{- define "audiobookshelf.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end }}

{{- define "audiobookshelf.fullname" -}}
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

{{- define "audiobookshelf.labels" -}}
helm.sh/chart: {{ include "audiobookshelf.chart" . }}
{{ include "audiobookshelf.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "audiobookshelf.selectorLabels" -}}
app.kubernetes.io/name: {{ include "audiobookshelf.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "audiobookshelf.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- /* Generate basic Istio http route for merge helper */ -}}
{{- define "audiobookshelf.istioHttpRoute" -}}
- name: "audiobookshelf-web"
  match:
    - uri:
        prefix: /
  route:
    - destination:
        host: {{ printf "%s.%s.svc.cluster.local" (default (include "audiobookshelf.fullname" .) "audiobookshelf") .Release.Namespace }}
        port:
          number: {{ .Values.service.port }}
{{- end }}

{{- define "audiobookshelf.ingressPaths" -}}
- path: /
  pathType: Prefix
  backend:
    service:
      name: {{ include "audiobookshelf.fullname" . }}
      port:
        number: {{ .Values.service.port }}
{{- end }}
