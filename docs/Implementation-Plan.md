# Plan

Prepare MacroFactor Workout Bridge for safe public collaboration by auditing every published branch, hardening repository files and CI, and matching the proven GitHub security settings used by macOS Widgets. Publish only after the local verification gate and remote-history checks pass.

## Scope
- In: `main` branch setup, remote-history and fixture privacy checks, public-facing README and community policies, defensive ignore rules, pinned least-privilege CI, GitHub visibility and security settings, branch rules, local verification, commit, and push.
- Out: merging unrelated feature branches, rewriting clean GitHub history, distributing signed binaries, changing application behavior, and deleting existing branches or user data.

## Action items
[x] Confirm all GitHub-reachable commits and anonymized fixtures contain no credentials, personal paths, private workout files, repository secrets, deploy keys, webhooks, or unexpected collaborators.
[x] Expand `.gitignore` for credentials, environment files, local workspaces, editor state, logs, and generated distribution artifacts while preserving anonymized fixtures.
[x] Add the MIT license, private vulnerability-reporting policy, contribution guide, Contributor Covenant, and focused issue and pull-request templates.
[x] Rework `README.md` for a public audience with project status, engineering and privacy highlights, architecture, safe local setup, verification, contribution, security-reporting, and licensing guidance.
[x] Add `.github/workflows/ci-verify.yml` with read-only permissions, immutable official-action pins, bounded runtime, pull-request concurrency cancellation, and the complete offscreen test and compile gate.
[x] Run the full unit/integration suite, compile checks, workflow and documentation consistency checks, fixture/privacy scans, `git diff --check`, and a second GitHub-reachable history scan; no application tests need changes because executable behavior is unchanged.
[ ] Commit and push the publication files on `main` with the repository-local Git identity set to the verified GitHub noreply address.
[ ] Set GitHub's default branch to `main`, make the repository public, enable private vulnerability reporting, Dependabot alerts and security updates, secret scanning and push protection, restrict Actions to SHA-pinned GitHub-owned actions with read-only workflow permissions, and apply the macOS Widgets protected-main ruleset.
[ ] Verify the public repository metadata, security settings, required `CI Verify` status, ruleset, remote commit, and clean local worktree after publication.

## Open questions
- None. Existing feature branches remain intact and public; the audit confirms their GitHub-reachable histories exclude the private manifests found only in local Codex checkpoint refs.
