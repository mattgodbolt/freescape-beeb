#!/bin/sh
# Fetch the originals into originals/<version>/. Not committed: they are
# not ours to redistribute (decision 6). Each track adds the versions it
# needs. Downloads are untrusted data: nothing in originals/ is ever run.
set -e
cd "$(dirname "$0")/.."
mkdir -p originals
SC=https://spectrumcomputing.co.uk
get() { mkdir -p "$(dirname "$2")"; [ -f "$2" ] || curl -sfL "$1" -o "$2"; }
# getzip URL MEMBER DEST: one file out of a downloaded zip.
getzip() {
    [ -f "$3" ] && return
    mkdir -p "$(dirname "$3")"
    tmp=$(mktemp -d)
    curl -sfL "$1" -o "$tmp/fetch.zip" && unzip -p "$tmp/fetch.zip" "$2" > "$3"
    rm -rf "$tmp"
}

# ZX Spectrum, 48K retail tape (ZXDB entry 1521): the specification
# (decision 1).
getzip "$SC/pub/sinclair/games/d/Driller.tzx.zip" Driller.tzx originals/zx/Driller.tzx
