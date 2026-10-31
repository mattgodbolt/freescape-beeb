#!/bin/sh
# Fetch the originals into originals/<version>/. Not committed: they are
# not ours to redistribute (decision 6). Downloads are untrusted data:
# nothing in originals/ is ever run, and Python reads them with -I.
#
# Each track adds the versions it needs as its own tools/fetch.d/*.sh,
# sourced here in order, with these helpers.
set -e
cd "$(dirname "$0")/.."
mkdir -p originals
SC=https://spectrumcomputing.co.uk
IA=https://archive.org/download
# get URL DEST
get() { mkdir -p "$(dirname "$2")"; [ -f "$2" ] || curl -sfL "$1" -o "$2"; }
# getzip URL MEMBER DEST: one file out of a downloaded zip.
getzip() {
    [ -f "$3" ] && return
    mkdir -p "$(dirname "$3")"
    tmp=$(mktemp -d)
    curl -sfL "$1" -o "$tmp/fetch.zip" && unzip -p "$tmp/fetch.zip" "$2" > "$3"
    rm -rf "$tmp"
}
for f in tools/fetch.d/*.sh; do
    . "$f"
done
