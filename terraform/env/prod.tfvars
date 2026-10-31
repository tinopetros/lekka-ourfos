project_id = "ourfos-prod"
region     = "africa-south1"
api_region = "europe-west1"
api_domain = "ourfos.lekkacredit.tech"
notify_to = {
  requisition = [
    "lekkai@lekkacredit.com",
    "directors@lekkacredit.com",
    "consultant-zsaruchera@lekkacredit.com",
  ]
  vehicle_log   = ["lekkai@lekkacredit.com", "directors@lekkacredit.com"]
  loan_approval = ["lekkai@lekkacredit.com", "directors@lekkacredit.com"]
  write_off     = ["lekkai@lekkacredit.com", "directors@lekkacredit.com"]
}
reply_to = {
  loan_approval = ["lekkai@lekkacredit.com", "directors@lekkacredit.com"]
}
mifos = {
  base_url   = "https://13.214.217.53/fineract-provider/api/v1"
  tenant_id  = "default"
  verify_ssl = false
}
ui_access = ["domain:lekkacredit.com"]
# After Mifos's own midnight jobs in Harare, and its SMS jobs at 5:00 there
mifos_syncs = {
  clients = { schedule = "30 22 * * *" }
  loans   = { schedule = "45 22 * * *" }
  # This month, and last month too in a month's first week
  manual_journal_entries = { schedule = "0 23 * * *" }
}
