{{/*
Expand the name of the chart.
*/}}
{{- define "showcase-yourself.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "showcase-yourself.fullname" -}}
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
{{- define "showcase-yourself.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "showcase-yourself.labels" -}}
helm.sh/chart: {{ include "showcase-yourself.chart" . }}
{{ include "showcase-yourself.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- include "gitops-tools.argocd.labels" (dict "context" .) }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "showcase-yourself.selectorLabels" -}}
app.kubernetes.io/name: {{ include "showcase-yourself.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Per-component labels. Usage:
  {{ include "showcase-yourself.componentLabels" (dict "context" . "component" "backend") }}
*/}}
{{- define "showcase-yourself.componentLabels" -}}
{{ include "showcase-yourself.labels" .context }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{/*
Per-component selector labels. Usage:
  {{ include "showcase-yourself.componentSelectorLabels" (dict "context" . "component" "backend") }}
*/}}
{{- define "showcase-yourself.componentSelectorLabels" -}}
{{ include "showcase-yourself.selectorLabels" .context }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "showcase-yourself.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "showcase-yourself.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
