{{/*
Expand the name of the chart.
*/}}
{{- define "openobserve.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "openobserve.fullname" -}}
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
Create chart-level labels to be applied to every resource.
*/}}
{{- define "openobserve.labels" -}}
helm.sh/chart: {{ include "openobserve.chart" . }}
{{ include "openobserve.selectorLabels" . }}
{{- include "gitops-tools.argocd.labels" (dict "context" .) }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "openobserve.selectorLabels" -}}
app.kubernetes.io/name: {{ include "openobserve.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "openobserve.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "openobserve.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Return the proper image name
*/}}
{{- define "openobserve.image" -}}
{{- printf "%s:%s" .Values.image.repository ( .Values.image.tag | default .Chart.AppVersion) }}
{{- end }}

{{/*
Get memory cache max size from percentage.
This helper parses a memory string (e.g., "4Gi", "500Mi") and calculates a percentage of it.
*/}}
{{- define "openobserve.memoryCacheMaxSize" -}}
{{- $memLimit := .Values.resources.limits.memory | default "0Gi" -}}
{{- $memLimitBytes := 0 -}}
{{- if regexMatch "[0-9]+Gi" $memLimit -}}
  {{- $memLimitBytes = regexReplaceAll "[^0-9]" $memLimit "" | int64 | mul 1073741824 -}}
{{- else if regexMatch "[0-9]+Mi" $memLimit -}}
  {{- $memLimitBytes = regexReplaceAll "[^0-9]" $memLimit "" | int64 | mul 1048576 -}}
{{- else if regexMatch "[0-9]+Ki" $memLimit -}}
  {{- $memLimitBytes = regexReplaceAll "[^0-9]" $memLimit "" | int64 | mul 1024 -}}
{{- else -}}
  {{- $memLimitBytes = regexReplaceAll "[^0-9]" $memLimit "" | int64 -}}
{{- end -}}
{{- $cacheSize := div (mul $memLimitBytes .Values.config.memoryCacheMaxSizePercentage) 100 -}}
{{- printf "%d" $cacheSize -}}
{{- end -}}

{{/*
Return the chart version
*/}}
{{- define "openobserve.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end -}}
