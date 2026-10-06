project_id = "ourfos-prod"
region     = "africa-south1"
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
test_to = ["tpetros@lekkacredit.com"]
reply_to = {
  loan_approval = ["lekkai@lekkacredit.com", "directors@lekkacredit.com"]
}
mifos = {
  base_url   = "https://13.214.217.53/fineract-provider/api/v1"
  tenant_id  = "default"
  verify_ssl = false
}
