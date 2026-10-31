{{- define "app-protect.enabled" -}}
{{- if or (not (hasKey . "protect")) .protect -}}true{{- end -}}
{{- end -}}

{{- define "app-protect.namespaces" -}}
{{- $ns := dict -}}
{{- range .Values.apps -}}
{{- if include "app-protect.enabled" . -}}{{- $_ := set $ns .namespace true -}}{{- end -}}
{{- end -}}
{{- keys $ns | sortAlpha | toJson -}}
{{- end -}}
