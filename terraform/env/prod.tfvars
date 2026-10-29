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
