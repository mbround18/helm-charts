{{/*
Expand the name of the chart.
*/}}
{{- define "istio-ingress.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "istio-ingress.fullname" -}}
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
{{- define "istio-ingress.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "istio-ingress.labels" -}}
helm.sh/chart: {{ include "istio-ingress.chart" . }}
{{ include "istio-ingress.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "istio-ingress.selectorLabels" -}}
app.kubernetes.io/name: {{ include "istio-ingress.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Return the gateway name
*/}}
{{- define "istio-ingress.gatewayName" -}}
{{- if .Values.gateway.name }}
{{- .Values.gateway.name }}
{{- else }}
{{- include "istio-ingress.fullname" . }}-gateway
{{- end }}
{{- end }}

{{/*
Return the VirtualService name
*/}}
{{- define "istio-ingress.vsName" -}}
{{- if .Values.virtualService.name }}
{{- .Values.virtualService.name }}
{{- else }}
{{- include "istio-ingress.fullname" . }}-vs
{{- end }}
{{- end }}

{{/*
Return the namespace
*/}}
{{- define "istio-ingress.namespace" -}}
{{- if .Values.gateway.namespace }}
{{- .Values.gateway.namespace }}
{{- else }}
{{- .Release.Namespace }}
{{- end }}
{{- end }}

{{/*
Construct gateway reference for VirtualService
*/}}
{{- define "istio-ingress.gatewayRef" -}}
{{- if .Values.virtualService.gateways }}
{{- toYaml .Values.virtualService.gateways }}
{{- else if .Values.helpers.useLocalGateway }}
- {{ include "istio-ingress.gatewayName" . }}
{{- end }}
{{- end }}
