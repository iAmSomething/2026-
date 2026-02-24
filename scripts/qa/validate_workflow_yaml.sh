#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

echo "[workflow-yaml] validating .github/workflows/*.yml(yaml)"
ruby <<'RUBY'
require "yaml"

files = Dir.glob(".github/workflows/*.{yml,yaml}").sort
if files.empty?
  warn "[workflow-yaml] no workflow files found"
  exit 1
end

files.each do |path|
  begin
    YAML.load_file(path)
    puts "[workflow-yaml] ok: #{path}"
  rescue Psych::SyntaxError => e
    warn "[workflow-yaml] fail: #{path}"
    warn e.message
    exit 1
  end
end
RUBY

echo "[workflow-yaml] all workflow files parsed successfully"
