#!/usr/bin/env bash
# Shared USB routines. No automatic mounts, formatting, network or sudo.
usb_error() { printf '[edge-usb] %s\n' "$*" >&2; return 1; }
usb_root() {
  local p
  p="$(realpath -e -- "$1")" || return 1
  if [[ -f "$p/.edge-llm-usb-v1" ]]; then printf '%s\n' "$p"
  elif [[ -f "$p/edge-llm-usb/.edge-llm-usb-v1" ]]; then printf '%s\n' "$p/edge-llm-usb"
  else return 1; fi
}
usb_select() {
  local explicit="$1" required="$2" yes="$3" checkout="$4" p reply
  local -a found=()
  if [[ -n "$explicit" ]]; then
    usb_root "$explicit" || usb_error "Not a prepared USB: $explicit"
    return
  fi
  mapfile -t found < <(for p in "$checkout/.." /media/"$(id -un)"/* /run/media/"$(id -un)"/* /mnt/* /media/*; do
    [[ -d "$p" ]] && usb_root "$p" 2>/dev/null || :
  done | sort -u)
  if (( ${#found[@]} == 1 )); then
    p="${found[0]}"
    if (( required || yes )); then printf '%s\n' "$p"; return; fi
    if [[ -t 0 ]]; then
      read -r -p "Prepared USB found at $p. Use it? [Y/n] " reply
      [[ "$reply" =~ ^[Nn] ]] || printf '%s\n' "$p"
    else
      usb_error "Prepared USB detected; noninteractive use requires --offline or --usb (or explicit --online)."
      return 1
    fi
    return 0
  fi
  if (( ${#found[@]} > 1 )); then printf 'Prepared USB candidates:\n%s\n' "${found[@]}" >&2; fi
  if (( required || ${#found[@]} > 1 )); then
    [[ -t 0 && "$yes" == 0 ]] || { usb_error 'Specify --usb /mount/path (or --online for intentional online installation).'; return 1; }
    read -r -p 'Mounted USB directory: ' reply
    usb_root "$reply" || usb_error 'No valid prepared USB.'
  fi
  return 0
}
usb_platform() {
  local ID VERSION_ID key
  . /etc/os-release
  key="${ID}-${VERSION_ID:-unknown}-$(uname -m)"
  [[ "$key" =~ ^[a-zA-Z0-9._-]+$ ]] || return 1
  printf '%s\n' "$key"
}
usb_check() {
  local dir="$1" bin="$2" model="$3"
  [[ -f "$dir/$bin" && -f "$dir/$model" && -f "$dir/SHA256SUMS" ]] ||
    { usb_error "Incomplete bundle: $dir"; return 1; }
  awk -v bin="$bin" -v model="$model" 'length($1)!=64 || $1 !~ /^[[:xdigit:]]+$/ || NF!=2 {exit 1} $2==bin {b++} $2==model {m++} END {if(NR!=2 || b!=1 || m!=1) exit 1}' "$dir/SHA256SUMS" ||
    { usb_error 'Invalid checksum manifest'; return 1; }
  (cd "$dir" && sha256sum --strict -c SHA256SUMS >&2)
}
usb_publish() {
  local dir="$1" bin="$2" model="$3" bn="$4" mn="$5" tmp
  if [[ -d "$dir" ]]; then usb_check "$dir" "$bn" "$mn"; return; fi
  mkdir -p "$(dirname "$dir")"
  tmp="$(mktemp -d "$(dirname "$dir")/.partial.XXXXXXXX")"
  if ! (cp -- "$bin" "$tmp/$bn" && cp -- "$model" "$tmp/$mn" &&
    cd "$tmp" && sha256sum "$bn" "$mn" > SHA256SUMS && sha256sum -c SHA256SUMS >&2); then
    rm -rf -- "$tmp"; return 1
  fi
  mv -T -- "$tmp" "$dir"
}
usb_copy() {
  local src="$1" dest="$2" mode="$3" tmp
  mkdir -p "$(dirname "$dest")"
  if [[ -f "$dest" ]] && cmp -s -- "$src" "$dest"; then chmod "$mode" "$dest"; return; fi
  tmp="$(mktemp "$(dirname "$dest")/.edge-copy.XXXXXXXX")"
  if ! (cp -- "$src" "$tmp" && cmp -s -- "$src" "$tmp" && chmod "$mode" "$tmp" && mv -fT -- "$tmp" "$dest"); then
    rm -f -- "$tmp"; return 1
  fi
}
usb_runtime_check() {
  local result
  result="$(ldd "$1" 2>&1)" || { echo "$result" >&2; return 1; }
  if grep -q 'not found' <<<"$result"; then
    echo "$result" >&2; usb_error 'Runtime mismatch: use matching OS release and CPU.'; return 1
  fi
  "$1" "$2" >/dev/null 2>&1 || usb_error "Executable failed to start: $1"
}

# v2 portable kit: Debian Bookworm (glibc >=2.36), generic CPU executables.
# Never substitute a portable artifact for a missing v1 bundle unless v2 is complete.
usb_portable() {
  local root="$1" arch version
  [[ -f "$root/.portable-complete" ]] || return 1
  arch="$(uname -m)"
  [[ "$arch" == x86_64 || "$arch" == aarch64 ]] || return 1
  version="$(getconf GNU_LIBC_VERSION 2>/dev/null | awk '{print $2}')"
  [[ "$version" =~ ^[0-9]+\.[0-9]+$ ]] || { usb_error 'glibc required'; return 1; }
  [[ "$(printf '%s\n' 2.36 "$version" | sort -V | head -1)" == 2.36 ]] ||
    { usb_error "glibc $version too old; use 64-bit Debian 12+/Ubuntu 24.04+ baseline."; return 1; }
  printf '%s\n' "$root/portable/$arch"
}
