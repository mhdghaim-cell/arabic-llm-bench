# The Miqyas Job Trial Standard, v1

**Status:** adopted 26 October 2026. Licence: CC BY 4.0. Anyone may run a Job Trial under this standard and say so, provided the trial meets every requirement below and the report says which version of the standard it follows.
**Maintainer:** Miqyas (مقياس), Mahmoud Deghaim. Changes to the standard are versioned; a trial is judged against the version named in its protocol.
**Reference implementation:** Job Trial #1, `findings/frontdesk-v2/`, protocol `docs/frontdesk_protocol_v2.md`.

## 1. What a Job Trial is

A Job Trial asks one plain question: **can this model do this job, on this machine?** It answers with evidence from complete, multi-turn interactions in a simulated workplace, scored on the final state of that workplace, and ends with one of three verdicts. It is not a leaderboard, not an aggregate score, and not a ranking without a job.

The three verdicts, in Arabic and English, are fixed:

| | Arabic | Meaning |
|---|---|---|
| ▪ Deploy | يُنشر | The model can do this job unattended on this hardware. |
| ▪ Deploy with supervision | بإشراف بشري | The model can do this job if a person checks its work or handles named sub-tasks. |
| ▪ Don't deploy | لا يُنشر | The model, or the hardware, fails the bar for this job. |

A verdict is always attached to a model, a sub-task, and named hardware. There is no fourth verdict.

## 2. Requirements

A trial is valid under this standard only if all ten requirements hold.

### R1. One question
The trial has one question that the evidence answers, written as a plain-language question in the target language (e.g. «هل يقدر نموذج عربي مفتوح يدير استقبال عيادة، بلا إنترنت؟»). The question is the title of the report. The verdict never appears in the title.

### R2. A job and a simulated workplace
The job is a real role (front desk, returns desk, IT helpdesk). The workplace is a deterministic simulator with tools and state: the model reads and changes the state only through tools, and the simulator's answers are reproducible from a seed. Success is judged on the final state of the simulator against pre-registered accept conditions, never on the wording of the model's replies alone.

### R3. Episodes with a dev/test split
Users are scripted episodes in the target dialect, with categories fixed in advance (e.g. booking, cancel, reschedule, emergency, adversarial). A dev set is used for building and piloting; the test set is untouched after pre-registration. Safety-critical categories get extra repetitions. Each episode has an oracle: a scripted perfect worker that must succeed.

### R4. Pre-registration
The protocol, episodes, scorer, pass marks, and hypotheses are committed to a public repository before any model is run, and the commit hash is reported. Any later change is a dated, reasoned amendment in the same repository. A change prompted by a model's score is not allowed; a change prompted by a scorer bug found in the dev pilot is allowed and must be disclosed.

### R5. Validity suite
Before results are reported:
- the oracle replays at 100% in every arm;
- a set of deliberately bad agents (negative controls: inventing times, silence, booking without asking, delayed escalation, and others relevant to the job) are all caught by the scorer;
- every automatic critical flag is reviewed by hand and the confirmed and cleared counts are reported;
- a blind human audit of at least 30 interactions, graded without knowledge of model, arm or scorer verdict, reaches at least 90% agreement on success;
- a reproduction run (same seeds, fresh server) is reported as the share of identical outcomes.

### R6. Statistics
Report, for every model and arm: success with a 95% confidence interval from a cluster bootstrap by episode; pass^k across repetitions; paired comparisons between models with intervals; critical failures as counts; and cost per correctly completed interaction (seconds of compute and generated tokens). Report the automatic numbers and the numbers after human review, and their difference.

### R7. The hardware ladder
Every trial reports waiting time per user message on three named machines:
- **floor**: an ordinary laptop a small business already owns (the reference floor is a 2020 Intel laptop with 8 GB);
- **middle**: a machine a small business would buy today (an Apple-silicon Mac or a 12–16 GB consumer GPU);
- **ceiling**: a workstation GPU (RTX 4090 class).
Times come from direct runs or from a speed model that has been validated on real interactions on that machine class (median absolute error reported). Models that do not fit in memory are reported as "does not fit", not as a time.

### R8. The verdict
Stated once, after the evidence, per model and per sub-task, on named hardware, using the three fixed words. Sub-tasks that fail for every model (e.g. rescheduling) get their own line.

### R9. The publication set
A permanent URL holding: the report in the target language with an English technical summary; a scorecard image; a slide document; the social text used; a `results.json` with every number in the report; and the raw interactions in full. A tagged release and a persistent identifier (DOI) per edition.

### R10. Disclosure
The report states: the model list and the inclusion rule; quantisation and runtime; sampling settings and their source; licences of models and corpus; funding and independence; the author's competence in the dialect and who reviewed the episodes; what was not measured; and a corrections log.

## 3. What a Job Trial never does
- Publish an aggregate score or a ranking without a job.
- State a verdict in a headline, or without hardware.
- Make an empirical claim without a link to the data behind it.
- Change the test after seeing a score.
- Use a fourth verdict word, or colour alone to carry a verdict.

## 4. Inclusion rule for models (Miqyas editions)
Open weights, Arabic capability claimed by the publisher, runs in llama.cpp at the quantisation stated. Vendor-recommended sampling settings, cited. A model is tested as released; deployment-tuned configurations are reported separately and labelled.

## 5. Reproduction
Each edition ships a reproduction kit: ten test episodes, one command, and a result file format. A reproducer who returns a result is named on the edition page in the same type as the author, with their numbers published as received.

## 6. Versioning of this standard
v1, 26 October 2026. Proposed changes are issues in the repository; accepted changes produce v1.1, v2, and so on. An edition names the version it follows in its measurement strip.
