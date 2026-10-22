"""Source-aware editorial style analysis of saved drafts. No API calls."""
import json
from pathlib import Path
import re

OUT = Path(__file__).resolve().parent
LABELS = {"source": "Original", "opus55": "Opus 5.5", "sonnet55": "Sonnet 5.5",
          "astra": "GPT-6 Astra", "sol61": "GPT-6.1 Sol"}


def passage(book, sid, variant, needle):
    folder = "baseline/chapters" if variant == "source" else variant + "/segments"
    path = OUT / book / folder / (sid + ".md")
    if not path.exists():
        return {"variant": variant, "label": LABELS[variant], "unavailable": True}
    text = path.read_text()
    for number, match in enumerate(re.finditer(r"\S[\s\S]*?(?=\n\s*\n|\Z)", text), 1):
        if needle in match.group():
            return {"variant": variant, "label": LABELS[variant],
                    "path": str(path.relative_to(OUT)), "paragraph": number,
                    "line": text[:match.start()].count("\n") + 1,
                    "text": match.group().strip()}
    raise ValueError((path, needle))


def example(title, book, sid, interpretation, needles):
    return {"title": title, "chapter": book + "/" + sid,
            "interpretation": interpretation,
            "passages": [passage(book, sid, variant, needle)
                         for variant, needle in needles.items()]}


analysis = {
    "scope": "Style fidelity of the saved outputs, assessed separately from compression, cost, and plot fidelity. Both saved Anthropic variants are included; Opus has no completed Gatsby I output.",
    "method": "Source-aware close reading by the coding assistant, not blinded or independently judged. Examples were selected after generation to make observed differences inspectable. Existing five-gram measurements describe wording reuse, not a percentage of style preserved. No new model calls.",
    "findings": [
        "For closeness to the authors’ style as these drafts stand, Opus and Sonnet generally lead the two GPT drafts. My earlier preference for Astra was an overall abridgment judgment that included compression and continuity; it should not be read as a finding that Astra sounds most like the originals.",
        "The Anthropic approach is predominantly deletion and splicing: it retains the original clause structures, characteristic word choices, repetition, punctuation, and stretches of dialogue. GPT preserves recognizable signature passages but more often rewrites the surrounding prose into concise narration. The stylistic gap appears most clearly in that surrounding prose, not in famous quotations everyone preserved.",
        "The length difference is substantial. In Gatsby I, Sonnet keeps about 95% of the source word count, compared with roughly half for either GPT draft. Across the three chapters with all four outputs, Opus retains about 73–75% of source length; Sonnet about 60–75%; GPT about 51–54%. These results cannot tell us which model would preserve style best at equal compression.",
        "For Fitzgerald, Anthropic more consistently preserves Nick’s imaginative detours, hedges, musical accumulation, and the characters’ social performance in dialogue. Astra and Sol often preserve the observation or information while shortening the act of noticing or speaking that gives it its flavor. Astra has a modest stylistic edge over Sol in Gatsby I, but Gatsby II contains offsetting choices rather than a decisive GPT winner.",
        "For Melville, Anthropic retains more of Ishmael’s digressive address, mock scholarship, classical/biblical allusions, and long winding syntax. Opus is my preferred stylistic version across the two Moby-Dick samples, although it is longer. Sol can be closer than Astra in local cadence: it preserves the enumerated wait and the full imaginary-writer quotation in The Carpet-Bag.",
        "Verbatim language can still lose its stylistic function. Both Anthropic Loomings drafts and Sol retain the perdition punchline after cutting its money/heaven premise. Astra better preserves that joke as a working piece of religious irony. Likewise, Opus and both GPT drafts retain the tears-of-orphans climax in The Carpet-Bag, which Sonnet omits. Phrase overlap alone misses these losses.",
        "All models retain meaningful authorial identity. The GPT drafts keep major signature passages, distinctive first-person narration, archaic vocabulary, and the ambiguous endings. Their weakness is unevenness: strongly preserved passages alternate with plainer compressed narration. The evidence supports an Anthropic advantage in surface style, a mixed Astra–Sol comparison, and no reliable equal-length model ranking."
    ],
    "chapter_judgments": [
        {"chapter": "Gatsby I", "judgment": "Sonnet is closest, helped greatly by retaining nearly the whole chapter. Astra is closer than Sol in several narratorial and diction details. Opus unavailable."},
        {"chapter": "Gatsby II", "judgment": "Both Anthropic drafts preserve more texture. No decisive Astra–Sol winner: Astra keeps more imagery in places; Sol preserves more of some dialogue."},
        {"chapter": "Loomings", "judgment": "Opus best preserves the larger digressive movement; Sonnet retains much local rhetoric. Astra preserves an important joke’s logic better than the other three. Neither GPT retains the same classical texture."},
        {"chapter": "The Carpet-Bag", "judgment": "Opus gives the best combination of source cadence and satirical payoff. Sol has several local stylistic advantages over Astra. Both GPT drafts preserve a climax lost by Sonnet."}
    ],
    "examples": [
        example("Nick’s imaginative detour becomes a location update", "gatsby", "002",
            "Both Anthropic drafts retain Fifth Avenue’s pastoral weather and the imagined flock of white sheep. Both GPT drafts reduce this to Nick trying to leave on Fifth Avenue. The scene still advances, but Nick’s fanciful way of seeing the city disappears.",
            {"source": "We drove over to Fifth Avenue", "opus55": "We drove over to Fifth Avenue",
             "sonnet55": "We drove over to Fifth Avenue", "astra": "On Fifth Avenue", "sol61": "On Fifth Avenue"}),
        example("Qualified, playful speculation becomes a firmer statement", "gatsby", "002",
            "The source and both Anthropic drafts say ‘Evidently some wild wag of an oculist’. Astra retains ‘wild wag’ but removes ‘Evidently’; Sol removes both. These are small changes with a stylistic effect: Nick’s amused conjecture becomes more matter-of-fact narration. The elaborate image of the disembodied eyes remains in all versions.",
            {v: "oculist" for v in LABELS}),
        example("A speech’s social performance becomes a summary of its content", "gatsby", "002",
            "The source’s repeated ‘I’m going to’ and ‘I’ve got to’, the address ‘My dear’, and the extended shopping list stage Myrtle’s affected importance. Opus and Sonnet retain most of that performance. Both GPT versions report her promises and list in narration. Their details are largely faithful, but the reader hears less of Myrtle herself.",
            {v: "wreath" for v in LABELS}),
        example("The seduction of Nick’s attention survives more fully in Astra", "gatsby", "001",
            "Sonnet retains the source almost verbatim. Astra keeps ‘ceasing to compel my attention, my belief’, preserving the movement from attraction to distrust. Sol removes that intermediate movement and goes directly from the end of Daisy’s voice to Nick’s judgment of insincerity. The conclusion is the same, but the narrator’s changing state receives less expression.",
            {v: "basic insincerity" for v in LABELS}),
        example("Period-specific diction becomes generic", "gatsby", "001",
            "Sonnet retains ‘rotogravure pictures’ and the named resort circuit; Astra retains ‘rotogravure pictures’ but drops the places. Sol writes ‘sporting pictures’. Sol conveys recognition efficiently, but loses the period-specific medium and some of the social setting.",
            {"source": "rotogravure", "sonnet55": "rotogravure", "astra": "rotogravure", "sol61": "sporting pictures"}),
        example("Melville’s comedy includes the classical contrast", "mobydick", "004",
            "All four retain the long ‘Whenever’ sequence and the pistol-and-ball line. Opus and Sonnet also retain Cato’s theatrical suicide contrasted with Ishmael quietly taking ship. Both GPT drafts cut that contrast. The plot does not require Cato, but the learned reference and deliberately anticlimactic answer are part of Ishmael’s comic voice.",
            {v: "Call me Ishmael" for v in LABELS}),
        example("Preserving a punchline is insufficient", "mobydick", "004",
            "Astra preserves the beliefs about money and heaven that motivate the cheerful-perdition joke. Opus, Sonnet and Sol cut that premise while retaining the punchline. Astra is stylistically stronger in this local unit despite its lower overall wording overlap: it preserves the ironic mechanism, not just Melville’s concluding words.",
            {v: "perdition" for v in LABELS}),
        example("A cadence becomes arithmetic in Astra", "mobydick", "005",
            "The source and Anthropic drafts enumerate ‘a night, a day, and still another night’, making the wait unfold in the sentence. Sol largely retains the enumeration. Astra changes it to ‘two nights and a day’. The duration is accurate, but the rhetorical pacing is less close to Melville. All versions retain the anxious-grapnels pocket metaphor.",
            {"source": "Now having a night", "opus55": "Now having a night", "sonnet55": "Now having a night",
             "astra": "Having two nights", "sol61": "Having a night"}),
        example("Mock scholarship needs its change of voice", "mobydick", "005",
            "Opus, Sonnet and Sol retain the elaborate direct quotation attributed to the imaginary old writer, including ‘thou observest’ and ‘the wight Death’. Astra keeps several archaic words but compresses the quotation into attributed narration. Sol better retains the distinct quoted voice and its winding syntax here; Anthropic additionally retains more of Ishmael’s commentary around it.",
            {v: "maketh" for v in LABELS}),
        example("The satirical climax matters more than an extra stretch of quotation", "mobydick", "005",
            "Opus and both GPT drafts preserve the ice palace and tears of orphans. Sonnet instead ends the Lazarus questions without that climax, then moves to the whaling transition. Sonnet’s very high wording overlap therefore does not guarantee preservation of the passage’s strongest satirical turn.",
            {"source": "tepid tears", "opus55": "tepid tears", "sonnet55": "But what thinks Lazarus",
             "astra": "tepid tears", "sol61": "tepid tears"})
    ],
    "measurement_note": "Share of consecutive five-word sequences in the draft that also occur in the source, after case/punctuation normalization. It measures wording reuse, not style, fidelity, or completeness. Omissions and broken rhetorical setups may score highly.",
}
metrics = json.loads((OUT / "metrics.json").read_text())
analysis["wording_reuse"] = [{k: row[k] for k in ["book", "chapter", "variant", "words", "source_five_gram_percent"]}
                             for row in metrics if row["variant"] in LABELS]
(OUT / "style_analysis.json").write_text(json.dumps(analysis, indent=2, ensure_ascii=False) + "\n")
print("Saved style review with", len(analysis["examples"]), "source-verified passage comparisons.")
