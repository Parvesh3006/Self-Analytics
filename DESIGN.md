# Design: Airmail

Self Analytics looks like correspondence crossing borders: an envelope-blue rail, pale onionskin paper, and a red-and-blue airmail edge. It stays an ordinary working dashboard. The world contributes palette, type, density and one signature move, and never the layout or controls.

## Signature move
**The postmark says where a number came from.** Headline figures, job detail pages and reports carry a circular cancellation (`components/postmark.tsx`) with the source and collection date. Tables use the small `SourceStamp`. It exists to serve the product rule that every number traces to a source, so never use it decoratively.

The airmail stripe (`.airmail-edge`) appears on the rail, and moves only while data is in transit. Use it nowhere else.

## Tokens (`web/src/app/globals.css`)
- Shell: rail `#123a86`, deep `#0d2d6b`. Ground: paper `#edf1f8`. Surfaces: sheet `#fcfcfb`, sheet-2 `#f3f6fb`.
- Ink: `#0f1f3d`, `#43526f`, `#66748f`. Lines: `#d7deeb`, `#b9c4d8`.
- Accent: air blue `#1c4fae` for actions and selection; air red `#c8202f` only for active tab or sort markers, the caret, and new-job counts.
- Status: good, warn and bad always come with an icon and a label.

## Type
Archivo (variable width) for everything, at a fixed rem scale: 26 page title, 16 panel title, 14 body, 13 notes, 12 captions. Condensed width only inside stamps. Tabular numerals only in columns.

## Charts
Follow the dataviz method: categorical slots in fixed order, sequential blue ramp for magnitude, no dual axes, hairline grids, thin 2px lines, and ranked lists instead of bar charts where labels matter. Every chart has a table equivalent. Salary medians need at least five postings. Trends use share of postings, never raw counts.

## Components
Filters are one bar above everything they scope, and live in the URL. Panels are single-level: never nest them. Loading uses skeletons first and then dims the previous result. Empty states say what to do next.
