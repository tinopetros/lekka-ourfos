# Release 1: decisions

Phases 1 to 9 and what follows them are release 1. Each phase kept its own ADR; the meaningful ones get gathered here later. New decisions that belong to no phase start here.

### 1. The services run on one instance (latency study 1)

- A run's calls to the services come one after another. On dev, Cloud Run started a second instance for `acknowledge` while the one `receive` had woken sat idle: about 6s of extra cold start
- So `max_instance_count = 1`. The first cold start from zero stays: keeping an instance warm is billed by the hour, for a few requisitions a month
- At most 10 requests at once on it (`max_instance_request_concurrency`), about 10 runs mid-step. A classify holds its files about three times over, so a burst can't pile enough onto the one instance to run it out of memory. The eleventh waits, or gets a 429 the workflow retries
- The trigger keeps Cloud Functions' default, 77 instances in `africa-south1`, one request each. It's public, but a flood costs little, and a cap risks refusing a real submission the form's add-on may not retry
- **Revisit** if volume grows: a second instance, or 2 GiB, before any run waits on the limit
