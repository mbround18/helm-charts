{{/*
Expand the name of the chart.
*/}}
{{- define "keygen.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "keygen.fullname" -}}
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
{{- define "keygen.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "keygen.labels" -}}
helm.sh/chart: {{ include "keygen.chart" . }}
{{ include "keygen.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- include "gitops-tools.argocd.labels" (dict "context" .) }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "keygen.selectorLabels" -}}
app.kubernetes.io/name: {{ include "keygen.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Worker selector labels (distinct component so the web/worker Deployments
never overlap in Service selection).
*/}}
{{- define "keygen.workerSelectorLabels" -}}
{{ include "keygen.selectorLabels" . }}
app.kubernetes.io/component: worker
{{- end }}

{{- define "keygen.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "keygen.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Name of the Secret holding the app's own generated secrets
(SECRET_KEY_BASE, ENCRYPTION_*, KEYGEN_ACCOUNT_ID).
*/}}
{{- define "keygen.secretsName" -}}
{{- default (printf "%s-secrets" (include "keygen.fullname" .)) .Values.secrets.name }}
{{- end }}

{{/*
Postgres host as reached inside the cluster. Assumes the bundled postgres
subchart named "postgres" -- override via .Values.postgres.host if pointing
at an external database.
*/}}
{{- define "keygen.postgresHost" -}}
{{- if .Values.postgres.host }}
{{- .Values.postgres.host }}
{{- else }}
{{- printf "%s-postgres" .Release.Name }}
{{- end }}
{{- end }}

{{/*
Redis host as reached inside the cluster. Assumes the bundled redis
subchart named "redis" -- override via .Values.redis.host if pointing at an
external Redis.
*/}}
{{- define "keygen.redisHost" -}}
{{- if .Values.redis.host }}
{{- .Values.redis.host }}
{{- else }}
{{- printf "%s-redis" .Release.Name }}
{{- end }}
{{- end }}
