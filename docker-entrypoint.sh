#!/bin/sh
# Take ownership of the Fly volume, then drop to the service account.
#
# Fly mounts a fresh volume root-owned, and the app needs to write review.db
# and the published edits under it. Doing the chown here — rather than running
# the whole server as root — keeps uid 0 out of the request path.
set -e

if [ "$(id -u)" = "0" ]; then
    # A restored or resized volume can come back root-owned again, so this runs
    # every boot rather than once at build time. Recursive because the app
    # creates subdirectories (edits/, artifacts/) under the mount itself.
    if [ -d /data ]; then
        chown -R forage:forage /data
    fi
    exec gosu forage "$@"
fi

# Already unprivileged (e.g. `docker run --user`): nothing to hand off.
exec "$@"
