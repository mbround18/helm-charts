{{- define "thanos.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "thanos.fullname" -}}
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

{{- define "thanos.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "thanos.labels" -}}
helm.sh/chart: {{ include "thanos.chart" . }}
{{ include "thanos.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- include "gitops-tools.argocd.labels" (dict "context" .) }}
{{- end }}

{{- define "thanos.selectorLabels" -}}
app.kubernetes.io/name: {{ include "thanos.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/* Labels and selector labels for one component: (dict "context" . "component" "store") */}}
{{- define "thanos.componentLabels" -}}
{{ include "thanos.labels" .context }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{- define "thanos.componentSelectorLabels" -}}
{{ include "thanos.selectorLabels" .context }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{- define "thanos.image" -}}
{{- $image := printf "%s:%s" .Values.image.repository (default .Chart.AppVersion .Values.image.tag) -}}
{{- if .Values.image.digest -}}
{{- $image = printf "%s@%s" $image .Values.image.digest -}}
{{- end -}}
{{- $image -}}
{{- end }}

{{/* The bucket configuration, mounted from a Secret this chart never creates. */}}
{{- define "thanos.objstoreVolume" -}}
- name: objstore
  secret:
    secretName: {{ .Values.objstore.existingSecret }}
    items:
      - key: {{ .Values.objstore.key }}
        path: objstore.yml
{{- end }}

{{- define "thanos.objstoreMount" -}}
- name: objstore
  mountPath: /etc/thanos
  readOnly: true
{{- end }}

{{/* Environment for the components that open the bucket (store, compactor). */}}
{{- define "thanos.objstoreEnv" -}}
{{- with .Values.objstore.extraEnvFrom }}
envFrom:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- with .Values.objstore.extraEnv }}
env:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end }}

{{- define "thanos.probes" -}}
readinessProbe:
  httpGet:
    path: /-/ready
    port: http
  periodSeconds: 10
livenessProbe:
  httpGet:
    path: /-/healthy
    port: http
  periodSeconds: 30
  failureThreshold: 4
{{- end }}

{{- define "thanos.volumeClaim" -}}
- metadata:
    name: data
  spec:
    accessModes:
      - {{ .accessMode }}
    resources:
      requests:
        storage: {{ .size }}
    {{- if .storageClass }}
    {{- if eq "-" .storageClass }}
    storageClassName: ""
    {{- else }}
    storageClassName: {{ .storageClass | quote }}
    {{- end }}
    {{- end }}
{{- end }}
