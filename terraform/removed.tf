# Project roles moved to infra (modules/ourfos-app). Forget them, don't revoke
# them. Delete this once dev and prod have both applied it
removed {
  from = google_project_iam_member.services
  lifecycle { destroy = false }
}

removed {
  from = google_project_iam_member.trigger_starts_workflows
  lifecycle { destroy = false }
}

removed {
  from = google_project_iam_member.workflow_logs
  lifecycle { destroy = false }
}
