{{- define "gitops-tools.argocd.enabled" -}}
{{- $mode := lower (default "auto" .Values.argoCd.mode) -}}
{{- if eq $mode "enabled" -}}
true
{{- else if eq $mode "disabled" -}}
false
{{- else if or (.Capabilities.APIVersions.Has "argoproj.io/v1alpha1/Application") (.Capabilities.APIVersions.Has "argoproj.io/v1alpha1/AppProject") (.Capabilities.APIVersions.Has "argoproj.io/v1alpha1/ApplicationSet") -}}
true
{{- else -}}
false
{{- end -}}
{{- end -}}

{{- define "gitops-tools.argocd.labels" -}}
{{- if eq (trim (include "gitops-tools.argocd.enabled" .context)) "true" -}}
{{- with .context.Values.argoCd.instanceLabel }}
argocd.argoproj.io/instance: {{ . | quote }}
{{- end }}
{{- with .context.Values.argoCd.commonLabels }}
{{- range $key, $value := . }}
{{ $key }}: {{ $value | quote }}
{{- end }}
{{- end }}
{{- end -}}
{{- end -}}

{{- define "gitops-tools.argocd.syncWave" -}}
{{- if hasKey . "phase" -}}
{{- $phase := lower .phase -}}
{{- if eq $phase "foundation" -}}
0
{{- else if or (eq $phase "database") (eq $phase "data") (eq $phase "data-layer") -}}
10
{{- else if eq $phase "supporting" -}}
20
{{- else if eq $phase "release" -}}
30
{{- else if or (eq $phase "ingress") (eq $phase "config") -}}
40
{{- else -}}
{{- fail (printf "unknown gitops-tools argocd phase %q" $phase) -}}
{{- end -}}
{{- else if hasKey . "syncWave" -}}
{{- printf "%v" .syncWave -}}
{{- end -}}
{{- end -}}

{{- define "gitops-tools.argocd.annotations" -}}
{{- $annotations := dict -}}
{{- if eq (trim (include "gitops-tools.argocd.enabled" .context)) "true" -}}
{{- with .context.Values.argoCd.commonAnnotations -}}
{{- range $key, $value := . -}}
{{- $_ := set $annotations $key $value -}}
{{- end -}}
{{- end -}}
{{- $syncWave := trim (include "gitops-tools.argocd.syncWave" .) -}}
{{- if $syncWave -}}
{{- $_ := set $annotations "argocd.argoproj.io/sync-wave" $syncWave -}}
{{- end -}}
{{- end -}}
{{- with .annotations -}}
{{- range $key, $value := . -}}
{{- $_ := set $annotations $key $value -}}
{{- end -}}
{{- end -}}
{{- if gt (len $annotations) 0 -}}
{{- toYaml $annotations -}}
{{- end -}}
{{- end -}}