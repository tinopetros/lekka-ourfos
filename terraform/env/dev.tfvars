project_id = "ourfos-dev"
region     = "africa-south1"
api_region = "europe-west1"
api_domain = "test-ourfos.lekkacredit.com"
simulate   = true
notify_to = {
  requisition   = ["lekkai@lekkacredit.com"]
  vehicle_log   = ["lekkai@lekkacredit.com"]
  loan_approval = ["lekkai@lekkacredit.com"]
  write_off     = ["lekkai@lekkacredit.com"]
}
test_to = ["tpetros@lekkacredit.com"]
reply_to = {
  loan_approval = ["lekkai@lekkacredit.com"]
}
mifos = {
  base_url   = "https://13.214.217.53/fineract-provider/api/v1"
  tenant_id  = "demo"
  verify_ssl = false
}
ui_access = ["domain:lekkacredit.com"]
