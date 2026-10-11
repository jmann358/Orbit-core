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

Luna autonomous code application remains disabled. ChatGPT is currently advancing the sprint while GitHub Actions independently verifies checkpoints. The current autonomy milestone includes bounded task selection, reviewable structured candidates, and isolated validation. Automatic model drafting, live code application, merges, spending, and security-boundary expansion remain approval-gated.
