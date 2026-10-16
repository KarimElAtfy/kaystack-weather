# 3. Merge commits of locally rebased branches, signed commits required

Date: 2026-10-16

## Context

Commits on `main` are signed, so anyone can check they were made with my key and not just pushed with my account. GitHub's "Rebase and merge" recreates every commit on its side and can't sign them with my key, and "Squash and merge" throws the single commits away. A plain merge commit keeps my commits exactly as I pushed them.

## Decision

Every change reaches `main` through a pull request closed with a merge commit, and `main` accepts only signed commits, signed with my SSH key and carrying the noreply address. Squash and rebase merges are turned off, linear history is not required, and the branch is rebased locally with `git rebase -i --autosquash main` before the merge.

## Consequences

The signatures survive the merge, because GitHub keeps the branch commits as they are. The merge commit itself is signed by GitHub, not by my key. History also shows where each pull request starts and ends.

The "Update branch" button is turned off. It would add a commit made by GitHub to the branch, or rewrite the branch in its rebase mode. A branch is brought up to date by rebasing it locally and force-pushing it.
