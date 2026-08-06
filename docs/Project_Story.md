# The Full Story: Building the Secure Face Registration and Verification Framework ("Nishika")

## What we were building

A system that lets someone register their face once, then later prove "yes, this is really me, and I'm a real person right now, not a photo or a video" — the kind of thing used for office logins, banking apps, or ID verification. The brief asked for two connected pieces: a verification pipeline (is this person real, and are they who they claim to be) and a registration pipeline (safely enrolling a new person's face in the first place) — plus a full paper trail of design decisions, test results, and a demo video, the way a real vendor would hand this off to a client.

---

## Phase 1: Planning, before writing any code

We started by reading the project brief carefully and honestly flagging its gaps out loud, before pretending it was ready to build: there was no plan for which datasets to use, no plan for how to pick the right sensitivity thresholds, and the success criteria were vague ("acceptable performance" instead of an actual number to hit). We fixed this by writing a real 15-day plan, choosing our tools (Python, MediaPipe for face detection, DeepFace for face matching, SQLite for storage — all free, all runnable on a normal laptop, no cloud needed), and setting up a daily log so every decision was written down as we made it, not remembered later from memory.

## Phase 2: Building the basics, and immediately hitting real problems

The first real work was teaching the system to reject bad photos — too dark, too blurry, face turned too far sideways, more than one face in frame, or a hand covering part of the face. We didn't guess the cutoff numbers for these checks. We took real photos of ourselves — some good, some deliberately bad — measured the actual numbers each type produced, and picked thresholds sitting in the real gap between them.

This is where we hit our first genuine bugs, not hypothetical ones: the head-angle detection was initially reporting faces as upside-down due to a coordinate math mistake, and separately could sometimes get confused between two mathematically valid but opposite answers. Both were found by testing against real footage and fixed by correcting the underlying geometry, not by fudging a number until the symptom went away.

## Phase 3: Teaching the system to detect a real, live person

This is the "liveness" part — making sure someone isn't holding up a printed photo or playing a video. We built this in three independent layers, on purpose, rather than trusting one method:

Layer one uses an already-trained, proven AI model (not something we built from scratch) that looks at a single photo and judges whether it looks like real skin versus a printed or screen-displayed fake.

Layer two asks the person to do something live — blink, or turn their head — and checks that a real, sustained movement actually happened, using math measured from real footage of our own eyes opening and closing.

Layer three, the most advanced one, tries to detect an actual heartbeat from tiny, invisible color changes in the skin caused by blood flow — something a photo or screen genuinely cannot fake, because they have no blood flow at all.

We were honest early on that layer two alone can be fooled by a good enough recorded video of the correct action — landmark-based blink detection doesn't know the difference between a real blink and a recorded one — and that's exactly why we didn't rely on just one layer.

## Phase 4: Getting real feedback, and actually changing the design because of it

Partway through, our mentor raised a real, fair concern: the system had six separate hardcoded pass/fail cutoffs scattered across different files, which is hard to explain to a client and impossible for them to adjust themselves — especially since real users won't always have great cameras or good lighting.

We rebuilt this properly rather than patching around it: instead of six rigid gates, every measurement now feeds into one combined quality score out of 100, and a client can choose between three plain-language settings — Strict, Balanced, or Lenient — depending on how forgiving they want the system to be. This is a literal dropdown in the interface, not just a setting buried in code.

## Phase 5: A serious, honest industry readiness review

Before calling this client-ready, we asked the harder question: is this actually safe and legal to deploy, not just functionally working? That review surfaced real gaps: face data was being stored without encryption, there was no way to delete someone's data if they asked (a legal requirement in most places), and the system had no login protection on its own API.

We fixed all three: face data is now encrypted before it's ever saved, registration requires explicit consent or it's refused outright, and there's now a real delete function, both a soft version (hidden from matching, recoverable) and a hard version (permanently purged). We also found that our own security testing had a hidden flaw of its own — the number used to judge "is this really the same person" was being tested against fake, made-up comparison data, not real different people. We caught this ourselves and fixed it using real photo pairs of genuinely different people (from the CFP research dataset) instead of synthetic stand-ins.

## Phase 6: A brutally honest full-system check, and sorting real bugs from false alarms

Right before this was going to be shown off, we did a full pass — actually reading through the whole codebase together as it stood, not just trusting that each piece worked because it worked once, in isolation, weeks earlier. This caught real, concrete issues that no single-piece test would have: a leftover reference to a file that no longer existed, a case where two different files had quietly grown into two separate copies of the same verification logic (meaning a fix in one wouldn't reach the other), and a case where the duplicate-registration safety check had been built and tested on its own but never actually connected to the live registration screen.

Not everything on that list turned out to be real, though, and it mattered to check rather than assume: a suspected crash in the standalone registration script — caused by a missing consent flag — turned out, on a direct re-read of the code, to already be handled correctly. That's worth stating plainly rather than quietly dropping: not every "found bug" survives a second look, and the discipline of re-checking before fixing caught a false alarm as readily as it caught real ones.

The real issues got fixed: the two copies of the verification logic were unified into one, so a fix in one place now genuinely reaches the live app. The duplicate-check was wired into the actual registration screen. The dead file reference was corrected and its script re-run cleanly with real output. The heartbeat-detection layer (Phase 3's third layer) was confirmed still built and calibrated, but a deliberate decision was made to leave it out of the live, real-time flow for now — it needs several frames buffered together to work, which adds real complexity to a live camera loop, so this was written down as a conscious scope decision with a reason, not left as a silent gap.

## Phase 7: Chasing "it feels slow and glitchy," and learning to tell the app apart from the machine it's running on

Once the pieces were connected, real usage surfaced new complaints: the camera felt laggy, sometimes blurry, and occasionally the on-screen guidance contradicted itself. Several of these turned out to be genuine, fixable code issues — most notably a recurring "check your network" warning during camera setup, which was traced to a networking setting that was defined in the code but never actually being passed to the connection, so the underlying library fell back to a public default and periodically complained about it. Passing the setting properly and testing it across five clean runs fixed it for good.

Others turned out not to be app bugs at all, and it took real measurement, not guessing, to tell the difference. The "very slow, laggy camera" complaint was eventually traced to more than fifty leftover background browser processes accumulated from earlier automated testing sessions quietly competing for the same machine's resources — a genuinely clean session, with those cleared out, ran roughly three times faster. A separate, real 20-to-30-second connection freeze was reproduced three separate times with precise timing instrumentation, and root-caused to an intermittent hiccup inside the underlying video-connection library itself — confirmed not to be a script freeze, not a leftover-process problem, and not explained by antivirus or system activity, by directly ruling each of those out with real logs rather than assuming. Since there's no code-level fix for a library-level hiccup, this was documented honestly as a known, disclosed limitation with a practical workaround for recording (keep continuous camera segments short) rather than chased indefinitely.

## Phase 8: A UI redesign that overshot once, and got caught quickly

Partway through polishing the interface for a client audience, a request to "make it look like a real, professional product" was followed too literally and produced the opposite of what was actually wanted — a dense, dark, sci-fi-style control panel full of technical jargon a real user would never understand, dashboards, and terminal-style status text. It technically matched the words of the request while completely missing the point of it.

This was caught and corrected quickly, and the fix mattered as much as the mistake: a vague instruction produced a vague-but-confident wrong answer, so the correction wasn't cosmetic tweaking, it was a much more specific brief with concrete before-and-after examples of what "professional" actually meant here — clean, calm, plain-language, the kind of interface a real non-technical user could walk up to and use without instructions. Several more rounds of real screenshot-driven fixes followed: a camera preview that didn't match the actual captured photo's framing, a verification flow that could get stuck mid-countdown with no result shown either way, and on-screen guidance that could show a green "you're good" signal while also displaying leftover text telling the user to keep adjusting — each one found from an actual screenshot, not a description, and fixed against the real evidence.

## Phase 9: Checking the finished system against the original brief, line by line

With the pieces connected and the interface stable, the last step was going back to the actual original project document — not a general impression of "is this good" — and checking every specific requirement and success criterion against real evidence, one at a time. Most of it held up well: quality checks, both liveness layers that are live, face matching with real accuracy numbers, registration, and duplicate detection were all confirmed present and working as specified.

But this pass also caught two things worth being honest about rather than glossing over. First, the system's staged-attack testing — printed photos, replayed video, screen replays — had only ever been measured against five total attack attempts, with two of the five getting through; far too small a sample to honestly claim the brief's "attacks are rejected" requirement is met, in either direction. Second, two of the four registration image-quality checks the brief specifically asked for — contrast and resolution — were never actually built; only brightness and blur were. Both gaps are now being closed: a much larger staged-attack test set, the two missing quality checks, a real architecture diagram (the brief asks for one explicitly, and until now only a file listing existed), and a single consolidated final report pulling together everything measured across this whole project into one document, the way the brief originally asked for it.

Alongside that, the multi-step "look front, then left, then right" registration flow — the part most prone to getting stuck mid-flow — is being simplified down to a single guided front-facing capture, once it became clear that neither the duplicate-check nor the live verification logic actually relies on the side-angle captures for accuracy; they were adding reliability risk without adding real security value. And the plain-language, specific "here's exactly what to fix" guidance (move closer, brighter room, remove what's covering your face) is being extended to show up live, while the user is still positioning, instead of only after a failed attempt.

## Where things stand right now, honestly

The individual engineering is genuinely solid: real bugs were found and fixed throughout, real data was used for calibration instead of guesses, a real mentor critique led to a real architectural change rather than a cosmetic one, and every known weakness — the deferred heartbeat layer, the small attack-test sample, a measured (not assumed) gap in fairness across different groups of people, the intermittent connection hiccup, the missing quality checks — was written down and disclosed rather than hidden or quietly worked around.

What's left is a short, known list, not a mystery: confirm the most recent fixes (front-only registration, live specific guidance, the larger attack test, the two new quality checks, the architecture diagram, and the consolidated final report) come back with real evidence attached, run the full automated test suite fresh and confirm it passes end to end, and then record the demonstration video — the one deliverable named explicitly in the original brief that, as of right now, still doesn't exist.
