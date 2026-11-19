# Job Discovery and Ranking Pipeline

**[Live dashboard](https://ruhinpatel.github.io/job-discovery-pipeline/)**

Job postings arrive from many sources, and most of them are duplicates, reposts, or roles the candidate is not eligible for. A person can only act on a handful per day. This pipeline collects postings from several sources, normalizes them into one schema, removes roles that are already resolved, applies hard eligibility gates, scores what is left against a fit rubric, routes each row to an effort lane, and hands a short ranked queue to a human to review. The pipeline orders the work, and a person decides what to do with it.

> **Runs on 30 synthetic demo postings. Human-in-the-loop: all outputs are reviewed by a person before use.** No real postings, no network calls, and no production usage are claimed.

![Job discovery pipeline dashboard](docs/dashboard.png)

**The funnel on the demo data:** 30 ingested -> 6 resolved-suppressed -> 11 gated out -> 4 in-batch duplicates collapsed -> 9 ranked and lane-routed for human review.

## Quickstart

```
pip install -r requirements.txt
PYTHONPATH=src python src/pipeline/candidate_queue.py
PYTHONPATH=src python -m pytest -q
```

`PYTHONPATH=src` is required because the package lives under `src/`.
Real output of the queue command (table trimmed to the first 5 of the 9 queued rows; the full run lists all 9, then the gated-out summary):

```
30 postings | 6 resolved-suppressed | 11 gated | 4 in-batch duplicates | 9 in queue

 #  Score  Lane           Company            Title                          Matched skills                                               Why
 1   93.3  1 FAST-APPLY   Tidewater Software Backend Engineer I             8 (Python, Go, SQL, AWS, Kubernetes, REST APIs, Git, CI/CD)  score 93.3 at or above 70
 2   80.0  1 FAST-APPLY   Lumen Orbital      Software Engineer, New Grad    6 (Python, Go, AWS, REST APIs, Git, CI/CD)                   referral bypasses the keyword screen
 3   73.3  1 FAST-APPLY   Kestrel Security   Platform Engineer, New Grad    5 (Go, AWS, Kubernetes, Git, CI/CD)                          score 73.3 at or above 70
 4   66.7  2 QUICK-TAILOR Northgate Robotics Software Engineer, Perception  4 (Python, Go, Git, CI/CD)                                   score 66.7 in the 60-70 band where a short t...
 5   60.0  2 QUICK-TAILOR Fernwood Games     Software Engineer New Grad 2027 3 (Python, Git, CI/CD)                                       score 60 in the 60-70 band where a short tai...
...
Gated out: 1 clearance, 1 location, 8 min_yoe, 1 work_authorization
```

The test suite currently reports `101 passed`.

## Architecture

```text
  Sources (4 adapters)      linkedin_alerts, job_boards, github_lists, company_careers
          |
          v
  Normalization             map each source's shape to one canonical posting schema
          |
          v
  Dedup ledger              drop roles already resolved (company|title fingerprint)
          |
          v
  Hard gates                remove ineligible rows (YOE, work auth, clearance, location)
          |
          v
  Fit scorer                weighted rubric -> 0-100 score (deterministic, optional LLM)
          |
          v
  Lane routing              SKIP / FAST-APPLY / QUICK-TAILOR / DEEP-TAILOR
          |
          v
  Ranked queue
          |
          v
  [ Human review gate ]     a person decides; nothing downstream runs automatically
```

The pipeline orders the work up to the ranked queue; the final gate is a person, not code.

### Optional: LLM scoring

By default scoring is deterministic and offline. To score with an LLM instead, run `pip install -r requirements-llm.txt` and set `JOBPIPE_LLM=1` plus `ANTHROPIC_API_KEY`; the router's cheap tier is used. Posting text is treated as untrusted data (delimited, with the model told to ignore embedded instructions), and any API or parse failure falls back to the deterministic scorer.

## Source adapters (sources + normalization)

`src/pipeline/adapters/` isolates each discovery source behind a small `SourceAdapter` subclass. There are four: `linkedin_alerts`, `job_boards`, `github_lists`, and `company_careers`. Each reads a committed synthetic raw fixture from `data/raw/`, and each fixture has a deliberately different shape (alert-digest JSON, ATS-board JSON, a curated-list CSV, a career-page JSON feed). Each adapter's `normalize` step maps its shape to one canonical posting schema (`company`, `title`, `url`, `description`, `min_years_experience`), including source-specific handling such as deriving a years-of-experience floor from free text or metadata. `ingest.run_all_adapters()` merges the four normalized outputs into one list, so everything downstream sees a single shape and adding a source means adding one adapter. In production `fetch_raw` would call live APIs or parse alert emails; here it reads fixtures only, so there are no network calls and no real postings.

The adapters are the single origin of the demo data. `data/postings.csv`, the master set the queue scores, is a generated snapshot of the merged adapter output (adapter order, each adapter's record order preserved, reposts kept so the queue's dedup has real work to do), not a hand-maintained file. To change the demo data, edit the raw fixtures in `data/raw/` and regenerate with `--write`; because the master is the adapters' output, the dashboard's per-source counts always sum to its "Postings ingested" total.

```
python src/pipeline/adapters/ingest.py          # per-source counts
python src/pipeline/adapters/ingest.py --write  # regenerate data/postings.csv
```

## Dedup / resolved-roles ledger

`src/pipeline/ledger.py` keeps a CSV ledger of roles that have already been resolved, so they are not surfaced again. Identity is a normalized `company|title` fingerprint (lowercased, punctuation, year and cohort words removed), so one role reposted at many URLs collapses to a single entry. Matching is exact after normalization, never fuzzy. The ledger holds one row per fingerprint; re-resolving a role refreshes that row in place.

## Fit-scoring rubric and cost-aware model routing

`src/pipeline/scorer.py` scores each posting against a candidate profile using a weighted rubric (skill overlap, role-title match, seniority fit) and returns a 0-100 score with a visible breakdown, so a reviewer can see why a row ranked where it did instead of trusting an opaque number. The real system scores with an LLM call; this public version swaps that call for a deterministic keyword/skill-overlap scorer against a synthetic candidate-profile fixture (`data/profile.json`), so the demo makes no API calls and uses no real data.

`src/pipeline/router.py` holds the routing decision that motivates scoring this way at all: high-frequency, low-stakes work (scoring every posting) routes to the cheapest model tier; low-frequency, higher-stakes work (tailoring content for a posting a person actually chose to pursue) routes to a larger tier. The policy is plain data (`TASK_TIERS`), separate from the scoring logic, so it can be inspected or changed without touching `scorer.py`.

## Candidate queue

`src/pipeline/candidate_queue.py` consumes the ledger and the scorer end to end: it loads postings, drops any whose fingerprint is already resolved, scores the survivors, and ranks them by fit. It also collapses within-batch duplicates: two unresolved reposts of the same role (same fingerprint, different URL) reduce to the single highest-scoring row, with ties keeping the first in input order. It returns the ranked queue together with the ledger-suppressed postings and the collapsed in-batch duplicates, each with its own count, so a reviewer can see how much repeat work was removed and why. The queue orders the work; a person still decides what to do with each row.

```
python src/pipeline/candidate_queue.py
```

The output header reports postings, resolved-suppressed, gated-out (failed a hard eligibility gate), in-batch duplicates, and the final queue size; the four removed-or-kept figures always reconcile to the total: resolved-suppressed + gated + in-batch duplicates + in queue = postings (in the demo, 6 + 11 + 4 + 9 = 30). The demo master set, generated by the adapters, is built to exercise every path: some roles match the resolved ledger and are suppressed, some are reposts (including one that appears in two different sources) and collapse to the best-scoring row, and the rest are ranked from strong backend/infrastructure fits down to off-target and over-senior roles.

Synthetic fixtures live in `data/`.

## Decision layer (hard gates + lane routing)

`src/pipeline/gates.py` runs hard eligibility gates before any posting is scored: a minimum years-of-experience floor, work authorization, clearance requirements, and location. A failed gate removes the posting regardless of how well it matches, because the scorer answers how good a fit a role is and the gate answers whether it is eligible at all. Gated postings are reported separately with the gate that removed them and a plain-language reason, so a reviewer can see what was excluded and why.

`src/pipeline/lanes.py` gives each surviving row a lane that recommends how much effort it earns: SKIP (failed gate, or a score too low to reach the keyword-match threshold with no referral), FAST-APPLY (no tailoring, submit now), QUICK-TAILOR (a short targeted edit in the band where it can realistically cross that threshold), and DEEP-TAILOR (reserved for postings a person picks deliberately, never assigned automatically). A referral routes a row to FAST-APPLY even below the keyword-match threshold, because a referral bypasses the keyword screen entirely. Each lane carries a `model_task` that maps to `router.py`: the lane decides how much effort a row gets, and the router decides which model tier performs that work.

The thresholds (`LANE_SKIP_BELOW=60`, `LANE_FAST_APPLY_MIN=70`) originate from a resume-versus-job-description keyword-match cliff, but in this public demo `score` is a profile-fit score from the scorer's rubric, not a keyword-match percentage, so the demo reuses those 60 and 70 bands as stand-in thresholds against the fit score.

## Running the tests

```
pip install -r requirements.txt
PYTHONPATH=src python -m pytest -q
```

The suite currently reports 101 passed.
