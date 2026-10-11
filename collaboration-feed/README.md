# Collaboration Feed

This folder is the owner-visible activity feed for ORBIT development.

It records safe, high-level coordination events between ChatGPT, Luna, and verification systems. It is intentionally **not** a transcript of private model reasoning and must never contain secrets, credentials, sensitive payloads, hidden watchdog data, or owner-vault contents.

## Event format

Each event should contain only:
- UTC timestamp
- actor: `chatgpt`, `luna`, `ci`, or `system`
- action: a short allowlisted development action
- status: `started`, `completed`, `blocked`, `waiting`, or `verified`
- task_id: an opaque task identifier
- summary: a short non-sensitive description

The feed is informational only. Entries cannot authorize code execution, merges, permission expansion, spending, or access to protected information.

## Current state

Luna now has a verified isolated test runner, approval-gated conversation continuity, a privacy-safe live activity timeline and terminal watcher, validated local SQLite backups, and a read-only readiness doctor. The owner-visible feed records these milestones without including private payloads.

Automatic model drafting is intentionally pinned. Live code application, merges, spending, credential access, external exposure, destructive restore, and security-boundary expansion remain approval-gated or disabled.
