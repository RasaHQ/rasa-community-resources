#!/usr/bin/env bash
# UPSTREAM-SHA: 106f0c70be1d9f8a0dac3d1383715bc309fbdd49a40a388e5ca51e5ee32869c6
# PreToolUse hook: deny `git push`, `git merge`, and `git rebase` only when
# (a) the command targets a git repo that is THIS repo (not some other repo
# the session's command happens to `cd`/`-C` into) and (b) the act would land
# on, or is performed while checked out on, the trunk branch there.
#
# WHY A HOOK AND NOT A PERMISSION GLOB: a glob string-matches the INVOCATION
# ("git push origin main"); this asks git the same question git itself would
# ask before acting - what repo, what branch - rather than pattern-matching
# the command text. A glob can be spelled around by rewording the command;
# this cannot, because it does not care how the command is spelled, only
# what it would actually do.
#
# WHY MERGE/REBASE ARE HERE TOO, NOT JUST PUSH: a blanket permission deny on
# `git merge:*`/`git rebase:*` blocks a stream from merging or rebasing its
# OWN branches, which is normal daily work, not the risk worth denying. The
# risk an outright deny is actually guarding against is narrower than "any
# merge or rebase": `git merge <branch>` while checked out on TRUNK mutates
# trunk's local HEAD directly, no push required for the damage to land
# locally, and even with push separately gated a polluted local trunk
# checkout is wrong for whoever looks at it next. `git rebase` while checked
# out on trunk rewrites trunk's own history locally, same shape. Neither risk
# depends on the branch being MERGED FROM/rebased FROM being someone else's;
# it depends entirely on what's currently checked out. So: gate on "am I on
# trunk right now", not on the command's other arguments - own-branch
# merge/rebase (including merging one feature branch into another) is
# unrestricted.
#
# git reset --hard and rm -rf are DELIBERATELY NOT HERE - those are
# data-loss risks on ANY branch, not a trunk-vs-own-branch question, and
# stay as ordinary permission denies in settings.json rather than becoming
# part of this hook's scope.
#
# Reads the tool_input JSON from stdin (piped by the PreToolUse hook wiring).

set -euo pipefail

TRUNK_BRANCH="${TRUNK_BRANCH:-main}"
# The repo this hook is deployed to. Resolved from THIS SCRIPT's own location
# (.claude/hooks/check-trunk-guard.sh lives at <repo>/.claude/hooks/...), not
# from the session's launch cwd - the two are not the same thing. A
# session-scoped guard fires on pushes into unrelated repos the session had
# `cd`'d into, which is wrong: this hook has no standing to deny an act in a
# repo it is not deployed to.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OWN_REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || true)"

cmd="$(jq -r '.tool_input.command // empty')"
[ -z "$cmd" ] && exit 0

deny() {
  local reason="$1"
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":%s}}\n' \
    "$(printf '%s' "$reason" | jq -Rs .)"
  exit 0
}

# ── RESOLVE THE REAL TARGET DIRECTORY FOR A GIVEN GIT SUBCOMMAND, NOT THE
#    SESSION'S LAUNCH CWD ────────────────────────────────────────────────────
# The command text may redirect where the act actually runs, three ways:
#   cd <path> && ... git <subcmd> ...
#   cd <path>; ... git <subcmd> ...
#   git -C <path> <subcmd> ...
# Take the LAST such redirect before the final occurrence of <subcmd> - a
# chain can `cd` multiple times, only the one immediately governing the act
# matters. If none is present, the act runs wherever this hook process
# itself runs, which for a PreToolUse hook is the session's own working
# directory - safe to read directly.
resolve_target_dir() {
  local subcmd="$1"
  local dir=""
  if echo "$cmd" | grep -qE "(^|[;&|]|\s)git\s+-C\s+\S+\s+${subcmd}(\s|\$)"; then
    dir="$(echo "$cmd" | grep -oE "git\s+-C\s+\S+\s+${subcmd}" | sed -E "s/^git[[:space:]]+-C[[:space:]]+//; s/[[:space:]]+${subcmd}\$//")"
  else
    local before_act last_cd
    before_act="$(echo "$cmd" | sed -E "s/(.*)git[[:space:]]+${subcmd}.*/\1/")"
    last_cd="$(echo "$before_act" | grep -oE 'cd[[:space:]]+[^;&|]+' | tail -1 || true)"
    if [ -n "$last_cd" ]; then
      dir="$(echo "$last_cd" | sed -E 's/^cd[[:space:]]+//' | sed -E "s/^['\"]//; s/['\"]?[[:space:]]*\$//")"
    fi
  fi
  if [ -n "$dir" ]; then
    dir="${dir/#\~/$HOME}"
  fi
  printf '%s' "$dir"
}

# Returns 0 (true) iff the resolved target directory's repo root is THIS
# hook's own repo. Anything else - a different repo, or an unresolvable
# target - means this hook has no standing to deny the act; get out of the
# way rather than guess.
targets_own_repo() {
  local target_dir="$1" resolved_target_root=""
  if [ -n "$target_dir" ]; then
    resolved_target_root="$(git -C "$target_dir" rev-parse --show-toplevel 2>/dev/null || true)"
  else
    resolved_target_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  fi
  [ -n "$OWN_REPO_ROOT" ] && [ -n "$resolved_target_root" ] && [ "$resolved_target_root" = "$OWN_REPO_ROOT" ]
}

current_branch_of() {
  local target_dir="$1"
  if [ -n "$target_dir" ]; then
    git -C "$target_dir" rev-parse --abbrev-ref HEAD 2>/dev/null || true
  else
    git rev-parse --abbrev-ref HEAD 2>/dev/null || true
  fi
}

# ══════════════════════════════════════════════════════════════════════════
# PUSH
# ══════════════════════════════════════════════════════════════════════════
if echo "$cmd" | grep -qE '(^|[;&|]|\s)git\s+(-C\s+\S+\s+)?push(\s|$)'; then
  target_dir="$(resolve_target_dir push)"
  if targets_own_repo "$target_dir"; then
    if echo "$cmd" | grep -qE '(^|[;&|]|\s)git\s+push\b.*(-f\b|--force\b)'; then
      deny "git push --force / -f is blocked in this repo: force-push rewrites history other seats or the operator may already have pulled. If a rewrite is genuinely needed, that is the operator's act."
    fi

    # Explicit destination: git push <remote> <refspec>, HEAD:<branch>, or
    # <local>:<remote-branch>. A refspec's REMOTE-side name is what lands
    # where - the part after a colon, or the bare name if there is none.
    rest="$(echo "$cmd" | sed -E 's/^.*[[:space:]]push[[:space:]]*//')"
    read -r -a words <<< "$rest"
    remote="" refspec="" explicit_dest=""
    for w in "${words[@]+"${words[@]}"}"; do
      case "$w" in
        -*) continue ;;
        *)
          if [ -z "$remote" ]; then remote="$w"; else refspec="$w"; break; fi
          ;;
      esac
    done
    if [ -n "$refspec" ]; then
      if [[ "$refspec" == *:* ]]; then explicit_dest="${refspec##*:}"; else explicit_dest="$refspec"; fi
    fi

    # TRUNK PUSH IS ALLOWED, GATED BY THE PROJECT'S OWN GATE RATHER THAN BY A
    # HUMAN: seats manage the merging of their own branches; that is what
    # pre-commit and pre-push hooks, linters, and tests are for.
    #
    # A guard that denies every trunk push outright forces every landing onto
    # a human even after independent gates have already vouched for it -
    # backwards. If a pre-push gate exists in this repo (`zeo equip --gates`
    # installs one when the stack's own checks are green), a trunk push that
    # survives it is by construction green. The authority to land is the
    # gate, not this guard.
    #
    # What is still denied here is the IRREVERSIBLE class, which no test
    # suite can vouch for: force-push (above) and branch DELETION (below).
    # Those destroy history others may hold; a green fast-forward does not.
    if [ -n "$explicit_dest" ]; then
      # `git push origin :branch` / `--delete branch` removes a remote ref.
      # Denied on any destination: archive-and-keep is the doctrine, and a
      # deleted remote branch is not recoverable by the seat that deleted it.
      if echo "$cmd" | grep -qE '(^|[;&|]|\s)git\s+push\b.*(--delete\b|[[:space:]]:[A-Za-z0-9._/-]+)'; then
        deny "git push --delete / :refspec (remote branch deletion) is blocked in this repo. Deletion is irreversible for the seat doing it and other seats may hold the ref. Doctrine is archive-before-delete: tag it (e.g. archive/integrated/<name>), push the tag, and leave the deletion to the operator."
      fi
    fi
  fi
fi

# ══════════════════════════════════════════════════════════════════════════
# MERGE / REBASE - gated on CURRENT BRANCH ONLY, not on what's being merged
# from. Both mutate the checked-out branch's local HEAD directly; the risk
# is "trunk gets rewritten locally without review", which is fully
# determined by what's checked out, never by the other ref named.
# ══════════════════════════════════════════════════════════════════════════
for subcmd in merge rebase; do
  if echo "$cmd" | grep -qE "(^|[;&|]|\s)git\s+(-C\s+\S+\s+)?${subcmd}(\s|\$)"; then
    # --abort / --continue / --skip / --quit UNDO or resolve an ALREADY-
    # in-progress merge/rebase; they never land new history, they recover
    # from a stuck one. Denying these would trap a seat mid-merge/rebase with
    # no way out - strictly worse than allowing them.
    if echo "$cmd" | grep -qE "git\s+(-C\s+\S+\s+)?${subcmd}\b.*--(abort|continue|skip|quit)\b"; then
      continue
    fi
    target_dir="$(resolve_target_dir "$subcmd")"
    if targets_own_repo "$target_dir"; then
      current_branch="$(current_branch_of "$target_dir")"
      # A `git checkout <branch>` EARLIER IN THE SAME COMMAND moves off trunk
      # before the merge/rebase runs, so the branch git will actually be on
      # is that one, not what HEAD says right now. Without this, the standard
      # own-branch update - `git checkout feat/mine && git rebase origin/main`
      # - is denied for being "on trunk" when it is precisely the act of
      # leaving trunk. Only a checkout appearing BEFORE the subcommand counts.
      before_sub="$(echo "$cmd" | sed -E "s/(.*)git[[:space:]]+(-C[[:space:]]+\S+[[:space:]]+)?${subcmd}.*/\1/")"
      co_target="$(echo "$before_sub" | grep -oE 'git[[:space:]]+(-C[[:space:]]+\S+[[:space:]]+)?(checkout|switch)[[:space:]]+(-b[[:space:]]+)?[^;&|[:space:]]+' | tail -1 | awk '{print $NF}' || true)"
      if [ -n "$co_target" ] && [ "$co_target" != "$TRUNK_BRANCH" ]; then
        current_branch="$co_target"
      fi
      if [ -n "$current_branch" ] && [ "$current_branch" = "$TRUNK_BRANCH" ]; then
        # MERGE ON TRUNK IS ALLOWED: merging a certified branch into trunk is
        # THE landing act, and denying it forces every landing onto a human
        # even when gates have already vouched for it. The merge ritual
        # doctrine - rebase onto origin/<trunk>, gate on the branch, merge
        # --no-ff, gate again on trunk, push - requires exactly this.
        #
        # REBASE ON TRUNK IS STILL DENIED, and the distinction is not
        # cosmetic: `git merge` on trunk only ever ADDS commits, and the
        # pre-push gate re-runs on the result before anything leaves the
        # machine. `git rebase` on trunk REWRITES commits that are already
        # published and that others may have pulled. That is the
        # irreversible class, like force-push and branch deletion, and no
        # green test suite makes it safe.
        if [ "$subcmd" = "rebase" ]; then
          deny "git rebase while checked out on '$TRUNK_BRANCH' in $(basename "$OWN_REPO_ROOT") is blocked - it rewrites already-published trunk history that others may have pulled, which no test suite can make safe. Merging INTO trunk is allowed (that is the landing act, gated by this repo's own pre-push checks). To update your own branch, checkout your branch and rebase it onto origin/$TRUNK_BRANCH there."
        fi
      fi
    fi
  fi
done

exit 0
