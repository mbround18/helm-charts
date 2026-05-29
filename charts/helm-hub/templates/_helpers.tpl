{{/* Common helpers for helm-hub chart */}}
{{- define "helm-hub.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end }}

{{- define "helm-hub.fullname" -}}
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

{{- define "helm-hub.labels" -}}
helm.sh/chart: {{ include "helm-hub.chart" . }}
{{ include "helm-hub.selectorLabels" . }}
{{- include "gitops-tools.argocd.labels" (dict "context" .) }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "helm-hub.selectorLabels" -}}
app.kubernetes.io/name: {{ include "helm-hub.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "helm-hub.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "helm-hub.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "helm-hub.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the database host
*/}}
{{- define "helm-hub.databaseHost" -}}
{{- if .Values.postgres.enabled -}}
  {{- if .Values.postgres.fullnameOverride -}}
    {{- .Values.postgres.fullnameOverride -}}
  {{- else -}}
    {{- printf "%s-db" (include "helm-hub.fullname" .) -}}
  {{- end -}}
{{- else -}}
  {{- .Values.database.host -}}
{{- end -}}
{{- end -}}

{{/*
Create the database name
*/}}
{{- define "helm-hub.databaseName" -}}
{{- if .Values.postgres.enabled -}}
  {{- .Values.postgres.auth.database -}}
{{- else -}}
  {{- .Values.database.name -}}
{{- end -}}
{{- end -}}

{{/*
Create the database user
*/}}
{{- define "helm-hub.databaseUser" -}}
{{- if .Values.postgres.enabled -}}
  {{- .Values.postgres.auth.username -}}
{{- else -}}
  {{- .Values.database.user -}}
{{- end -}}
{{- end -}}
