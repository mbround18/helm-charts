{{/*
Expand the name of the chart.
*/}}
{{- define "backup-job.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "backup-job.fullname" -}}
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
{{- define "backup-job.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "backup-job.labels" -}}
helm.sh/chart: {{ include "backup-job.chart" . }}
{{ include "backup-job.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- include "gitops-tools.argocd.labels" (dict "context" .) }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "backup-job.selectorLabels" -}}
app.kubernetes.io/name: {{ include "backup-job.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
