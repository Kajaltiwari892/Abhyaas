import json
from pathlib import Path

from app.services.chapter_publication import validate_bundle

ROOT = Path(__file__).resolve().parents[1]


def test_versioned_sound_collection_has_exact_official_sources_and_local_scans():
    bundle = json.loads((ROOT / "data/chapter_questions/sound-waves-20261009.json").read_text())
    validate_bundle(bundle)
    archive = json.loads((ROOT / "data/upsc_paper_archive_20261001.json").read_text())
    sources = {
        (p["year"], p["cycle"], p["subject_slug"]): p["source_url"] for p in archive["papers"]
    }
    assert sum(len(p["questions"]) for p in bundle["papers"]) == 6
    for paper in bundle["papers"]:
        assert paper["source_url"] == sources[paper["year"], paper["cycle"], paper["subject_slug"]]
        for question in paper["questions"]:
            asset = (
                ROOT.parent
                / "Frontend/abhyaas/public/papers"
                / (
                    f"cds-{paper['cycle'].lower()}-{paper['year']}/{paper['subject_slug']}/page-{question['page']}.webp"
                )
            )
            assert asset.is_file()
            assert "correct_index" not in question
