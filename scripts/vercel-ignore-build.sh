#!/bin/sh
# Vercel "Ignored Build Step": exit 0 skips the deployment, exit 1 builds.
# The Hobby plan caps deployments per day, and Dependabot previews plus
# pipeline-only merges were using up the whole budget.

case "$VERCEL_GIT_COMMIT_REF" in
  dependabot/*)
    echo "Skipping: Dependabot branch (App CI builds and e2e-tests it)"
    exit 0
    ;;
esac

# The app imports these two files from pipeline/, so changes to them still build.
APP_INPUTS="pipeline/accounts.json pipeline/data/account_activity.json"

# git diff exits 1 on changes and 128 on errors (e.g. a too-shallow clone);
# anything but a clean "no changes" falls through to a build.
if git diff --quiet HEAD^ HEAD -- . ':(exclude)pipeline' ':(exclude).github' &&
   git diff --quiet HEAD^ HEAD -- $APP_INPUTS; then
  echo "Skipping: only pipeline/ or .github/ changed"
  exit 0
fi

exit 1
