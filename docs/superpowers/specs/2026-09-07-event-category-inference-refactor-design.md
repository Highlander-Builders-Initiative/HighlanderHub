# Event Category Inference Refactor

## Goal

Keep PR #7's category behavior while moving category policy out of
`normalize_events.py` and replacing its generic plural suffix with explicit,
predictable keyword aliases.

## Structure

Add `pipeline/category_inference.py` as the canonical owner of:

- Localist type-to-category precedence.
- HighlanderLink theme and category-name mappings.
- Weighted text-keyword scoring.
- Source-specific category resolvers.

`normalize_events.py` remains responsible for reading source fields and
constructing event rows. It passes normalized label lists, titles, and
descriptions into the category resolvers instead of passing whole raw records.

## Keyword Matching

Each category contains keyword concepts. A concept lists every accepted textual
form explicitly, such as:

- `("class", "classes")`
- `("gallery", "galleries")`
- `("thesis", "theses")`

Every form is matched on whole-word boundaries. All aliases in one concept
share one score, so text containing both `class` and `classes` cannot count the
same concept twice. Existing title, source-label, and description weights and
the explicit category tie-break order remain unchanged.

This deliberately avoids a general English singularization system. The campus
vocabulary is small, and explicit aliases make accepted behavior visible in the
policy table.

## Tests

Add focused tests for the pure text classifier using table-driven cases:

- regular and irregular plural aliases;
- aliases counting once per concept;
- negative substring matches such as `classical` and `self-defense`;
- title/source/description field weights;
- category tie-breaking.

Keep the existing mapper tests as integration coverage for Localist and
HighlanderLink source precedence.

## Compatibility

The refactor must preserve PR #7's source-taxonomy precedence, athletics
override, weighted scoring, category priority, and `community` fallback. No
database schema, event-row shape, or external dependency changes are included.
