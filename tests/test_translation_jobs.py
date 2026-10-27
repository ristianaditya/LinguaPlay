from linguaplay.translation_jobs import TranslationJob


def test_translation_job_resumes_from_manifest(tmp_path):
    calls = []
    job = TranslationJob(tmp_path / "job.json", ["one", "two"], lambda text: calls.append(text) or text.upper())
    assert job.run(max_units=1).completed_units == 1
    resumed = TranslationJob(tmp_path / "job.json", ["one", "two"], lambda text: text.upper())
    result = resumed.run()
    assert result.state == "completed"
    assert result.outputs == ["ONE", "TWO"]

