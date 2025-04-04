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
