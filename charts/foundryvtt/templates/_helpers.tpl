{{- define "foundryvtt.name" -}}
foundryvtt
{{- end -}}

{{- define "foundryvtt.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{ .Values.fullnameOverride | trimSuffix "-" }}
{{- else -}}
{{ include "foundryvtt.name" . }}-{{ .Release.Name }}
{{- end -}}
{{- end -}}

{{/* Chart name and version */}}
{{- define "foundryvtt.chart" -}}
{{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
{{- end -}}

{{/* Standard labels (Kubernetes recommended) */}}
{{- define "foundryvtt.labels" -}}
helm.sh/chart: {{ include "foundryvtt.chart" . }}
app.kubernetes.io/name: {{ include "foundryvtt.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- if .Values.commonLabels }}
{{- toYaml .Values.commonLabels | nindent 0 }}
{{- end }}
{{- end -}}

{{/* Selector labels (should be immutable for a release) */}}
{{- define "foundryvtt.selectorLabels" -}}
app.kubernetes.io/name: {{ include "foundryvtt.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/* ServiceAccount name helper */}}
{{- define "foundryvtt.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "foundryvtt.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}
