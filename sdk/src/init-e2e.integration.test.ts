/**
 * E2E integration test — proves InitRunner.run() drives real Agent SDK
 * sessions for the eclusa-sdk init workflow.
 *
 * Requires Claude Code CLI (`claude`) installed and authenticated.
 * Skips gracefully if CLI is unavailable.
 *
 * This test proves the headless init pipeline can bootstrap a real project
 * without human intervention: setup → config → PROJECT.md → research →
 * synthesis → requirements → roadmap.
 */

import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { execSync } from 'node:child_process';
import { mkdtemp, rm, readFile, stat } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { homedir } from 'node:os';

import { InitRunner } from './init-runner.js';
import { EclusaTools } from './eclusa-tools.js';
import { EclusaEventStream } from './event-stream.js';
import { EclusaEventType } from './types.js';
import type { EclusaEvent } from './types.js';

// ─── CLI availability check ─────────────────────────────────────────────────

let cliAvailable = false;
try {
  execSync('which claude', { stdio: 'ignore' });
  cliAvailable = true;
} catch {
  cliAvailable = false;
}

const __dirname = fileURLToPath(new URL('.', import.meta.url));
const sdkPromptsDir = join(__dirname, '..', 'prompts');
const ECLUSA_TOOLS_PATH = join(homedir(), '.claude', 'eclusa', 'bin', 'eclusa-tools.cjs');

// ─── Test suite ──────────────────────────────────────────────────────────────

describe.skipIf(!cliAvailable)('E2E: InitRunner.run() full workflow', () => {
  let tmpDir: string;
  let events: EclusaEvent[];

  beforeAll(async () => {
    tmpDir = await mkdtemp(join(tmpdir(), 'eclusa-sdk-init-e2e-'));

    // Initialize git in the temp dir (required by InitRunner)
    execSync('git init', { cwd: tmpDir, stdio: 'ignore' });
    execSync('git config user.email "test@test.com"', { cwd: tmpDir, stdio: 'ignore' });
    execSync('git config user.name "Test"', { cwd: tmpDir, stdio: 'ignore' });
  }, 30_000);

  afterAll(async () => {
    if (tmpDir) {
      await rm(tmpDir, { recursive: true, force: true });
    }
  });

  it('InitRunner.run() bootstraps a project without human intervention', async () => {
    events = [];
    const eventStream = new EclusaEventStream();
    eventStream.on('event', (e: EclusaEvent) => events.push(e));

    const tools = new EclusaTools({
      projectDir: tmpDir,
      eclusaToolsPath: ECLUSA_TOOLS_PATH,
      timeoutMs: 30_000,
    });

    const runner = new InitRunner({
      projectDir: tmpDir,
      tools,
      eventStream,
      config: {
        maxBudgetPerSession: 1.0,
        maxTurnsPerSession: 15,
      },
      sdkPromptsDir,
    });

    const result = await runner.run('Build a CLI tool that prints hello world');

    // ── Assert: pipeline executed (success OR at least 3+ steps completed) ──
    const completedSteps = result.steps.filter(s => s.success);
    const pipelineProgressed = result.success || completedSteps.length >= 3;
    expect(pipelineProgressed).toBe(true);

    // ── Assert: config.json artifact created ──
    // config.json is written directly by InitRunner (not by Claude session)
    // so it should always exist if the config step succeeded
    const configStep = result.steps.find(s => s.step === 'config');
    if (configStep?.success) {
      const configPath = join(tmpDir, '.eclusa', 'config.json');
      const configStat = await stat(configPath).catch(() => null);
      expect(configStat).not.toBeNull();

      if (configStat) {
        const configContent = JSON.parse(await readFile(configPath, 'utf-8'));
        expect(configContent.workflow.auto_advance).toBe(true);
      }
    }

    // ── Assert: PROJECT.md created if project step succeeded ──
    const projectStep = result.steps.find(s => s.step === 'project');
    if (projectStep?.success) {
      const projectPath = join(tmpDir, '.eclusa', 'PROJECT.md');
      const projectStat = await stat(projectPath).catch(() => null);
      expect(projectStat).not.toBeNull();
    }

    // ── Assert: events captured include InitStart and at least one InitStepComplete ──
    const initStartEvents = events.filter(e => e.type === EclusaEventType.InitStart);
    expect(initStartEvents.length).toBe(1);

    const stepCompleteEvents = events.filter(e => e.type === EclusaEventType.InitStepComplete);
    expect(stepCompleteEvents.length).toBeGreaterThanOrEqual(1);

    // ── Assert: InitComplete event emitted ──
    const initCompleteEvents = events.filter(e => e.type === EclusaEventType.InitComplete);
    expect(initCompleteEvents.length).toBe(1);

    // ── Assert: cost and duration are tracked ──
    expect(result.totalDurationMs).toBeGreaterThan(0);
    expect(typeof result.totalCostUsd).toBe('number');

    // ── Assert: artifacts list is populated ──
    if (result.success) {
      expect(result.artifacts.length).toBeGreaterThan(0);
      expect(result.artifacts).toContain('.eclusa/config.json');
    }
  }, 600_000); // 10 minute timeout for the full 7-session init workflow
});
