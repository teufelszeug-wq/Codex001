"""Fail-closed editorial release gate for PRISM M-PAPER.

Research previews must never be labeled as production morning editions.
This is a necessary metadata gate, not a substitute for visual proofing.
"""
def validate_morning_edition(edition):
    errors = []
    if not isinstance(edition, dict):
        return {"approved": False, "errors": ["edition payload required"]}
    if edition.get("edition_type") != "MORNING_FINAL":
        errors.append("not a final morning edition")
    if edition.get("renderer_id") != "prism.mpaper.production":
        errors.append("approved production renderer not used")
    if edition.get("layout_qa", {}).get("vertical_all_pages") is not True:
        errors.append("vertical typesetting QA not passed")
    if edition.get("layout_qa", {}).get("visual_proof_reviewed") is not True:
        errors.append("rendered pages not visually reviewed")
    if edition.get("layout_qa", {}).get("horse_columns_complete") is not True:
        errors.append("horse columns incomplete")
    if edition.get("layout_qa", {}).get("newspaper_hierarchy_passed") is not True:
        errors.append("newspaper hierarchy QA not passed")
    if edition.get("forecast", {}).get("pre_off_saved") is not True:
        errors.append("pre-off forecast history not verified")
    if edition.get("forecast", {}).get("all_runners_covered") is not True:
        errors.append("full-field diagnoses incomplete")
    if edition.get("forecast", {}).get("independent_agents_verified") is not True:
        errors.append("independent specialist forecasts not verified")
    if edition.get("editorial", {}).get("five_topics_complete") is not True:
        errors.append("five-topic discussion incomplete")
    if edition.get("editorial", {}).get("character_db_verified") is not True:
        errors.append("character database not verified")
    if not edition.get("artifact", {}).get("pdf_path"):
        errors.append("actual PDF artifact missing")
    return {"approved": not errors, "errors": errors}
