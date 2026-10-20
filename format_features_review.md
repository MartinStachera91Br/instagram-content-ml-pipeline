# Format Features -- Review
> Edit freely: rename features, rewrite descriptions, add/remove
> categories, delete entire sections.
> When done, run: python -m scripts.format.pipeline confirm

---

## 1. plot_twist_strength
**Description:** The intensity and surprise factor of the plot twist or revelation.
**Type:** numeric

**Scale:**
- `0` -- Minimum
- `10` -- Maximum
- 0 is no surprise, 10 is highly surprising and impactful.

*Why it matters:* Strong plot twists can captivate the audience and increase engagement.

---

## 2. presenter_combination
**Description:** The combination of presenters used in the video.
**Type:** categorical

**Categories:**
- `presenter_a`
- `presenter_b`
- `presenter_c`
- `guest`
- `presenter_a_presenter_b`
- `presenter_a_presenter_c`
- `presenter_b_presenter_c`
- `presenter_a_guest`
- `presenter_b_guest`
- `presenter_c_guest`

*Why it matters:* Certain presenter combinations may have better on-camera chemistry, impacting viewer retention.

---

## 3. subject_type
**Description:** The type of subject discussed in the video.
**Type:** categorical

**Categories:**
- `company`
- `person`
- `strategy`
- `cultural_trend`

*Why it matters:* Different subjects may resonate differently with the target audience.

---

## 4. relatability_score
**Description:** How relatable the story is to social media and marketing professionals.
**Type:** numeric

**Scale:**
- `0` -- Minimum
- `10` -- Maximum
- 0 is not relatable, 10 is highly relatable.

*Why it matters:* Higher relatability can lead to increased shares and interactions.

---

## 5. educational_entertainment_balance
**Description:** The balance between educational content and entertainment.
**Type:** numeric

**Scale:**
- `0` -- Minimum
- `10` -- Maximum
- 0 is purely educational, 10 is purely entertainment.

*Why it matters:* An optimal balance can maintain viewer interest and encourage sharing.

---

## 6. hook_strength
**Description:** The effectiveness of the hook in capturing attention in the first few seconds.
**Type:** numeric

**Scale:**
- `0` -- Minimum
- `10` -- Maximum
- 0 is weak, 10 is extremely compelling.

*Why it matters:* A strong hook is crucial for preventing viewers from scrolling past the video.

---

## 7. use_of_specific_numbers
**Description:** Presence of specific numbers, revenue figures, or growth stats in the video.
**Type:** boolean

**Values:**
- `true`
- `false`

*Why it matters:* Specific data can lend credibility and make stories more compelling.

---

## 8. narrative_complexity
**Description:** The complexity of the narrative structure.
**Type:** categorical

**Categories:**
- `single_arc`
- `layered`

*Why it matters:* Layered narratives might engage viewers more deeply but risk losing them if too complex.

---

## 9. tone_of_voice
**Description:** The tone of voice used by the presenters.
**Type:** categorical

**Categories:**
- `provocative`
- `engaging`
- `colloquial`

*Why it matters:* The tone must align with audience expectations to maintain engagement.

---

## 10. pop_culture_focus
**Description:** Whether the topic is focused more on pop culture or business.
**Type:** categorical

**Categories:**
- `business`
- `pop_culture`

*Why it matters:* Topics aligned with audience interests are more likely to perform well.

---

## 11. call_to_action_quality
**Description:** Effectiveness and clarity of the call to action.
**Type:** numeric

**Scale:**
- `0` -- Minimum
- `10` -- Maximum
- 0 is ineffective, 10 is highly motivating.

*Why it matters:* A strong CTA can increase conversions and video purpose fulfillment.

---

## 12. cultural_relevance
**Description:** Relevance of the topic to current cultural trends.
**Type:** numeric

**Scale:**
- `0` -- Minimum
- `10` -- Maximum
- 0 is not relevant, 10 is highly relevant.

*Why it matters:* Culturally relevant content is more likely to be shared and discussed.

---

## 13. audience_familiarity_with_subject
**Description:** How well-known the subject is to the audience.
**Type:** numeric

**Scale:**
- `0` -- Minimum
- `10` -- Maximum
- 0 is unknown, 10 is very well-known.

*Why it matters:* Familiar subjects can attract more initial interest but risk being less engaging.

---

## 14. presenter_energy_level
**Description:** The energy level of the presenters during the video.
**Type:** numeric

**Scale:**
- `0` -- Minimum
- `10` -- Maximum
- 0 is low energy, 10 is high energy.

*Why it matters:* High energy can keep viewers engaged and interested throughout the video.

---

## 15. visual_relevance
**Description:** Relevance of visual elements to the story being told.
**Type:** numeric

**Scale:**
- `0` -- Minimum
- `10` -- Maximum
- 0 is not relevant, 10 is highly relevant.

*Why it matters:* Relevant visuals can enhance understanding and retention of the story.

---
