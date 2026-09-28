# Published content audit — September 28, 2026

## Result and scope

The public feed still contains incorrect dates, an unsupported venue, content outside the UCR student audience, mislabeled deadlines, and unsupported food/registration badges. The most urgent correction is ACM's revised kickoff schedule: both its old and new dates are live.

This was a read-only audit. No production rows, source decisions, code, notifications, or paid model jobs were changed. This report is the only repository change.

- Read all **843 live event rows**, 3,121 source records, 33 duplicate-review records, and 19 deletion records.
- Scanned the **346 current/upcoming public listings**, using the app's actual visibility and end-time rules. They have 277 linked source records.
- Revalidated 269 complete saved source assessments against the current validator; reviewed captions, OCR, dates, classifications, eligibility, food and RSVP evidence for flagged listings. This is a broad metadata scan with focused semantic review, not manual verification of every historical flyer.
- Verified six affected event detail pages in the live browser. Its counts matched the database: 346 upcoming, 49 marked free food, and 37 marked deadlines.
- Visually inspected both versions of ACM's date/time slides and the Snow Club flyer.
- Re-read all events at the end: all 843 rows were unchanged from the initial snapshot.

Times below are Pacific. Local evidence and read-only audit scripts are in `/private/tmp/hh-content-audit-20260928/`. Saved source text establishes what ingestion saw; it does not establish that every original Instagram post is still available or unchanged.

## Fix first

### 1. ACM's superseded schedule remains visible alongside its replacement

The older [kickoff post](https://www.instagram.com/p/Ddt8nHdG6am/) was published September 25. The [newer post](https://www.instagram.com/p/Dd0PmR7FAJZ/), published September 27 Pacific, uses the same design and revises the schedule. Visual inspection confirms the changes are printed on the images, not OCR mistakes.

| Session | Older listing still live | Newer listing also live |
| --- | --- | --- |
| ACM Info Night | September 29, 6:30 PM | **September 28, 6:30 PM** |
| Trivia Night | October 1, 5–6 PM | **October 1, 6:30 PM**, no end stated |

The four IDs are:

- Old info night: `ig_acm_ucr_p3994115015402301094-20260930T0130Z`
- New info night: `ig_acm_ucr_p3995887370667033177-20260929T0130Z`
- Old trivia: `ig_acm_ucr_p3994115015402301094-20261002T0000Z`
- New trivia: `ig_acm_ucr_p3995887370667033177-20261002T0130Z`

Treat these as a source revision requiring review and withdrawal of the superseded sessions. Do not relax all date/time conflict safeguards. The older post also lists an October 2 Leetcode workshop omitted from the new flyer; omission alone is insufficient to establish cancellation of that separate session.

### 2. An expired awards deadline was moved into 2027

[Political Science Awards Application Deadline](https://highlanderhub.app/events/ig_highlander_opps_20270527T2300Z) is stored as **May 27, 2027, 4 PM**. Its source story was posted May 26, 2026 and prints a **Wednesday, May 27, 4 PM** deadline. May 27 was Wednesday in 2026; it is Thursday in 2027. The 2026–27 text describes the award/eligibility year, not the application deadline's year.

This is an expired **May 27, 2026** deadline appearing as upcoming. Event ID: `ig_highlander_opps_20270527T2300Z`; source: `instagram:3905737909998506298`.

The live page confirms the Thursday date. The old Instagram image URL returned HTTP 403, so the date finding relies on saved source OCR, the source timestamp, and the weekday match rather than a fresh visual inspection.

### 3. College Night still shows an invented venue

[Chance Encounters: College Night](https://highlanderhub.app/events/ig_ucrarts_p3992937072452983510), October 1, 6–9 PM, visibly displays `UCR (implied by college lounge/UCR mention)`.

The original caption addresses college students but does not establish that venue. The saved reminder `instagram:post:3994869751280487508` explicitly names **The Culver Center**. The older event's timed occurrence remains supported; its location needs a reviewed correction using the reminder.

The current location validator rejects the inference, but the old cached assessment remains live. A code safeguard alone has not corrected this row. Event ID: `ig_ucrarts_p3992937072452983510`.

### 4. Two listings are outside the intended student audience

| Listing | Evidence | Recommended disposition |
| --- | --- | --- |
| [Associate Vice Chancellor for Financial Planning & Analysis](https://highlanderhub.app/events/ig_ucrcareers_p3993454373387702537) | Executive finance leadership recruitment, explicitly seeking an experienced senior leader. Published as `student_deadline` for October 12. | Exclude from the student feed. |
| [2027 United States Senate Youth Program](https://highlanderhub.app/events/ig_eaopucr_p3981918303153167138) | Flyer explicitly addresses **California high-school juniors and seniors**. Published as a student deadline for October 7. | Exclude from the UCR student feed. |

Both are visible in the live browser. The classifier currently bypasses eligibility checks for Instagram sources (`pipeline/classify.py`, `classify_content_kind`), so a university-affiliated account can publish an opportunity meant for a different audience.

Do not treat every off-campus or restricted event as invalid. For example, the Lifeline event is explicitly for ages 18–39; its flyer mentions high-school events in a separate section. Club invitation requirements also do not by themselves make an event incorrect.

## Other confirmed metadata defects

### 5. Two deadlines are classified as attendable events

| Listing | Actual cutoff | Stored kind |
| --- | --- | --- |
| [Volunteer Cleanup Event Sign-up Deadline](https://highlanderhub.app/events/ig_ucrpds_p3993126604118164988-20261001T0100Z) | September 30, 6 PM; the cleanup itself is October 1, 9:30–10:30 AM | `student_event` |
| [Pi Sigma Epsilon Application Deadline](https://highlanderhub.app/events/ig_ucrpse_p3995937187540986297-20261009T0500Z) | October 8, 10 PM | `student_event` |

Both should be `student_deadline` and appear in the deadline filter. The live PSE page instead displays **Career / Free food**, uses event calendar wording, and has no deadline badge.

Root cause: `post_rows` passes the post-level `result["kind"]` to every occurrence. A post containing activities and a cutoff gives all of them the activity kind. Preserve the real cleanup and recruitment activities while correcting the two cutoff rows.

### 6. At least 16 current free-food badges lack support for that specific session

These are unsupported claims, not proof that the organizers will provide no food. The saved evidence does not justify the badge.

| Source group | Affected current listings | Why the evidence is insufficient |
| --- | --- | --- |
| CSA welcome week | Boba Tea House, Info Night, CCN Info Night, Field Day — **4** | A trip to a boba shop is not a promise of free drinks, and the other sessions contain no food offer. |
| Designing Dreams fall schedule | Sewing Kits, Tailoring Pop-up, Beginner Workshop, Rave/Halloween Meeting, Intermediate Workshop — **5** | The schedule's separate September 25 Boba Social makes every later sewing session inherit a food flag. |
| AACF welcome week | Outreach Night, Freshman Night, Small Group Kickoff — **3** | Boba/food is advertised for the earlier stroll/picnic, not these three sessions. |
| MSA welcome week | Fall Involvement Fair, Club Mixer, Qamaria Social — **3** | Other slides mention food. These slides advertise tabling/socializing; the coffee-shop slide even contains menu prices. |
| PSE recruitment | Application Deadline — **1** | BBQ food belongs to the October 7 activity, not the October 8 application cutoff. |

The appendix gives every affected ID. Additional PSE/CNAS sibling sessions merit the same review; the count above is deliberately limited to the clearest examples.

Root cause: `post_rows` joins OCR from **all** carousel slides and passes it to every row. `build_instagram_row` uses that combined text for `detect_free_food`, and the detector accepts bare `boba`. Food evidence needs to belong to the individual occurrence and establish provision rather than a paid venue visit.

### 7. Five direct Zoom links are presented as registration requirements

- [Anesthesiology Introductory Meeting](https://highlanderhub.app/events/ig_asig.ucrsom_p3993387279296486330), September 29.
- CMSP Information Sessions on September 30, October 13, October 21, and October 28, all from `instagram:post:3981974972906924967`.

The sources provide direct Zoom `/j/` meeting links and invite people to join. They do not state an RSVP requirement. All five have `rsvp_required=true`; the ASIG live page labels its direct meeting link **Registration / RSVP**.

Keep the meeting link, but distinguish joining a call from registering. `build_instagram_row` currently treats any accepted URL as proof of required RSVP. The earlier Google Maps case is fixed, but this semantic problem remains for meeting links.

### 8. Several activity categories are wrong or omit clear activity evidence

| Listing | Current topic | Source-supported topic |
| --- | --- | --- |
| AACF Outreach Night, September 30 | Volunteering | Get involved — its slide invites students to learn about AACF; no service activity is advertised. |
| Ballet Folklórico beginners/intermediate/advanced practices, September 30 / October 2 / October 3 | Sports | Arts & shows — these are dance rehearsals. |
| National Latino Physician Day Volunteer Opportunity, October 3 | Other | Volunteering — the source explicitly seeks volunteers for an 8 AM–3:30 PM shift. |
| MSA Fall Involvement Fair, September 30 | Hang out | Get involved — the specific session is tabling at the fair. |
| BSIB Jeopardy Night, October 14 | Career & skills | Hang out — the separate professional-development session in the same calendar supplies unrelated career context. |
| Silent Disglo, September 29 | Other | Arts & shows or Hang out — the source clearly describes a DJ/dance event. |
| Catalina Island Snorkeling Adventure, October 10 | Other | Sports & rec. |
| Collegiate Grappling Open Mat, October 3 | Other | Sports & rec. |

These are evidence-based examples, not a count of every debatable category. Prefer the specific session's activity over its host's profession or words elsewhere in a multi-event calendar. Preserve `other` when an activity genuinely cannot be established.

## Source conflicts and review candidates

### Snow Club: the source itself disagrees about the year

[UCR Snow Club AllCal 2027](https://highlanderhub.app/events/ig_ucrsnowclub_p3957192671860744764) is stored for December 12–18, **2027**. Its August 2026 caption twice identifies AllCal **2026** and describes the coming December. The actual saved flyer, visually inspected, prints **2027**.

This is a confirmed source conflict, not a confirmed OCR error. Do not silently change the year based only on one side of the post. Verify with the organizer or another authoritative announcement. The ski trip also belongs in Sports & rec rather than Other.

### Homecoming: two broad listings still overlap

`ig_ucralumni_p3976819441404675490` (Homecoming featuring Funk Flex) and `ig_ucriversideofficial_p3986151799102313494-20261107T0800Z` (Homecoming 2026) both advertise November 7 with no distinct session times. They are a strong duplicate-review candidate; confirm whether the product intends a separate headline-performance listing before merging.

SHARP's three “Fall Collab Date” entries advertise club collaboration slots. Their dates/times are supported, but the source does not establish a general drop-in event. Review how booked club collaborations should appear rather than automatically removing a potentially valid service opportunity.

## Missing imminent events

These do not represent wrong visible rows, but are relevant to the launch's content quality:

- **EMA first meeting:** September 29, **2–3 PM, HMNSS 2211**. Source `instagram:post:3994807273716605662` explicitly gives the first date. It remains a cached grounding refusal with no published IDs, and no corresponding live event exists.
- **Latinxs & the Environment seminar:** September 30, **11 AM–12:20 PM, INTN 3023**, with food advertised. Source `instagram:post:3993019144614497302` explicitly gives the starting date. It likewise has no published IDs or corresponding live event.

Recover the supported first occurrences through source review. Neither post supplies a bounded quarter-end schedule, so do not invent later dates. Ordinary reruns retain these cached refusals.

## Checks that passed and limits

- No live event ID appears in the deletion registry.
- Every current/upcoming event has at least one linked source record.
- No current/upcoming event has an end at or before its start. One old May SWE row still has equal timestamps; it is outside the current feed.
- The current duplicate planner proposes zero automatic merges. That does not settle the ACM revisions or semantic Homecoming overlap.
- Of 269 complete saved assessments checked, seven fail the current validator: College Night's unsupported location and six legacy records missing the newer evidence structure. Those six support events that also have newer post sources; they are not six proven bad public events.
- The earlier art/music festival now has `category=arts` and no map-based RSVP. Dunk a Dove is absent. The previously reported USM and Family Weekend duplicate pairs have been consolidated.
- Two source records reference absent event IDs, and the single pending review pair includes an absent SWE ID. This is bookkeeping cleanup, not an additional incorrect visible listing.
- The audit did not re-scrape every Instagram account, exhaustively test external RSVP destinations, contact organizers, or certify every archived listing. Website and database observations are current; most source comparisons use saved captions and OCR.

## Suggested correction order

1. Review the ACM replacement and withdraw its superseded date/time rows; correct College Night's venue and the awards deadline year.
2. Exclude the executive job and high-school-only program; classify the two actual deadlines correctly.
3. Correct food and RSVP evidence per occurrence, then repair affected rows without replaying paid extraction.
4. Correct the clear topic mismatches and recover the two imminent missing first meetings.
5. Resolve the Snow Club year with additional source evidence and review the remaining Homecoming overlap.

All corrections above are recommendations; none were applied in this audit.

## Appendix: unsupported free-food badges

| Group | Listing | Exact event ID |
| --- | --- | --- |
| CSA | [Boba Tea House](https://highlanderhub.app/events/ig_ucrcsa_p3994927916525294302-20260929T0300Z) | `ig_ucrcsa_p3994927916525294302-20260929T0300Z` |
| CSA | [Info Night](https://highlanderhub.app/events/ig_ucrcsa_p3994927916525294302-20260930T0300Z) | `ig_ucrcsa_p3994927916525294302-20260930T0300Z` |
| CSA | [CCN Info Night](https://highlanderhub.app/events/ig_ucrcsa_p3994927916525294302-20261001T0300Z) | `ig_ucrcsa_p3994927916525294302-20261001T0300Z` |
| CSA | [Field Day](https://highlanderhub.app/events/ig_ucrcsa_p3994927916525294302-20261002T0300Z) | `ig_ucrcsa_p3994927916525294302-20261002T0300Z` |
| Designing Dreams | [Sewing Kits- First Meeting!](https://highlanderhub.app/events/ig_designingdreamsucr_p3991225804188653761-20261003T0100Z) | `ig_designingdreamsucr_p3991225804188653761-20261003T0100Z` |
| Designing Dreams | [Tailoring Pop-up](https://highlanderhub.app/events/ig_designingdreamsucr_p3991225804188653761-20261007T1600Z) | `ig_designingdreamsucr_p3991225804188653761-20261007T1600Z` |
| Designing Dreams | [Beginner Workshop](https://highlanderhub.app/events/ig_designingdreamsucr_p3991225804188653761-20261016T2330Z) | `ig_designingdreamsucr_p3991225804188653761-20261016T2330Z` |
| Designing Dreams | [Rave/Halloween Meeting](https://highlanderhub.app/events/ig_designingdreamsucr_p3991225804188653761-20261024T0030Z) | `ig_designingdreamsucr_p3991225804188653761-20261024T0030Z` |
| Designing Dreams | [Intermediate Workshop](https://highlanderhub.app/events/ig_designingdreamsucr_p3991225804188653761-20261115T0030Z) | `ig_designingdreamsucr_p3991225804188653761-20261115T0030Z` |
| AACF | [Outreach Night](https://highlanderhub.app/events/ig_aacfucriverside_p3992368583007792793-20261001T0300Z) | `ig_aacfucriverside_p3992368583007792793-20261001T0300Z` |
| AACF | [Freshman Night](https://highlanderhub.app/events/ig_aacfucriverside_p3992368583007792793-20261003T0300Z) | `ig_aacfucriverside_p3992368583007792793-20261003T0300Z` |
| AACF | [Small Group Kickoff](https://highlanderhub.app/events/ig_aacfucriverside_p3992368583007792793-20261006T0200Z) | `ig_aacfucriverside_p3992368583007792793-20261006T0200Z` |
| MSA | [Fall Involvement Fair](https://highlanderhub.app/events/ig_msaucr_p3995798591671828458-20260930T1700Z) | `ig_msaucr_p3995798591671828458-20260930T1700Z` |
| MSA | [Club Mixer](https://highlanderhub.app/events/ig_msaucr_p3995798591671828458-20260930T2300Z) | `ig_msaucr_p3995798591671828458-20260930T2300Z` |
| MSA | [Qamaria Social](https://highlanderhub.app/events/ig_msaucr_p3995798591671828458-20261001T0130Z) | `ig_msaucr_p3995798591671828458-20261001T0130Z` |
| PSE | [Application Deadline](https://highlanderhub.app/events/ig_ucrpse_p3995937187540986297-20261009T0500Z) | `ig_ucrpse_p3995937187540986297-20261009T0500Z` |
