# Titles, thumbnails, trailer

## Research before suggesting (don't guess)
1. Pull real numbers: in the browser, YouTube search results sorted by view count
   (`/results?search_query=<q>&sp=CAM%253D`), reading `ytInitialData` for title, views, age, length.
   Search several angles of the video (place, food, "first time in", "worth it", time-boxed "48 hours",
   the creator's audience e.g. "desi in New York").
2. Note which *patterns* win and for whom -- giant numbers usually belong to giant channels; for a small
   channel the packaging must also match what people search.
3. Recommend one title + one thumbnail, plus an alternative to A/B in YouTube Studio "Test & Compare".
   Be honest: nobody can promise a video "blows up".

Patterns that tested well for a city/food vlog:
- Honest verdict / "is it worth it?" (pays off if the video actually gives one)
- Time-boxed trip ("48 Hours in ...")
- Superlative question ("Is This The World's Best Pizza?") -- if the topic is only part of the vlog,
  add context in brackets so retention doesn't suffer: "... ? (48 Hours in NYC)"
- Keep it under ~60 characters (mobile truncation)

## Thumbnail rules (from published CTR studies; treat percentages as directional)
- A real, expressive face ~1/4-1/3 of the frame (faces appear in most breakout thumbnails); genuine
  expression beats a fake scream.
- <= 3-4 words; text *adds to* the title rather than repeating it (title asks "World's best pizza?",
  thumbnail says "New York's Most Famous Slice!!").
- One focal point, high contrast, nothing important bottom-right (timestamp).
- Context background that tells the story (e.g. the restaurant's famous sign) + the creator cut out on top
  with a white sticker outline and soft shadow -- `scripts/cutout` (Apple Vision) + `thumbnail.py compose`.
- Use the channel's house text style from the profile so the channel looks consistent.

## Process
1. Candidate stills: `thumbnail.py still CLIP T out.png` at expressive moments (bites, reactions); HDR is
   tone-mapped so stills match the video.
2. Cut-out: `swiftc -O scripts/cutout.swift -o scripts/cutout` once, then `scripts/cutout frame.png me.png`.
3. Compose 2 variants, look at them small (phone size) -- if the text isn't readable at 320 px wide, it fails.

## Social trailer (horizontal reel)
- Reuse the opening montage (already loved) instead of building a new edit.
- Drop in 3-4 short dialogue beats (a food reaction, meeting a friend, a funny line).
- Music from the first frame, soft fade-in, then loud and continuous; voices ride on top
  (`no_duck`, gentle side-chain, `music_level` ~0.6).
- End on the title alone. Avoid TV/movie meme clips on Instagram (stricter copyright matching).
