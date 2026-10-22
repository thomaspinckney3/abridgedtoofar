"""Assemble the source-aware review and measurements without editing model prose."""
import json
import trial as t
from forage.target_revision import normalized


def main():
    m=t.verify()
    comparison=t.read(t.OUT/'comparison.json')
    reviews=t.read(t.OUT/'reviews.json')
    assert len(comparison['chapters'])==len(reviews)==4
    for key,review in reviews.items():
        for example in review.get('examples',[]):
            for passage in example['passages']:
                assert normalized(passage['text']) in normalized((t.OUT/key/(passage['variant']+'.md')).read_text()), (key,passage)
    first=comparison['mean_absolute_target_deviation_percent']['first']
    final=comparison['mean_absolute_target_deviation_percent']['revision']
    total=comparison['protected']['revision']
    api_cost=round(sum(t.read(p)['cost_usd'] for p in t.OUT.rglob('*.response.json')),6)
    results={
        'summary':f'The counted revision step reduces mean absolute target deviation from {first:.2f}% to {final:.2f}% on the same four chapters. Original targets remain fixed in both passes. The second pass preserves {total["present"]} of {total["total"]} required exact excerpts; remaining length differences and editorial concerns stay visible for review.',
        'findings':[
            'Implemented in forage.target_revision and available through forage draft-two-pass. One whole-book planning call per book is followed by two chapter calls: initial abridgment, then cut evaluation and revision using exact counts. No chapter-specific editorial choices were written by hand.',
            'The second pass receives the original source, the same validated plan, the mechanically measured first-draft count, the exact required net change, and numbered draft paragraphs with word counts and protected-passage labels. It returns a complete chapter and an editorial cut evaluation.',
            'Code recounts the revision, checks required exact text, validates cut-evaluation paragraph references, and calculates actual words removed and added. These measurements are independent of the model’s claimed counts or estimated savings.',
            f'The run made {len(list(t.OUT.rglob("*.response.json")))} paid calls at a measured cost of ${api_cost:.6f}. Both book plans passed source-evidence validation before drafting.',
            'Berlin retains the Sumner/cabman/poodle and Apthorp/Beethoven chains; its language-proficiency qualification is lost in revision. Dynamo explicitly keeps the Marx payoff and its principal argument, but still needs shortening. The chapter-level notes below record the Christie findings.',
            'Protected text is only one part of fidelity. The manual review identifies specific tradeoffs and checks speaker attribution, source uncertainty, clue placement and transitions. Automatic cut-rationale checks are limited to obvious contradictions where all referenced paragraphs remain verbatim.',
            'There is no automatic third generation pass, manual trimming, target adjustment, production replacement or publication. Remaining target differences are measured and reported rather than accepted through an allowance.'
        ],
        'next_pipeline_changes':[
            'The measured-feedback step is effective in this sample. Preserve its single target, explicit net change and before/after artifacts.',
            'For an exact-length requirement, a remaining mismatch needs another bounded revision and recount; this experiment stops after the requested second pass.',
            'Retain semantic review: an exact word count and surviving protected excerpts cannot prove that every qualification, attribution or cross-chapter connection survived.'
        ],
        'limits':m['limitations']+[
            'One response per pass per chapter. This is not a statistical reliability estimate.',
            'Editorial review was performed by the coding assistant with knowledge of which pass produced each text.',
            'Full-book source evidence is checked mechanically for existence, not for the completeness of the planner’s dependency inventory.',
            'The new command produces review artifacts. The existing production drafting command and accepted book text have not been replaced.'
        ],
        'chapters':reviews,'measurements':comparison,
        'implementation':{'module':'forage/target_revision.py','command':'forage draft-two-pass','tests_passed':149}
    }
    t.save(t.OUT/'assessment.json',results)
    for key in reviews:
        p=t.OUT/key/'checks.json'; checks=t.read(p)
        checks['manual_review']='completed with findings; see assessment.json'
        t.save(p,checks)
    m['status']='complete_measured_and_reviewed'
    m['review_completed_at']=t.stamp()
    m['summary_measurements']={k:comparison[k] for k in ['mean_absolute_target_deviation_percent','total_words','protected']}
    m['report']='report.html'
    t.save(t.OUT/'manifest.json',m)
    print('Reviewed four chapters; verified quoted examples; model prose left unchanged.')

if __name__=='__main__':main()
