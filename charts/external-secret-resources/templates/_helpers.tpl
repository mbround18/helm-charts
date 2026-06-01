{{- define "external-secret-resources.name" -}}
external-secret-resources
{{- end -}}

{{- define "external-secret-resources.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "external-secret-resources.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "external-secret-resources.labels" -}}
app.kubernetes.io/name: {{ include "external-secret-resources.name" . | quote }}
app.kubernetes.io/instance: {{ .Release.Name | quote }}
helm.sh/chart: {{ printf "%s-%s" (include "external-secret-resources.name" .) (.Chart.Version | replace "+" "_") | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service | quote }}
{{- end -}}

{{- define "external-secret-resources.mergeMaps" -}}
{{- $result := dict -}}
{{- range .maps -}}
{{- with . -}}
{{- range $key, $value := . -}}
{{- $_ := set $result $key $value -}}
{{- end -}}
{{- end -}}
{{- end -}}
{{- if gt (len $result) 0 -}}
{{- toYaml $result -}}
{{- end -}}
{{- end -}}
