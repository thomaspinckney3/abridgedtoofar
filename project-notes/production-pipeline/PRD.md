# Book Production Requirements

## Problem

Forage has capable generation and review components, but file existence can
be confused with completion or freshness. Corrections can leave review views
and narration behind the current draft. Graphic production is disconnected
from the normal CLI workflow.

## Intended Outcome

An operator can inspect a production plan, execute selected outputs, resume a
failed run, review text/audio/panels, and regenerate after corrections without
silently publishing partial or obsolete artifacts.

## User Flows

1. Select a book and requested outputs; preview pending stages without cost.
2. Execute the workflow using configured providers. Rerun resumes valid work.
   Publish a versioned work-in-progress revision to a separate review website.
3. Review prose, listen to audio, or inspect panels there asynchronously under
   the existing authentication model. Generation does not wait for approval by
   default.
4. Periodically import remote feedback, deduplicate it, incorporate eligible
   prose feedback using the existing application ledger, regenerate affected
   outputs, and republish for further review.
5. Explicitly release a completed revision publicly. Continue accepting
   feedback afterward and publishing subsequent revisions without losing the
   prior release or treating an unreviewed draft as the same release.

## Acceptance

The measurable acceptance criteria are AC1–AC12 in [PROJECT.md](PROJECT.md).
Human media comments must be stored and exportable; automated interpretation
of arbitrary media-specific feedback is not implied. Prose feedback continues
through the existing constrained review-apply stage.

The CLI exposes review publication, configured feedback import/sync, and public
release promotion as distinct operations. An external scheduler can invoke sync
periodically; a new always-running service is not required. Imported revision
anchors survive local revision changes. No live site mutation is needed for
implementation verification.

## Boundaries

This is an implementation and offline verification task. It does not include
generating paid books, choosing publishing rights, deploying the public site,
or certifying creative quality from mocked model responses.
