"""Graphic-novel pipeline stages.

Each stage is a pure function over a storyboard dict — `stage(storyboard) ->
(storyboard, report)` — so stages compose, can be replayed, and are testable
without touching disk. The CLI in `forage.cli` exposes them as
`forage graphic <stage>`; `scripts/` retains thin argparse wrappers for the
stages that have not been migrated yet.
"""
