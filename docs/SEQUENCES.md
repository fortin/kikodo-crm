# Sequences: steps, timings, and AI suggestions

## How steps are added to sequences

1. **Create a sequence:** Go to **Sequences** → **New Sequence** (or the "New" link from the sequence list).
2. **Fill name and description:** Enter a name and optional description for the sequence.
3. **Steps table:** You get a table of steps with columns: **Order**, **After (days)**, **Medium**, **Auto?**, **Subject**, **Body**, **Delete**.
4. **Default suggestion:** On first load, the form is pre-filled with 4 steps:
   - Step 1: Day 0, email
   - Step 2: Day 3, email
   - Step 3: Day 7, meeting
   - Step 4: Day 14, email
   You can edit or delete any row. One extra empty row is shown so you can add another step.
5. **Suggest steps with AI:** Click **Suggest steps with AI** (requires Ollama running). The LLM uses the sequence name and description to suggest 4–6 steps with:
   - **Optimal timing:** First touch Day 0, follow-ups 2–4 days apart, mix of email/call/meeting, total under ~21 days unless long nurture.
   - **Activity types:** email, call, meeting, task, linkedin, note, demo, proposal.
   - **Subject and body** drafts for each step (you can edit before saving).
   After suggesting, review and edit the table, then click **Save Sequence**.

**After (days)** is *offset from the previous step*: Step 1 is usually 0 (same day as enrollment), Step 2 might be 3 (3 days after Step 1), etc. The sequence engine (`run_sequences` management command) runs on a schedule and executes the next step when `next_run_at` is due.

## Automating timings for effectiveness

- **Current behaviour:** Timings are set per step via **After (days)**. The default heuristic (0, 3, 7, 14) follows a common pattern: first email, quick follow-up, then meeting/demo, then final touch.
- **AI-suggested timings:** When you use **Suggest steps with AI**, the prompt instructs the LLM to use best-practice timing (Day 0 first touch; 2–4 days between emails; mix in call/meeting after 1–2 emails; final touch 5–7 days after previous; total under 21 days unless long nurture). So timings are automated in the sense that the LLM proposes them from your name/description; you can still edit any value.
- **Future improvements:** You could later use analytics (e.g. open/reply rates by delay, or A/B tests) to recommend offsets; that would require storing per-step metrics and a small “optimizer” or report.

## LLM integration (Ollama)

- **Where it’s used:** The same Ollama integration used for **Signals** (URL → headline, summary, etc.) is used for **Suggest steps with AI** on the sequence form.
- **Settings:** `OLLAMA_BASE_URL` and `OLLAMA_MODEL` in settings (e.g. `http://localhost:11434` and your model name). If Ollama isn’t running or the call fails, the form falls back to the default 4-step suggestion and shows a warning.
- **What the LLM suggests:** Number of steps, **offset_days** (timings), **activity_type**, and draft **subject** and **body** for each step, plus **auto_execute** (true for email, false for call/meeting so they become tasks). You can change any of these before saving.

## Running the sequence engine

Sequence steps are executed by the **run_sequences** management command. Run it on a schedule (e.g. cron every 5–15 minutes):

```bash
python manage.py run_sequences
```

Use `--dry-run` to list due enrollments without executing. Enrollments with `status=active` and `next_run_at <= now` get their next step executed (email sent or task created); then `next_run_at` is set to the following step’s offset.
