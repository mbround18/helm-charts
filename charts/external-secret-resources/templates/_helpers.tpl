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

{{- define "external-secret-resources.enabled" -}}
{{- $mode := lower (default "" .Values.mode) -}}
{{- if eq $mode "enabled" -}}
true
{{- else if eq $mode "disabled" -}}
false
{{- else if eq $mode "auto" -}}
{{- if or (.Capabilities.APIVersions.Has "external-secrets.io/v1") (.Capabilities.APIVersions.Has "external-secrets.io/v1beta1") -}}
true
{{- else -}}
false
{{- end -}}
{{- else if .Values.enabled -}}
true
{{- else -}}
false
{{- end -}}
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
