# Senior Algorithm Developer — Home Assignment
## Compressed Air Operations Intelligence

---

## Background

We operate a SaaS platform that monitors industrial compressed air systems across customer manufacturing sites. Each site runs multiple compressors that keep production lines running. Downtime is expensive, energy is the largest operational cost, and our customers rely on us to surface problems before they become outages.

We collect continuous sensor data from every compressor: pressure, flow, power, activity, and more. Our customer wants answers to the following questions:

1. *"Is my station operating efficiently?"*
2. *"Compressor #2 is causing me problems lately. Can you notify me in advance before it breaks down?"*
3. *"How can I save more money?"*

Your job is to help us answer those questions.

---

## What You're Given

- **`data/station_sensor_data.csv`** — 7 days of continuous sensor readings from the customer site.
- **`data/compressor_specs.json`** — Nameplate specifications for each compressor.
- **`data/data_specification.csv`** — Specifications table for the sensor data.
- **`PRIMER.md`** — A short domain primer to get you oriented. It covers the basics.

---

## The Ask

Build a system that ingests this sensor data and produces a useful, actionable report on the health and efficiency of the station.

What "useful and actionable" means is deliberately left for you to define. We want to see how you think about the problem, what you decide matters, and how you communicate findings — not just whether you can execute a spec.

At a minimum, we'd expect your submission to:

- [ ] Handle the data thoughtfully (quality, completeness, physical plausibility)
- [ ] Produce some measure of operational efficiency
- [ ] Identify and explain anything that looks abnormal
- [ ] Be callable as a service (an API endpoint) - No need for a fancy UI, but it should be easy to run and understand the output
- [ ] Include tests that give us confidence the core logic works
- [ ] Answer the business questions
- [ ] Include a short write-up explaining your approach, your assumptions, and what you'd do differently with more time

Everything else — architecture, algorithms, scope, what to prioritise — is up to you.

---

## Guidance

**Depth over breadth.** A single well-reasoned detector with clear evidence and a justified threshold is worth more than five shallow ones. We'd rather see you own one decision completely than gesture at many.

**Show your thinking.** The write-up matters. Tell us what you tried, what didn't work, and why you made the trade-offs you did. If you made a simplifying assumption, say so.

**The domain is learnable.** You're not expected to be a compressed air expert. We care about how you approach an unfamiliar domain.

**On using AI tools.** We expect senior engineers to use the tools available to them. What we're evaluating is your judgment and understanding, not whether you typed every line. Be prepared to walk through your code and defend every decision in the debrief.

---

## Submission

Please share a git repository (public or private with access granted) containing your code, tests, and write-up.

Estimated time: **6-8 hours over 2–3 days.** Please don't spend more than that — we're mindful of your time and will calibrate our expectations accordingly.

---

## Debrief

After submission, we'll schedule a 60-minute technical debrief. We'll ask you to walk us through your decisions — what you built, what you left out, and what you'd do next. Come ready to discuss the reasoning behind your choices, not just the code itself.

---

*Questions? Reach out to your recruiting contact.*
