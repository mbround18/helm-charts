{{/* Common helpers for changedetection-io chart */}}
{{- define "changedetection-io.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end }}

{{- define "changedetection-io.fullname" -}}
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

{{- define "changedetection-io.labels" -}}
helm.sh/chart: {{ include "changedetection-io.chart" . }}
{{ include "changedetection-io.selectorLabels" . }}
{{- include "gitops-tools.argocd.labels" (dict "context" .) }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "changedetection-io.selectorLabels" -}}
app.kubernetes.io/name: {{ include "changedetection-io.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "changedetection-io.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "changedetection-io.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "changedetection-io.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
