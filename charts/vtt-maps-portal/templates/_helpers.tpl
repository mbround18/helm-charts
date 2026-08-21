{{/*
Expand the name of the chart.
*/}}
{{- define "vtt-maps-portal.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "vtt-maps-portal.fullname" -}}
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
{{- define "vtt-maps-portal.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "vtt-maps-portal.labels" -}}
helm.sh/chart: {{ include "vtt-maps-portal.chart" . }}
{{ include "vtt-maps-portal.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- include "gitops-tools.argocd.labels" (dict "context" .) }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "vtt-maps-portal.selectorLabels" -}}
app.kubernetes.io/name: {{ include "vtt-maps-portal.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "vtt-maps-portal.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "vtt-maps-portal.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Whether the ExternalSecrets Operator path for the generated JWT/OAuth-state
secrets is active -- mirrors gitops-tools' argoCd.mode auto-detection, but
kept local to this chart since external-secret-resources is an application
(not library) chart and this only needs to gate this chart's own fallback
Secret template.
*/}}
{{- define "vtt-maps-portal.esoEnabled" -}}
{{- $mode := lower (default "auto" .Values.externalSecrets.mode) -}}
{{- if eq $mode "enabled" -}}
true
{{- else if eq $mode "disabled" -}}
false
{{- else if or (.Capabilities.APIVersions.Has "external-secrets.io/v1") (.Capabilities.APIVersions.Has "external-secrets.io/v1beta1") -}}
true
{{- else -}}
false
{{- end -}}
{{- end -}}

{{/*
Shared env block: MONGO_URI (secret ref, mongo subchart, or omitted),
JWT_SECRET_CURRENT/OAUTH_STATE_SECRET (secret ref override, or the Secret
this chart generates itself -- see generatedSecretName), plain env vars,
then any other secretEnv entries. Used by both the Deployment and the
preload CronJob so the two stay in lockstep.
*/}}
{{- define "vtt-maps-portal.env" -}}
{{- if .Values.secretEnv.MONGO_URI.secretName }}
- name: MONGO_URI
  valueFrom:
    secretKeyRef:
      name: {{ .Values.secretEnv.MONGO_URI.secretName }}
      key: {{ .Values.secretEnv.MONGO_URI.secretKey }}
{{- else if .Values.mongo.enabled }}
- name: MONGO_URI
  value: "mongodb://{{ include "mongo.fullname" .Subcharts.mongo }}:{{ .Values.mongo.service.port }}/{{ .Values.mongo.mongodb.db }}"
{{- end }}
{{- if .Values.secretEnv.RUSTFS_ENDPOINT.secretName }}
- name: RUSTFS_ENDPOINT
  valueFrom:
    secretKeyRef:
      name: {{ .Values.secretEnv.RUSTFS_ENDPOINT.secretName }}
      key: {{ .Values.secretEnv.RUSTFS_ENDPOINT.secretKey }}
{{- else if .Values.rustfs.enabled }}
- name: RUSTFS_ENDPOINT
  value: "http://{{ include "rustfs.fullname" .Subcharts.rustfs }}:{{ .Values.rustfs.service.port }}"
{{- end }}
{{- if .Values.generatedSecrets.enabled }}
- name: JWT_SECRET_CURRENT
  valueFrom:
    secretKeyRef:
      name: {{ .Values.generatedSecretName }}
      key: JWT_SECRET_CURRENT
- name: OAUTH_STATE_SECRET
  valueFrom:
    secretKeyRef:
      name: {{ .Values.generatedSecretName }}
      key: OAUTH_STATE_SECRET
- name: RUSTFS_ACCESS_KEY
  valueFrom:
    secretKeyRef:
      name: {{ .Values.generatedSecretName }}
      key: RUSTFS_ACCESS_KEY
- name: RUSTFS_SECRET_KEY
  valueFrom:
    secretKeyRef:
      name: {{ .Values.generatedSecretName }}
      key: RUSTFS_SECRET_KEY
{{- end }}
{{- range $key, $value := .Values.env }}
- name: {{ $key }}
  value: {{ $value | quote }}
{{- end }}
{{- range $name, $ref := .Values.secretEnv }}
{{- if and $ref.secretName (not (has $name (list "MONGO_URI" "RUSTFS_ENDPOINT"))) }}
- name: {{ $name }}
  valueFrom:
    secretKeyRef:
      name: {{ $ref.secretName }}
      key: {{ $ref.secretKey }}
{{- end }}
{{- end }}
{{- end }}
