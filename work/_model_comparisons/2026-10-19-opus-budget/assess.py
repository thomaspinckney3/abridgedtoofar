"""Record source-aware close reading of this completed experiment; no API calls."""
import json
from pathlib import Path
import re

OUT = Path(__file__).resolve().parent


def save(name, data):
    (OUT / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def passage(variant, needle):
    path = OUT / ("revision.md" if variant == "revision" else f"inputs/{variant}.md")
    for i, text in enumerate(re.split(r"\n\s*\n", path.read_text().strip()), 1):
        text = " ".join(text.split())
        if needle in text:
            return {"variant": variant, "paragraph": i, "path": str(path.relative_to(OUT)), "text": text}
    raise ValueError((variant, needle))


def example(title, observation, needles):
    return {"title": title, "observation": observation,
            "passages": [passage(v, needle) for v, needle in needles.items()]}


assessment = {
    "verdict": "The pilot meets its length and protected-passage requirements while largely retaining Opus’s source-based style. It supports the bounded-plan revision approach, with one minor continuity loose end and identifiable interpretive losses from optional cuts.",
    "method": "Full source-aware close reading by the coding assistant, unblinded and not an independent evaluation; mechanical word, anchor, provider-completion, wording-reuse and immutable-input checks. The assistant also authored the preservation plan, informed by the earlier samples. No model judge or further generation call.",
    "findings": [
        "Length fell from 3,187 to 2,376 words: 811 words removed net, a 25.45% reduction. The new result is 76 words above the 2,300 target (+3.30%), within the specified ±5% range and 384 words below the 2,760 ceiling. It retains 55.53% of source length, compared with 74.48% before.",
        "All nine protected passages survive after whitespace and straight/curly quote normalization. The provider completed normally (end_turn), with the full bedroom/portfolio/station ending. The model did not declare infeasibility.",
        "The dominant operation remains deletion and splicing. Source five-gram reuse falls only from 93.33% to 90.95%; excluding sequences found in the protected passages, it falls from 92.17% to 88.70%. The latter figure is 41.91% for Astra and 51.11% for Sol in the earlier first drafts. These measure wording reuse, not the percentage of style retained.",
        "Unprotected prose still carries Fitzgerald’s characteristic diction and syntax: Wilson’s 'damp gleam of hope', Myrtle’s 'continually smouldering' vitality, the full threat over the car, the oversized Versailles furniture, and the long sentence of bloody aftermath survive. Myrtle’s shopping remains performed in direct speech, whereas both GPT drafts summarize it.",
        "The plan also produces a factual correction: Catherine is again excluded from 'all present' drinking whisky. The lather setup and later wipe both remain. Catherine and the McKees are identified, and the Gasoline Pump exchange is removed together with its setup.",
        "The observed overrun was not unavoidable for this chapter. With explicit permission to cut bounded optional material, the same model reaches the target range while retaining much of its earlier verbal texture. This supports a prompt/prioritization explanation; it does not isolate which prompt change caused the improvement."
    ],
    "caveats": [
        "This is one chapter, one sample, and a revision of an existing draft. The plan was manually specified by the assistant and informed by earlier results. It tests the combined workflow, not autonomous planning, a pure prompt ablation, or a fair equal-prompt model ranking. The revision remains 190–203 words longer than the GPT drafts.",
        "A minor continuity loose end remains: Myrtle gathers her dog 'and her other purchases' after the earlier shopping details have been removed. The source supports those purchases, but the revised chapter no longer establishes them. This should be resolved before adopting the text.",
        "Optional cuts have real interpretive costs. The Catholic lie and Nick’s rebuttal disappear, as does Myrtle’s 'lower orders' performance. The elevator-lever interruption is removed; the protected bedroom/station ending survives, but a potentially suggestive comic beat before it is lost. Both GPT drafts retain these units while compressing more of the surrounding prose.",
        "The taxi and dog bridges are more compressed than the surrounding prose. The dog purchase is still intelligible through 'Here’s your money'; the shift into party/marriage talk is quicker. The long eyes paragraph and almost all the shopping speech remain, so the suggested scene allocations were not hard per-scene limits.",
        "The model’s cut notes mix changes from the existing draft with omissions already made before this trial (for example the elevator McKees announcement, Europe/Monte Carlo conversation and 'crazy about him' exchange). The current pipeline parser also keeps only the first eight list entries, reducing 19 raw change notes to eight. The report preserves all raw notes and supplies an independently checked before/after cut list.",
        "The prose has not been hand-corrected after generation. The small loose end is retained in the artifact so the experimental result remains inspectable. No production prompt or published chapter was changed."
    ],
    "actual_revision_changes": [
        {"unit": "Opening and garage", "change": "Removed grey-car operations, river/drawbridge sentence, public-affair gossip, Nick’s curious-but-unwilling qualification, supercilious-assumption sentence, compact-Main-Street clause, Ford wreck and Myrtle’s age/build; preserved eyes, forced exit, car threat, vitality and ash contrast."},
        {"unit": "Travel and dog", "change": "Removed Italian child/torpedoes and dress/newsstand/drugstore/four-cab details; shortened dog bargaining and removed the explicit ten-dollar price. The narrator’s Airedale qualification, Tom’s sex assertion and payment remain."},
        {"unit": "Apartment and arrivals", "change": "Removed room inventory, hen/mother photograph and its attribution to McKee, magazines/book, dog biscuits, telephone/cigarette/disappearance detour and Catherine’s bracelets. Kept Versailles furniture, drunken framing, first-name introduction, named arrivals and lather."},
        {"unit": "Party conversation", "change": "Restored Mrs. McKee’s dress compliment as direct speech; removed ice/lower-orders/kitchen episode, Gatsby fear lines, photographer work request/Gasoline Pump joke, Catholic lie/Nick rebuttal and eleven-years/first-sweetie line. Restored Nick’s Wilson question and the source’s description of Myrtle’s obscene answer."},
        {"unit": "Whisky and shopping", "change": "Restored Catherine’s non-drinking exception. Removed spring ashtray list item and restored the list-making closing sentence; kept the speech as direct dialogue rather than summary."},
        {"unit": "Late party and ending", "change": "Removed repeated crowd movements and the elevator-lever exchange. Retained lather callback, Daisy dispute, blow, full bloody aftermath, lunch invitation and protected ending."}
    ],
    "acceptance": {
        "target_range": "pass", "ceiling": "pass", "nine_protected_spans": "pass",
        "complete_response_and_ending": "pass", "critical_causal_chain": "pass",
        "manual_editorial_review": "minor continuity finding and documented interpretive losses; not an unconditional editorial sign-off",
        "model_cut_notes": "available but require verification; raw notes preserved separately from normalized sidecar",
        "overall": "promising pilot, suitable for a broader controlled trial; not evidence for unattended production adoption"
    },
    "recommendation": "Retain the bounded three-tier plan, visible target/ceiling, mechanical counting and source-aware continuity check as the candidate workflow. Before changing production, test matched first drafts on additional chapters using frozen plans, and audit losses as well as words. Explicitly preserve any elevator/sexual-ambiguity setup judged essential, and do not treat the model’s cut ledger as authoritative.",
    "examples": [
        example("Unprotected diction survives the compression", "The revision removes the wrecked Ford but keeps Wilson’s full description and the 'damp gleam of hope' sentence. Astra and Sol compress and partly recast these sentences. This is evidence of retained texture outside the protected passages, with a genuine loss of the Ford image in the revision.",
                {"source": "The interior was unprosperous", "opus_before": "The interior was unprosperous", "revision": "The interior was unprosperous", "astra": "The interior was unprosperous", "sol": "The interior was unprosperous"}),
        example("Myrtle still performs her importance in speech", "The revision retains the address, repeated 'I’m going to'/'I’ve got to', and list-making close. It removes one shopping item but does not turn the speech into a report. Both earlier GPT drafts convey the purchases in narrated summary. This speech was essential in function, not one of the nine verbatim spans.",
                {v: "wreath" for v in ["source", "opus_before", "revision", "astra", "sol"]}),
        example("A factual repair accompanies the cuts", "The original Opus draft incorrectly extends drinking to everyone present. The revised chapter restores the source’s Catherine exception. Both GPT drafts avoid the false universal by simply saying that the second bottle was in constant demand.",
                {v: "constant demand" for v in ["source", "opus_before", "revision", "astra", "sol"]}),
        example("A small reference is left behind", "The arrival sentence keeps 'her other purchases', although the revision has cut the earlier buying of magazines, cold cream and perfume. This is source-backed but less coherent as a self-contained abridgment. The earlier Opus draft supplies the missing shopping context; this trial intentionally leaves the generated text intact.",
                {v: "regal homecoming" for v in ["source", "opus_before", "revision"]}),
        example("The elliptical ending is intact, but its lead-in loses a beat", "The revision retains the lunch invitation and all of the protected bedroom/portfolio/station text. It cuts the elevator boy’s lever warning and McKee’s apology, a comic interruption that can carry suggestive force. This is an interpretive cost that an exact ending check cannot detect.",
                {v: "Keep your hands off the lever" for v in ["source", "opus_before", "astra", "sol"]}),
        example("Cutting a whole exchange still loses Nick’s judgment", "The prior Opus and both GPT drafts keep the explicit correction of the Catholic claim. The new revision removes the claim and rebuttal together, so no dangling rebuttal remains, but this instance of Nick recognizing a lie is lost. The plan deliberately classified the entire unit as optional.",
                {v: "Daisy was not a Catholic" for v in ["source", "opus_before", "astra", "sol"]})
    ]
}
save("assessment.json", assessment)
checks = json.loads((OUT / "checks.json").read_text())
checks["manual_review"] = assessment["acceptance"]["manual_editorial_review"]
checks["critical_causal_chain"] = "pass"
checks["minor_continuity_findings"] = ["other purchases lacks retained shopping setup"]
save("checks.json", checks)
manifest = json.loads((OUT / "manifest.json").read_text())
manifest["status"] = "assessed_with_minor_editorial_findings"
manifest["assessment"] = "assessment.json"
save("manifest.json", manifest)
print("Saved source-aware assessment and six source-verified examples.")
