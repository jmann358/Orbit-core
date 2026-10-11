# Priority 3: local conversation continuity

Luna already stores chats in SQLite. Priority 3 makes earlier messages discoverable and optionally useful to later model replies without treating raw conversation as approved long-term memory.

## Available behaviors

- **Existing chat persistence:** the SQLite `messages` table remains the source of truth. Closing a browser window does not delete it. Previously saved session IDs can be reopened in Chat.
- **Read-only local search:** the Memory tab can search older conversations by keywords. `GET /continuity/search?q=...&session=...` provides the same source-attributed search API. It does not call a model.
- **Bounded cross-session context:** when explicitly enabled, Luna retrieves up to five excerpts relevant to the new message (scanning at most 2,000 recent saved turns), excluding duplicates already in the current 30-message context. The prompt is capped and excerpts are labeled as historical, untrusted conversation data.
- **Separate cloud consent:** the Memory tab has independent controls for using earlier chats and allowing those excerpts to go to a configured cloud AI provider. Both default **OFF**. Local-only use of historical context does not silently enable cloud sharing. Disabling continuity also disables cloud history sharing.
- **Project-note preview:** the Memory tab can preview narrowly matched ORBIT/Luna project notes from explicit user messages in the current session. This is deterministic, not an AI-generated summary. Previews aren't saved. Choosing **Submit for memory review** creates a pending candidate, not an approved memory. The existing approval flow is still mandatory.
- **Provider portability:** conversation history, settings and approved memory records live in ORBIT's SQLite database, independent of any selected language model.

## Where to use it

Start ORBIT as before on localhost. In **Memory → Conversation continuity**, search past conversations, enable local continuity when desired, and optionally enable cloud context sharing only after reviewing the privacy notice. Search and previews do not require enabling model context.

The new routes are:

- `GET /continuity/settings`
- `POST /continuity/settings` body `{"enabled": true, "cloud_enabled": false}`
- `GET /continuity/search?session=default&q=project`
- `GET /continuity/project-notes?session=default`

The settings POST is intended for the existing **localhost-only** app. There is no new network listener, external synchronization, or new identity/authorization mechanism.

## Safety and privacy

History excerpts are **not approved facts**, cannot create permission grants, and aren't executable tasks. A quoted previous assistant response could be wrong; Luna should verify contradictory details rather than present retrieval as certainty. Old conversation text may also contain instructions that should be ignored as untrusted data; this labeling is a mitigation, not a complete prompt-injection defense.

Only explicit user turns with specific project-related openings are considered for project-note previews. Existing sensitive-content filters are reused. These filters are conservative but not comprehensive. **No assistant turn is converted into a memory suggestion, and no suggestion is automatically approved.**

The saved database is local plaintext SQLite. ORBIT does not encrypt it or back it up automatically. Before moving to the Mac mini, stop Luna, copy the SQLite database securely, and verify that the conversation list and approved memories still appear. Opening the browser on another device does not itself sync the database.

Do not expose the current FastAPI dashboard beyond `127.0.0.1`: authenticated mobile access has not been implemented. The API currently trusts users who can access the local server. Cloud continuity must remain off unless explicitly selected; a configured model provider still receives the current chat context according to the existing adapter.

## Known limits

- Search is lexical, not semantic. Rephrased concepts may not match.
- Retrieval scans at most the latest 2,000 saved turns, while records themselves remain persisted beyond that window.
- The UI shows source snippets, not a model-generated summary. Session-specific project-note previews only recognize narrowly phrased decisions.
- This adds no scheduled background memory processing, no automatic translation of old chats into permanent knowledge, no paid model calls, and no model-independent cross-device synchronization.
- The chat response window still uses recent messages plus bounded relevant excerpts rather than uploading an entire transcript to every model.

## Verification

Regression tests cover retrieval across persisted sessions, scope, limits, source attribution, pending-memory separation, owner opt-in settings, API routes, cloud-vs-local model prompt behavior, and review-only project-note previews. GitHub Actions performs the full trusted test suite on this branch. Actual device migration and interactive UI testing remain separate owner-side verification steps.
