'use strict';

/**
 * Provenance chain for eclusa pipeline.
 *
 * Each commit carries hashes linking to pipeline stage outputs:
 * sources_hash, constraints_hash, test_suite_hash.
 *
 * Storage: git trailers (default) or file-based.
 * Verification: walk the chain and check all hashes match.
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execSync } = require('child_process');

// ─── Hash Computation ───────────────────────────────────────────────────────

/**
 * Compute SHA-256 hash of a file's content.
 */
function hashFile(filePath) {
  if (!fs.existsSync(filePath)) return null;
  const content = fs.readFileSync(filePath);
  return crypto.createHash('sha256').update(content).digest('hex').slice(0, 16);
}

/**
 * Compute SHA-256 hash of a directory's contents (sorted, recursive).
 */
function hashDirectory(dirPath) {
  if (!fs.existsSync(dirPath)) return null;
  const hash = crypto.createHash('sha256');
  const files = getFilesRecursive(dirPath).sort();
  for (const file of files) {
    hash.update(file); // Include path for structure
    hash.update(fs.readFileSync(path.join(dirPath, file)));
  }
  return hash.digest('hex').slice(0, 16);
}

function getFilesRecursive(dir, base = '') {
  const files = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const rel = path.join(base, entry.name);
    if (entry.isDirectory()) {
      files.push(...getFilesRecursive(path.join(dir, entry.name), rel));
    } else {
      files.push(rel);
    }
  }
  return files;
}

// ─── Provenance Record ──────────────────────────────────────────────────────

/**
 * Compute the current provenance hashes for a project.
 */
function computeProvenance(cwd) {
  const projectFile = path.join(cwd, 'project.eclusa');
  const constraintsDir = path.join(cwd, 'constraints');
  const testDir = path.join(cwd, 'tests'); // Or wherever derived tests live

  return {
    project_hash: hashFile(projectFile),
    sources_hash: computeSourcesHash(cwd),
    constraints_hash: hashDirectory(constraintsDir),
    test_suite_hash: hashDirectory(testDir),
    computed_at: new Date().toISOString(),
  };
}

/**
 * Compute a hash of the matched sources section from project.eclusa.
 */
function computeSourcesHash(cwd) {
  const projectFile = path.join(cwd, 'project.eclusa');
  if (!fs.existsSync(projectFile)) return null;
  const content = fs.readFileSync(projectFile, 'utf-8');
  // Hash just the sources section
  const sourcesMatch = content.match(/sources:[\s\S]*?(?=\n\w|\n$|$)/);
  if (!sourcesMatch) return null;
  return crypto.createHash('sha256').update(sourcesMatch[0]).digest('hex').slice(0, 16);
}

// ─── Git Trailers ───────────────────────────────────────────────────────────

/**
 * Format provenance as git trailers.
 * These go at the end of a commit message.
 */
function formatTrailers(provenance) {
  const lines = [];
  if (provenance.sources_hash) {
    lines.push(`Eclusa-Sources-Hash: ${provenance.sources_hash}`);
  }
  if (provenance.constraints_hash) {
    lines.push(`Eclusa-Constraints-Hash: ${provenance.constraints_hash}`);
  }
  if (provenance.test_suite_hash) {
    lines.push(`Eclusa-Test-Suite-Hash: ${provenance.test_suite_hash}`);
  }
  if (provenance.project_hash) {
    lines.push(`Eclusa-Project-Hash: ${provenance.project_hash}`);
  }
  return lines.join('\n');
}

/**
 * Extract provenance trailers from a commit message.
 */
function parseTrailers(commitMessage) {
  const provenance = {};
  const trailerRegex = /^Eclusa-(\w[\w-]*)-Hash:\s*([a-f0-9]+)$/gm;
  let match;
  while ((match = trailerRegex.exec(commitMessage)) !== null) {
    const key = match[1].toLowerCase().replace(/-/g, '_') + '_hash';
    provenance[key] = match[2];
  }
  return provenance;
}

// ─── Verification ───────────────────────────────────────────────────────────

/**
 * Verify the provenance chain.
 * Walk recent commits and check that hashes match current state.
 */
function verifyProvenance(cwd) {
  const current = computeProvenance(cwd);
  const issues = [];

  // Get the most recent commit with provenance trailers
  let lastTrailers;
  try {
    const log = execSync('git log --format="%B" -n 20', {
      cwd,
      encoding: 'utf-8',
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    const commits = log.split('\n\n\n').filter(Boolean);
    for (const msg of commits) {
      const trailers = parseTrailers(msg);
      if (Object.keys(trailers).length > 0) {
        lastTrailers = trailers;
        break;
      }
    }
  } catch {
    return {
      verified: false,
      issues: [{ type: 'error', message: 'Cannot read git log. Not a git repository?' }],
      current,
    };
  }

  if (!lastTrailers) {
    return {
      verified: true,
      issues: [{ type: 'info', message: 'No provenance trailers found in recent commits. Chain not yet started.' }],
      current,
    };
  }

  // Compare hashes
  for (const [key, hash] of Object.entries(lastTrailers)) {
    if (current[key] && current[key] !== hash) {
      issues.push({
        type: 'warning',
        message: `${key} has changed since last provenance commit: ${hash} → ${current[key]}`,
      });
    }
  }

  return {
    verified: issues.filter(i => i.type === 'error').length === 0,
    issues,
    current,
    last_committed: lastTrailers,
  };
}

// ─── Diagnose ───────────────────────────────────────────────────────────────

/**
 * Full diagnostic: validation, provenance, decisions, enforcement.
 */
function diagnose(cwd) {
  const results = {
    provenance: verifyProvenance(cwd),
    project_file: { exists: fs.existsSync(path.join(cwd, 'project.eclusa')) },
    constraints: { exists: fs.existsSync(path.join(cwd, 'constraints', 'Constraints.hs')) },
    pipeline_state: { exists: fs.existsSync(path.join(cwd, '.eclusa', 'PIPELINE.md')) },
  };

  // Check for pending decisions
  const pipelinePath = path.join(cwd, '.eclusa', 'PIPELINE.md');
  if (fs.existsSync(pipelinePath)) {
    const content = fs.readFileSync(pipelinePath, 'utf-8');
    const pendingStages = (content.match(/○/g) || []).length;
    const inProgressStages = (content.match(/→/g) || []).length;
    results.pipeline_state.pending = pendingStages;
    results.pipeline_state.in_progress = inProgressStages;
  }

  return results;
}

// ─── CLI Commands ───────────────────────────────────────────────────────────

function cmdProvenance(cwd) {
  const result = verifyProvenance(cwd);
  process.stdout.write(JSON.stringify(result));
}

function cmdProvenanceCompute(cwd) {
  const provenance = computeProvenance(cwd);
  process.stdout.write(JSON.stringify(provenance));
}

function cmdProvenanceTrailers(cwd) {
  const provenance = computeProvenance(cwd);
  process.stdout.write(formatTrailers(provenance));
}

function cmdDiagnose(cwd) {
  const result = diagnose(cwd);
  process.stdout.write(JSON.stringify(result));
}

module.exports = {
  hashFile,
  hashDirectory,
  computeProvenance,
  computeSourcesHash,
  formatTrailers,
  parseTrailers,
  verifyProvenance,
  diagnose,
  cmdProvenance,
  cmdProvenanceCompute,
  cmdProvenanceTrailers,
  cmdDiagnose,
};
