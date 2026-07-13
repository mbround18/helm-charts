{{- define "keycloak.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "keycloak.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "keycloak.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "keycloak.labels" -}}
helm.sh/chart: {{ include "keycloak.chart" . }}
{{ include "keycloak.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- include "gitops-tools.argocd.labels" (dict "context" .) }}
{{- end -}}

{{- define "keycloak.selectorLabels" -}}
app.kubernetes.io/name: {{ include "keycloak.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "keycloak.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "keycloak.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{- define "keycloak.bootstrapAdminSecretName" -}}
{{- if .Values.bootstrapAdmin.existingSecret -}}
{{- .Values.bootstrapAdmin.existingSecret -}}
{{- else -}}
{{- printf "%s-admin" (include "keycloak.fullname" .) -}}
{{- end -}}
{{- end -}}

{{- define "keycloak.dbSecretName" -}}
{{- if .Values.database.existingSecret -}}
{{- .Values.database.existingSecret -}}
{{- else -}}
{{- printf "%s-db" (include "keycloak.fullname" .) -}}
{{- end -}}
{{- end -}}

{{- define "keycloak.persistenceClaimName" -}}
{{- if .Values.persistence.existingClaim -}}
{{- .Values.persistence.existingClaim -}}
{{- else if .Values.persistence.claimName -}}
{{- .Values.persistence.claimName -}}
{{- else -}}
{{- printf "%s-data" (include "keycloak.fullname" .) -}}
{{- end -}}
{{- end -}}

{{- define "keycloak.prebuildClaimName" -}}
{{- if .Values.keycloak.preDeployJobs.persistence.existingClaim -}}
{{- .Values.keycloak.preDeployJobs.persistence.existingClaim -}}
{{- else if .Values.keycloak.preDeployJobs.persistence.claimName -}}
{{- .Values.keycloak.preDeployJobs.persistence.claimName -}}
{{- else -}}
{{- printf "%s-prebuild" (include "keycloak.fullname" .) -}}
{{- end -}}
{{- end -}}
