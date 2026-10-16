# One line per resource the plan touches, "actions  address", sorted. The PR
# comment, the reviewed plan and the plan apply-prod runs are all compared in
# this form.
[
  .resource_changes[]?
  | select(.change.actions != ["no-op"] and .change.actions != ["read"])
  | "\(.change.actions | join("/"))  \(.address)"
]
| sort[]
