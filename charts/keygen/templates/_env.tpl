{{/*
Shared container env for the web Deployment, worker Deployment, and
migration Job. DATABASE_URL/REDIS_URL are single connection-string env vars
(Keygen's Rails config only reads the URL form, not discrete host/port/user
vars), so the password pieces are passed in separately and assembled by
"keygen.entrypointCommand" at container startup.
*/}}
{{- define "keygen.env" -}}
- name: RAILS_ENV
  value: {{ .Values.keygen.railsEnv | quote }}
- name: RAILS_LOG_LEVEL
  value: {{ .Values.keygen.railsLogLevel | quote }}
- name: PORT
  value: {{ .Values.keygen.port | quote }}
- name: BIND
  value: "0.0.0.0"
- name: KEYGEN_HOST
  value: {{ .Values.keygen.host | quote }}
{{- with .Values.keygen.hosts }}
- name: KEYGEN_HOSTS
  value: {{ . | quote }}
{{- end }}
- name: KEYGEN_EDITION
  value: {{ .Values.keygen.edition | quote }}
- name: KEYGEN_MODE
  value: {{ .Values.keygen.mode | quote }}
- name: SECRET_KEY_BASE
  valueFrom:
    secretKeyRef:
      name: {{ include "keygen.secretsName" . }}
      key: SECRET_KEY_BASE
- name: ENCRYPTION_DETERMINISTIC_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "keygen.secretsName" . }}
      key: ENCRYPTION_DETERMINISTIC_KEY
- name: ENCRYPTION_PRIMARY_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "keygen.secretsName" . }}
      key: ENCRYPTION_PRIMARY_KEY
- name: ENCRYPTION_KEY_DERIVATION_SALT
  valueFrom:
    secretKeyRef:
      name: {{ include "keygen.secretsName" . }}
      key: ENCRYPTION_KEY_DERIVATION_SALT
- name: KEYGEN_ACCOUNT_ID
  valueFrom:
    secretKeyRef:
      name: {{ include "keygen.secretsName" . }}
      key: KEYGEN_ACCOUNT_ID
- name: DB_HOST
  value: {{ include "keygen.postgresHost" . }}
- name: DB_PORT
  value: "5432"
- name: DB_NAME
  value: {{ .Values.postgres.postgresql.db | quote }}
- name: DB_USER
  value: {{ .Values.postgres.postgresql.user | quote }}
- name: DB_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ .Values.postgres.secrets.password.name }}
      key: {{ .Values.postgres.secrets.password.key }}
- name: REDIS_HOST
  value: {{ include "keygen.redisHost" . }}
- name: REDIS_PORT
  value: "6379"
{{- if .Values.redis.auth.enabled }}
- name: REDIS_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ .Values.redis.auth.existingSecret }}
      key: {{ .Values.redis.auth.existingSecretKey }}
{{- end }}
{{- end }}

{{/*
Wraps the image's fixed entrypoint (/app/scripts/entrypoint.sh) so that
DATABASE_URL and REDIS_URL -- the only connection forms Keygen reads -- get
assembled from the discrete DB_ and REDIS_ env vars above before handing off
to the given process type ("web", "worker", or "release").
*/}}
{{- define "keygen.entrypointCommand" -}}
command:
  - sh
  - -c
  - |
    set -e
    export DATABASE_URL="postgres://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
    export REDIS_URL="redis://{{ if .root.Values.redis.auth.enabled }}:${REDIS_PASSWORD}@{{ end }}${REDIS_HOST}:${REDIS_PORT}"
    exec /app/scripts/entrypoint.sh {{ .process }}
{{- end }}
