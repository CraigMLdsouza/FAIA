from fastapi.testclient import TestClient

from api import app


def test_rest_api_discovery_and_metadata_contract():
    with TestClient(app) as client:
        assert client.get("/health").json()["resolver_status"] == "VALIDATED"
        assert client.get("/version").status_code == 200
        assert client.get("/schema").status_code == 200
        assert client.get("/repository/github_com_upstash_context7").status_code == 200
        assert client.get("/provider/upstash").status_code == 200

        search = client.post("/search", json={"query": "context7"})
        assert search.status_code == 200
        assert search.json()["status"] == "SUCCESS"

        invalid_search = client.post("/search", json={"query": " "})
        assert invalid_search.status_code == 400
        assert invalid_search.json()["detail"]["error_code"] == "INVALID_QUERY"

        openapi = client.get("/openapi.json").json()
        assert openapi["info"]["title"] == "FAIA REST API"
