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
  # docs/phase10/adr.md 6
  write_off = ["lekkai@lekkacredit.com", "directors@lekkacredit.com"]
}
reply_to = {
  loan_approval = ["directors@lekkacredit.com", "lekkai@lekkacredit.com"]
}
