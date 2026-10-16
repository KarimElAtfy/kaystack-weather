variable "name" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "containers" {
  type = list(string)
}

variable "anonymous_read" {
  type        = bool
  default     = false
  description = "Anyone can read blobs, but cannot list containers."
}

variable "soft_delete_days" {
  type    = number
  default = 0
}

variable "cors_origins" {
  type    = list(string)
  default = []
}

variable "prevent_destroy" {
  type = bool
}

variable "tags" {
  type = map(string)
}
