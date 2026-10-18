# ═══════════════════════════════════════════════════════════════════════════
# Terraform — AWS Provider
# Credentials are read from the standard AWS credential chain:
#   1. Environment variables  AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
#   2. Shared credentials file  ~/.aws/credentials  (profile = var.aws_profile)
#   3. Instance / container metadata
#
# Do NOT hardcode access keys here.
# ═══════════════════════════════════════════════════════════════════════════

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile != "" ? var.aws_profile : null
}
