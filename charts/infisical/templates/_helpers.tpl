{{- define "infisical.name" -}}
infisical
{{- end -}}

{{- define "infisical.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{ .Values.fullnameOverride | trimSuffix "-" }}
{{- else -}}
{{ include "infisical.name" . }}-{{ .Release.Name }}
{{- end -}}
{{- end -}}

{{- define "infisical.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/name: {{ include "infisical.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "infisical.selectorLabels" -}}
app.kubernetes.io/name: {{ include "infisical.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "infisical.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "infisical.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{- define "infisical.namespace" -}}
{{- if .Values.namespace.name -}}
{{ .Values.namespace.name }}
{{- else -}}
{{ .Release.Namespace }}
{{- end -}}
{{- end -}}