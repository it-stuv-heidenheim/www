#!/usr/bin/env bash
# Reports a Monitor job's findings in one open issue instead of a failed run (and an e-mail) every day:
# opens it on the first finding, comments only when the findings change, closes it when they are gone.
#
#   monitor_issue.sh <issue title> <findings file>   (an empty file means no findings)
#
# Needs GH_TOKEN with issues: write, and the GITHUB_* variables of a workflow run.
set -euo pipefail

title=$1
findings=$2
run="$GITHUB_SERVER_URL/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID"
label=monitor

number=$(gh issue list --label "$label" --state open --limit 100 --json number,title \
  --jq "map(select(.title == \"$title\"))[0].number // empty")

if [ ! -s "$findings" ]; then
  if [ -n "$number" ]; then
    gh issue close "$number" --comment "Resolved: the checks pass again ([run]($run))."
  fi
  echo "No findings."
  exit 0
fi

# The hash marks which findings the issue shows, so an unchanged finding notifies nobody again.
marker="<!-- monitor:$(sha256sum "$findings" | cut -c1-16) -->"
body="$RUNNER_TEMP/monitor-issue.md"
{
  echo "$marker"
  echo "Found by the Monitor workflow ([run]($run)). A comment follows when the findings change;"
  echo "the issue closes itself once the checks pass again. What to do: docs/testing.md, Überwachung."
  echo
  cat "$findings"
} > "$body"

if [ -z "$number" ]; then
  gh label create "$label" --color B60205 --description "Findings of the Monitor workflow" --force > /dev/null
  url=$(gh issue create --title "$title" --label "$label" --body-file "$body")
  echo "::warning::New findings: $url"
elif gh issue view "$number" --json body --jq .body | grep -qF -- "$marker"; then
  echo "::notice::Findings unchanged, still open in #$number."
else
  gh issue edit "$number" --body-file "$body" > /dev/null
  gh issue comment "$number" --body "The findings changed ([run]($run)); the description shows the current ones." > /dev/null
  echo "::warning::Findings changed in #$number."
fi
