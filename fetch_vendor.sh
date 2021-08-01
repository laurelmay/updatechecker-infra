#!/usr/bin/env bash

mkdir -p runtime/vendor
rm -rf runtime/vendor/updatechecker
temp_dir="$(mktemp -d)"
git clone https://github.com/kylelaker/updatechecker "$temp_dir"
cp -r "$temp_dir/updatechecker" "runtime/vendor"
rm -rf "$temp_dir"