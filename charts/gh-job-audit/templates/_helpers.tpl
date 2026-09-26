{{- define "gh-job-audit.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "gh-job-audit.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "gh-job-audit.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "gh-job-audit.labels" -}}
app.kubernetes.io/name: {{ include "gh-job-audit.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}

{{- define "gh-job-audit.selectorLabels" -}}
app.kubernetes.io/name: {{ include "gh-job-audit.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "gh-job-audit.image" -}}
{{ .Values.image.repository }}:{{ default .Chart.AppVersion .Values.image.tag }}
{{- end -}}

{{- define "gh-job-audit.secretEnv" -}}
- name: {{ .env }}
  valueFrom:
    secretKeyRef:
      name: {{ .name | required (printf "existing secret name for %s is required" .env) }}
      key: {{ .key }}
{{- end -}}

{{/* Env shared by the web deployment and both cronjobs. */}}
{{- define "gh-job-audit.env" -}}
{{- $s := .Values.existingSecrets -}}
- { name: GH_OWNER, value: {{ required "owner is required" .Values.owner | quote }} }
- { name: BASE_URL, value: {{ required "baseUrl is required" .Values.baseUrl | quote }} }
- { name: MAIL_TO, value: {{ required "mail.to is required" .Values.mail.to | quote }} }
- { name: MAIL_FROM, value: {{ required "mail.from is required" .Values.mail.from | quote }} }
- { name: ARCHIVE_IDLE_DAYS, value: {{ .Values.thresholds.archiveIdleDays | quote }} }
- { name: ARCHIVE_POPULAR_SCORE, value: {{ .Values.thresholds.archivePopularScore | quote }} }
- { name: CI_OFF_RUNS_30D, value: {{ .Values.thresholds.ciOffRuns30d | quote }} }
- { name: PRIVATE_MINUTES_30D, value: {{ .Values.thresholds.privateMinutes30d | quote }} }
- { name: HEAVY_MINUTES_30D, value: {{ .Values.thresholds.heavyMinutes30d | quote }} }
- { name: BOT_RUNS_30D, value: {{ .Values.thresholds.botRuns30d | quote }} }
- { name: REPORT_MIN_ITEMS, value: {{ .Values.thresholds.reportMinItems | quote }} }
- { name: RENOTIFY_DAYS, value: {{ .Values.thresholds.renotifyDays | quote }} }
- { name: USAGE_ALERT_PCTS, value: {{ .Values.thresholds.usageAlertPcts | quote }} }
- { name: ACTIONS_QUOTA_MINUTES, value: {{ .Values.thresholds.actionsQuotaMinutes | quote }} }
- { name: ACTION_TTL_HOURS, value: {{ .Values.thresholds.actionTtlHours | quote }} }
- { name: GITHUB_APP_PRIVATE_KEY_FILE, value: /var/run/gh-app/private-key }
{{- if .Values.nats.url }}
- { name: NATS_URL, value: {{ .Values.nats.url | quote }} }
{{- end }}
{{ include "gh-job-audit.secretEnv" (dict "env" "GITHUB_APP_ID" "name" $s.githubApp.name "key" $s.githubApp.appIdKey) }}
{{ include "gh-job-audit.secretEnv" (dict "env" "GITHUB_APP_CLIENT_ID" "name" $s.githubApp.name "key" $s.githubApp.clientIdKey) }}
{{ include "gh-job-audit.secretEnv" (dict "env" "GITHUB_APP_CLIENT_SECRET" "name" $s.githubApp.name "key" $s.githubApp.clientSecretKey) }}
{{ include "gh-job-audit.secretEnv" (dict "env" "DATABASE_URL" "name" $s.database.name "key" $s.database.key) }}
{{ include "gh-job-audit.secretEnv" (dict "env" "SESSION_SECRET" "name" $s.session.name "key" $s.session.key) }}
{{- if eq $s.mail.provider "resend" }}
{{ include "gh-job-audit.secretEnv" (dict "env" "RESEND_API_KEY" "name" $s.mail.name "key" $s.mail.resendApiKeyKey) }}
{{- else if eq $s.mail.provider "smtp" }}
- { name: SMTP_HOST, value: {{ required "mail.smtp.host is required" .Values.mail.smtp.host | quote }} }
- { name: SMTP_PORT, value: {{ .Values.mail.smtp.port | quote }} }
- { name: SMTP_STARTTLS, value: {{ .Values.mail.smtp.starttls | quote }} }
{{ include "gh-job-audit.secretEnv" (dict "env" "SMTP_USERNAME" "name" $s.mail.name "key" $s.mail.smtpUsernameKey) }}
{{ include "gh-job-audit.secretEnv" (dict "env" "SMTP_PASSWORD" "name" $s.mail.name "key" $s.mail.smtpPasswordKey) }}
{{- else }}
{{- fail "existingSecrets.mail.provider must be resend or smtp" }}
{{- end }}
{{- if $s.githubToken.name }}
{{ include "gh-job-audit.secretEnv" (dict "env" "GITHUB_TOKEN" "name" $s.githubToken.name "key" $s.githubToken.key) }}
{{- end }}
{{- with .Values.extraEnv }}
{{ toYaml . }}
{{- end }}
{{- end -}}

{{- define "gh-job-audit.podBits" -}}
securityContext:
  {{- toYaml .Values.podSecurityContext | nindent 2 }}
{{- with .Values.nodeSelector }}
nodeSelector:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- with .Values.affinity }}
affinity:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- with .Values.tolerations }}
tolerations:
  {{- toYaml . | nindent 2 }}
{{- end }}
volumes:
  - name: gh-app
    secret:
      secretName: {{ .Values.existingSecrets.githubApp.name | required "existingSecrets.githubApp.name is required" }}
      items:
        - key: {{ .Values.existingSecrets.githubApp.privateKeyKey }}
          path: private-key
      defaultMode: 0440
  - name: tmp
    emptyDir: {}
{{- end -}}
