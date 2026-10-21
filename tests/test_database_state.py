import os
from uuid import uuid4

import pytest

from app.database import state


def test_state_uses_json_files_without_database_url(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    monkeypatch.setattr(state, "_database_url", lambda: None)

    state.save_state("test", path, {"value": 1})

    assert state.load_state("test", path, {}) == {"value": 1}
    assert state.update_state(
        "test",
        path,
        {},
        lambda current: ({**current, "value": 2}, "updated"),
    ) == "updated"
    assert state.load_state("test", path, {}) == {"value": 2}


@pytest.mark.skipif(
    os.getenv("RUN_NEON_INTEGRATION_TESTS") != "1",
    reason="Set RUN_NEON_INTEGRATION_TESTS=1 to test the configured Neon database.",
)
def test_job_queue_persists_to_neon_through_api():
    from fastapi.testclient import TestClient

    from app.database.jobs import save_analysis
    from main import app

    assert state._database_url(), "DATABASE_URL must be configured for Neon integration tests."
    job_url = f"https://integration-test.invalid/{uuid4().hex}"
    saved = save_analysis(
        {
            "job_url": job_url,
            "title": "Neon persistence integration test",
            "company": "Test",
        },
        {"score": 87, "decision": "REVIEW"},
    )

    try:
        with TestClient(app) as client:
            queue_response = client.get("/api/jobs/queue")
            assert queue_response.status_code == 200
            assert any(job["id"] == saved["id"] for job in queue_response.json())

            status_response = client.patch(
                f"/api/jobs/queue/{saved['id']}/status",
                json={"status": "REVIEW"},
            )
            assert status_response.status_code == 200
            assert status_response.json()["status"] == "REVIEW"

            delete_response = client.delete(f"/api/jobs/queue/{saved['id']}")
            assert delete_response.status_code == 200
            assert delete_response.json() == {"deleted": True}

            queue_response = client.get("/api/jobs/queue")
            assert all(job["id"] != saved["id"] for job in queue_response.json())
    finally:
        from app.database.jobs import delete_job

        delete_job(saved["id"])
