{{/* vim: set filetype=mustache: */}}
{{/*
Expand the name of the chart.
*/}}
{{- define "opentelemetry-collector.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "opentelemetry-collector.fullname" -}}
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
{{- define "opentelemetry-collector.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "opentelemetry-collector.labels" -}}
helm.sh/chart: {{ include "opentelemetry-collector.chart" . }}
{{ include "opentelemetry-collector.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "opentelemetry-collector.selectorLabels" -}}
app.kubernetes.io/name: {{ include "opentelemetry-collector.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "opentelemetry-collector.serviceAccountName" -}}
{{- if .Values.rbac.serviceAccount.create }}
{{- default (include "opentelemetry-collector.fullname" .) .Values.rbac.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.rbac.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Generate the OpenTelemetry Collector configuration.
*/}}
{{- define "opentelemetry-collector.config" -}}
{{- $cfg := .Values.config | deepCopy -}}

{{- /* Memory Limiter Processor */ -}}
{{- if .Values.memory_limiter.enabled -}}
  {{- $memLimitRaw := .Values.resources.limits.memory -}}
  {{- $memLimitMib := 0 -}}
  {{- if $memLimitRaw -}}
    {{- if kindIs "string" $memLimitRaw -}}
      {{- if hasSuffix "Gi" $memLimitRaw -}}
        {{- $memLimitMib = trimSuffix "Gi" $memLimitRaw | atoi | mul 1024 -}}
      {{- else if hasSuffix "Mi" $memLimitRaw -}}
        {{- $memLimitMib = trimSuffix "Mi" $memLimitRaw | atoi -}}
      {{- else if hasSuffix "Ki" $memLimitRaw -}}
        {{- $memLimitMib = trimSuffix "Ki" $memLimitRaw | atoi | div 1024 -}}
      {{- end -}}
    {{- else -}}
      {{- $memLimitMib = $memLimitRaw | div 1048576 -}}
    {{- end -}}
  {{- end -}}
  {{- $limits := dict "limit_mib" 0 "spike_limit_mib" 0 -}}
  {{- if gt $memLimitMib 0 -}}
    {{- $_ := set $limits "limit_mib" (div (mul $memLimitMib .Values.memory_limiter.percentage_of_limit) 100) -}}
    {{- $_ := set $limits "spike_limit_mib" (div (mul $limits.limit_mib .Values.memory_limiter.spike_percentage) 100) -}}
  {{- end -}}
  {{- $memoryLimiterConfig := dict "check_interval" "1s" "limit_mib" $limits.limit_mib "spike_limit_mib" $limits.spike_limit_mib -}}
  {{- $_ := set $cfg.processors "memory_limiter" $memoryLimiterConfig -}}
{{- end -}}

{{- /* Batch Processor */ -}}
{{- if .Values.batch_processor.enabled -}}
  {{- $batchProcessorConfig := dict "timeout" .Values.batch_processor.timeout "send_batch_size" .Values.batch_processor.send_batch_size -}}
  {{- $_ := set $cfg.processors "batch" $batchProcessorConfig -}}
{{- end -}}

{{- /* Self-Observability */ -}}
{{- if .Values.observability.enabled -}}
  {{- $telemetryConfig := dict "metrics" (dict "address" "0.0.0.0:8888") -}}
  {{- $_ := set $cfg.service "telemetry" $telemetryConfig -}}
{{- end -}}

{{- toYaml $cfg -}}
{{- end -}}
