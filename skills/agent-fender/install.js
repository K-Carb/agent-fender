#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

const SKILL_NAME = "agent-fender";
const HOME = process.env.HOME || process.env.USERPROFILE;
const TARGET_DIR = path.join(HOME, ".claude", "skills", SKILL_NAME);

const files = [
  "SKILL.md",
  "references/audit-examples.md",
  "references/inline-patterns.md",
  "references/library-integration.md",
];

// Skip postinstall for non-global installs. npx (bin) always runs.
if (process.env.npm_lifecycle_event === "postinstall" && process.env.npm_config_global !== "true") {
  process.exit(0);
}

if (!HOME) {
  console.error("Cannot determine home directory. Set HOME or USERPROFILE.");
  process.exit(1);
}

fs.mkdirSync(TARGET_DIR, { recursive: true });

let installed = 0;
for (const file of files) {
  const src = path.join(__dirname, file);
  const dest = path.join(TARGET_DIR, file);

  if (!fs.existsSync(src)) {
    console.warn(`  SKIP: ${file} (not found)`);
    continue;
  }

  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.copyFileSync(src, dest);
  installed++;
}

console.log(
  `\nagent-fender skill installed to ${TARGET_DIR} (${installed}/${files.length} files)\n`
);
console.log(
  "Run Claude Code and say: \"audit my agent code for safety gaps\"\n"
);
