{{/*
Expand the name of the chart.
*/}}
{{- define "meilisearch.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "meilisearch.fullname" -}}
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

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "meilisearch.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "meilisearch.labels" -}}
helm.sh/chart: {{ include "meilisearch.chart" . }}
{{ include "meilisearch.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "meilisearch.selectorLabels" -}}
app.kubernetes.io/name: {{ include "meilisearch.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Generate HTTP routes for Istio VirtualService with optional UI route
*/}}
{{- define "meilisearch.istioHttpRoutes" -}}
- name: "meilisearch-api"
  route:
    - destination:
        host: meilisearch.default.svc.cluster.local
        port:
          number: 7700
{{- if .Values.ui.enabled }}
- name: "meilisearch-ui"
  match:
    - uri:
        prefix: {{ .Values.ui.basePath }}
  route:
    - destination:
        host: meilisearch.default.svc.cluster.local
        port:
          number: 24900
{{- end }}
{{- end }}

{{/*
Generate ingress paths with optional UI path
*/}}
{{- define "meilisearch.ingressPaths" -}}
- path: /
  pathType: Prefix
  backend:
    service:
      name: {{ include "meilisearch.fullname" . }}
      port:
        number: {{ .Values.service.port }}
{{- if and .Values.ui.enabled .Values.ui.ingress.enabled }}
- path: {{ .Values.ui.basePath }}
  pathType: Prefix
  backend:
    service:
      name: {{ include "meilisearch.fullname" . }}-ui
      port:
        number: {{ .Values.service.uiPort }}
{{- end }}
{{- end }}
