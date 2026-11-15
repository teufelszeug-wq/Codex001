"""Evidence-bound operational publication gate, separate from research previews.

Passing verifies persisted artifacts and their internal bindings. Provider receipts
and human QA are retained evidence, not external attestations of authenticity.
The original positional API remains callable; incomplete legacy records fail closed.
"""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
DAY_DELTA_FIELDS = frozenset({"body_weight", "body_weight_change", "odds", "going",
                              "weather", "track_bias", "scratches", "rider_change"})
TICKET_LEGS = {"WIN": 1, "PLACE": 1, "QUINELLA": 2, "EXACTA": 2,
               "WIDE": 2, "TRIO": 3, "TRIFECTA": 3, "FRAME_QUINELLA": 2}


def content_hash(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _hash(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _time(value):
    if not isinstance(value, str):
        raise ValueError("timezone-aware timestamp required")
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timezone-aware timestamp required") from exc
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return instant


def _execution(record, author, stage, receipts, race_id, snapshot, now, errors):
    """Require the complete provider transcript and a durable-save timestamp."""
    label = stage + ":" + author
    try:
        execution_id = record["execution_id"]
        result = receipts[execution_id]
        if result["output"] != record:
            raise ValueError("output differs from provider transcript")
        from prism_ops.provider import validate_execution
        validate_execution(result, require_independent=True)
        receipt = result["receipt"]
        if (receipt["forecaster_id"] != author or receipt["stage"] != stage or
                receipt["character_snapshot_hash"] != snapshot or
                receipt["output_hash"] != record["content_hash"] or
                record["race_id"] != race_id or record["forecaster_id"] != author or
                record["stage"] != stage or record["character_snapshot_hash"] != snapshot):
            raise ValueError("receipt binding mismatch")
        completed = _time(receipt["completed_at"])
        saved = _time(record["saved_at"])
        persisted = _time(result["persisted_at"])
        if not completed <= saved <= persisted <= now:
            raise ValueError("invalid durable-save time")
        return persisted
    except (KeyError, TypeError, ValueError, ImportError, AttributeError):
        errors.append("EXECUTION_UNPROVEN:" + label)
        return None


def _forecast(record, author, numbers, horse_numbers, frame_counts, errors, stage):
    label = stage + ":" + author
    if not isinstance(record, dict):
        errors.append("MALFORMED_FORECAST:" + label)
        return
    def number(row):
        if not isinstance(row, dict):
            return None
        mapped = horse_numbers.get(row.get("horse_id"))
        explicit = row.get("horse_no")
        if mapped is not None and explicit is not None and mapped != explicit:
            return None
        return mapped if mapped is not None else explicit

    diagnoses = record.get("diagnoses")
    if (not isinstance(diagnoses, list) or len(diagnoses) != len(numbers) or
            any(not isinstance(d, dict) or number(d) not in numbers or
                not _text(d.get("reason")) for d in diagnoses) or
            {number(d) for d in diagnoses if isinstance(d, dict)} != numbers):
        errors.append("ALL_RUNNER_DIAGNOSES_REQUIRED:" + label)
    picks = record.get("picks")
    valid_picks = (isinstance(picks, list) and bool(picks) and
                   all(isinstance(p, dict) and number(p) in numbers and
                       _text(p.get("mark")) for p in picks))
    if valid_picks and len({number(p) for p in picks}) != len(picks):
        valid_picks = False
    if not valid_picks and not (picks == [] and _text(record.get("skip_reason"))):
        errors.append("MARKS_OR_SKIP_REQUIRED:" + label)
    tickets = record.get("tickets")
    if not isinstance(tickets, list):
        errors.append("TICKETS_REQUIRED:" + label)
        return
    if not tickets and not _text(record.get("skip_reason")):
        errors.append("TICKETS_OR_SKIP_REQUIRED:" + label)
    for ticket in tickets:
        if not isinstance(ticket, dict):
            errors.append("INVALID_TICKET:" + label)
            continue
        kind = ticket.get("type", ticket.get("bet_type"))
        frame_ticket = kind == "FRAME_QUINELLA"
        legs = ticket.get("frame_nos" if frame_ticket else "horse_nos")
        known = set(frame_counts) if frame_ticket else numbers
        stake = ticket.get("stake_yen")
        if (kind not in TICKET_LEGS or not isinstance(legs, list) or
                len(legs) != TICKET_LEGS.get(kind) or
                any(type(n) is not int or n not in known for n in legs) or
                (not frame_ticket and len(set(legs)) != len(legs)) or
                (frame_ticket and len(set(legs)) == 1 and frame_counts.get(legs[0], 0) < 2) or
                (frame_ticket and "horse_nos" in ticket and ticket["horse_nos"] != []) or
                (not frame_ticket and "frame_nos" in ticket and ticket["frame_nos"] != []) or
                type(stake) is not int or stake < 100 or stake % 100):
            errors.append("INVALID_TICKET:" + label)


def _paper(paper, race_id, expected_hash, latest_final, published, now, errors):
    try:
        if (paper["race_id"] != race_id or not _hash(expected_hash) or
                paper["content_hash"] != expected_hash):
            raise ValueError("paper binding")
        if paper["manifest_hash"] != content_hash({k: v for k, v in paper.items() if k != "manifest_hash"}):
            raise ValueError("paper manifest integrity")
        qa = paper["qa"]
        if qa["qa_hash"] != content_hash({k: v for k, v in qa.items() if k != "qa_hash"}):
            raise ValueError("QA integrity")
        if (qa["status"] != "VERIFIED" or not _text(qa["reviewer"]) or
                not _text(qa["notes"]) or qa["writing_mode"] != "vertical-rl" or
                type(qa["pages"]) is not int or qa["pages"] < 1 or
                qa["pages"] != len(paper["images"]) or
                len({image["path"] for image in paper["images"]}) != qa["pages"]):
            raise ValueError("all-page visual QA required")
        mechanical = qa["mechanical_checks"]
        if (mechanical.get("passed") is not True or mechanical.get("font_ready") is not True or
                mechanical.get("all_text_retained") is not True or mechanical.get("errors") != [] or
                mechanical.get("pages") != qa["pages"]):
            raise ValueError("mechanical all-page checks required")
        generated, checked = _time(paper["generated_at"]), _time(qa["checked_at"])
        if not latest_final <= generated <= checked <= published <= now:
            raise ValueError("paper sequence")
        for artifact, magic in [(paper["pdf"], b"%PDF-"),
                                *((image, b"\x89PNG\r\n\x1a\n") for image in paper["images"])]:
            data = Path(artifact["path"]).read_bytes()
            if not data.startswith(magic) or sha256(data).hexdigest() != artifact["sha256"]:
                raise ValueError("paper file integrity")
    except (KeyError, TypeError, ValueError, OSError, AttributeError):
        errors.append("PAPER_PDF_IMAGE_QA_UNVERIFIED")


def check_publication(race, preliminary, discussions, final, published_at, *,
                      required_forecasters=None, character_snapshot_hash=None,
                      execution_receipts=None, paper=None, publication_content_hash=None,
                      checked_at=None):
    """Fail closed unless complete independent predictions precede a reviewed paper.

    ``execution_receipts`` maps execution IDs to complete provider result objects
    with ``persisted_at`` supplied after durable output storage. Topic records have
    distinct ``topic_id``/``title``, start/end times, fixed facilitator/newcomer,
    and ``turns`` containing the provider RESPONSE outputs.
    """
    errors = []
    race_id = race.get("race_id") if isinstance(race, dict) else None
    try:
        start, published = _time(race["start_at"]), _time(published_at)
        now = _time(checked_at) if checked_at is not None else datetime.now(timezone.utc)
    except (KeyError, TypeError, ValueError):
        return {"ready": False, "errors": ["INVALID_PUBLICATION_TIMESTAMP"], "race_id": race_id}
    if published.astimezone(JST).date() >= start.astimezone(JST).date():
        errors.append("LATE_PUBLICATION")
    if published >= start:
        errors.append("POST_START")
    if published > now:
        errors.append("FUTURE_PUBLICATION")
    required = required_forecasters if required_forecasters is not None else race.get("required_forecasters")
    if (not isinstance(required, (list, tuple)) or not required or
            any(not _text(a) for a in required) or len(set(required)) != len(required)):
        errors.append("REQUIRED_FORECASTERS_MISSING")
        required = []
    snapshot = character_snapshot_hash or race.get("character_snapshot_hash")
    if not _hash(snapshot):
        errors.append("CHARACTER_SNAPSHOT_UNBOUND")
    if race.get("declaration_stage") != "DRAW_CONFIRMED":
        errors.append("DRAW_NOT_CONFIRMED")
    receipts = execution_receipts if isinstance(execution_receipts, dict) else {}
    runners = race.get("runners")
    if (not isinstance(runners, list) or not runners or
            any(not isinstance(r, dict) or type(r.get("horse_no")) is not int or
                r["horse_no"] < 1 or not _text(r.get("name", r.get("horse_name"))) for r in runners)):
        errors.append("RUNNERS_MISSING")
        numbers = set()
    else:
        numbers = {r["horse_no"] for r in runners}
        if len(numbers) != len(runners):
            errors.append("DUPLICATE_RUNNERS")
        if any(type(r.get("frame_no")) is not int or not 1 <= r["frame_no"] <= 8 for r in runners):
            errors.append("RUNNER_DRAW_INCOMPLETE")
    horse_numbers = {r["horse_id"]: r["horse_no"] for r in (runners or [])
                     if isinstance(r, dict) and _text(r.get("horse_id")) and
                     type(r.get("horse_no")) is int}
    frame_counts = {}
    for runner in (runners or []):
        if isinstance(runner, dict) and type(runner.get("frame_no")) is int and 1 <= runner["frame_no"] <= 8:
            frame_counts[runner["frame_no"]] = frame_counts.get(runner["frame_no"], 0) + 1
    pre_times, final_times = [], []
    for group, stage, times in [(preliminary, "PRELIMINARY", pre_times), (final, "FINAL", final_times)]:
        if not isinstance(group, dict) or not group:
            errors.append(stage + "_MISSING")
            group = {}
        if set(group) != set(required):
            errors.append(stage + "_FORECASTER_COVERAGE")
        for author, record in group.items():
            if not _text(author):
                errors.append("INVALID_FORECASTER_ID")
                continue
            try:
                _forecast(record, author, numbers, horse_numbers, frame_counts, errors, stage)
            except (KeyError, TypeError, ValueError):
                errors.append("MALFORMED_FORECAST:" + stage + ":" + author)
            at = _execution(record, author, stage, receipts, race_id, snapshot, now, errors)
            if at is not None:
                times.append(at)
                if at > published:
                    errors.append("FORECAST_AFTER_PUBLICATION:" + stage + ":" + author)
            if stage == "FINAL" and at is not None:
                context = receipts[record["execution_id"]]["context"]
                if context.get("preliminary") != preliminary or context.get("discussions") != discussions:
                    errors.append("FINAL_INPUT_DEPENDENCY_MISMATCH:" + author)
            if stage == "FINAL" and isinstance(preliminary, dict) and author in preliminary:
                initial = preliminary[author]
                if (isinstance(record, dict) and isinstance(initial, dict) and
                        any(record.get(k) != initial.get(k) for k in ("picks", "tickets", "skip_reason")) and
                        not _text(record.get("change_reason"))):
                    errors.append("CHANGE_REASON_REQUIRED:" + author)
    topic_ids, titles, response_authors, discussion_times = set(), set(), set(), []
    response_texts = set()
    if not isinstance(discussions, list) or len(discussions) < 5:
        errors.append("DISCUSSION_TOPICS_LT_5")
        discussions = discussions if isinstance(discussions, list) else []
    for topic_index, topic in enumerate(discussions):
        try:
            topic_id, title = topic["topic_id"], topic["title"]
            if not _text(topic_id) or not _text(title) or topic_id in topic_ids or title.strip() in titles:
                raise ValueError("distinct substantive topic required")
            topic_ids.add(topic_id); titles.add(title.strip())
            began, ended = _time(topic["started_at"]), _time(topic["completed_at"])
            if (not began <= ended <= published <= now or not pre_times or
                    began < max(pre_times) or
                    topic["facilitator"] != "SHINOMIYA_RITSU" or topic["newcomer"] != "RIO"):
                raise ValueError("topic order/roles")
            turns = topic["turns"]
            if not isinstance(turns, list) or not turns:
                raise ValueError("topic text required")
            authors = set()
            for turn_index, turn in enumerate(turns):
                author = turn["forecaster_id"]
                if author not in required or not _text(turn.get("text")) or author in authors:
                    raise ValueError("topic specialist response")
                normalized_text = "".join(turn["text"].split())
                if normalized_text in response_texts:
                    raise ValueError("duplicate response text is not a substantive discussion")
                response_texts.add(normalized_text)
                authors.add(author)
                at = _execution(turn, author, "RESPONSE", receipts, race_id, snapshot, now, errors)
                if at is None or not began <= at <= ended:
                    raise ValueError("response time")
                context = receipts[turn["execution_id"]]["context"]
                if (context.get("preliminary") != preliminary or
                        context.get("topic") != {"topic_id": topic_id, "title": title} or
                        context.get("prior_turns") != turns[:turn_index] or
                        context.get("previous_topics") != discussions[:topic_index]):
                    raise ValueError("response input dependency mismatch")
            if authors != set(required):
                raise ValueError("all specialists must participate in every topic")
            response_authors.update(authors)
            discussion_times.append(ended)
        except (KeyError, TypeError, ValueError, AttributeError):
            errors.append("INVALID_DISCUSSION_TOPIC")
    if len(topic_ids) < 5:
        errors.append("FIVE_DISTINCT_TOPICS_REQUIRED")
    if set(required) != response_authors:
        errors.append("DISCUSSION_FORECASTER_COVERAGE")
    if not final_times or not discussion_times or min(final_times) < max(discussion_times):
        errors.append("FINAL_BEFORE_DISCUSSION_COMPLETE")
    _paper(paper, race_id, publication_content_hash, max(final_times) if final_times else published,
           published, now, errors)
    return {"ready": not errors, "errors": sorted(set(errors)), "race_id": race_id,
            "source_authenticity_verified": False}


def append_revision(history, revision, *, legacy=False):
    """Return an isolated append; strict revisions preserve a hashed pre-day base.

    ``legacy=True`` only replays old version/time records and does not establish
    eligibility for operational publication. Strict deltas carry ``base_sha256``,
    ``previous_sha256``, ``race_id``, ``changes`` and a nonempty ``change_reason``.
    """
    if not isinstance(history, list) or not history:
        raise ValueError("previous-day version required")
    if not isinstance(revision, dict) or any(x["version"] == revision.get("version") for x in history):
        raise ValueError("duplicate or missing version")
    if not _text(revision.get("version")) or _time(revision["saved_at"]) <= _time(history[-1]["saved_at"]):
        raise ValueError("revision timestamp must increase")
    if not legacy:
        base_hash = content_hash(history[0])
        for index, prior in enumerate(history[1:], start=1):
            if (prior.get("base_sha256") != base_hash or
                    prior.get("previous_sha256") != content_hash(history[index - 1]) or
                    prior.get("race_id") != history[0].get("race_id") or
                    _time(prior["saved_at"]) <= _time(history[index - 1]["saved_at"])):
                raise ValueError("existing revision history integrity mismatch")
        if (revision.get("base_sha256") != base_hash or
                revision.get("previous_sha256") != content_hash(history[-1]) or
                not _text(revision.get("race_id")) or revision["race_id"] != history[0].get("race_id")):
            raise ValueError("revision must bind unchanged previous-day base and prior version")
        changes = revision.get("changes")
        if (not isinstance(changes, dict) or not changes or not set(changes) <= DAY_DELTA_FIELDS or
                not _text(revision.get("change_reason"))):
            raise ValueError("only reasoned day-of deltas are allowed")
        if set(revision) - {"version", "saved_at", "race_id", "base_sha256", "previous_sha256",
                            "changes", "change_reason", "content_hash"}:
            raise ValueError("revision cannot replace preceding-day predictions")
        if "content_hash" in revision and revision["content_hash"] != content_hash({k: v for k, v in revision.items() if k != "content_hash"}):
            raise ValueError("revision integrity mismatch")
    return deepcopy([*history, revision])
