import os
import pytest
import requests
import time
import uuid
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Test configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:5001")
TEST_TIMEOUT = int(os.getenv("TEST_TIMEOUT", "60"))


@pytest.fixture(scope="module")
def api_client():
    """Fixture to provide a session for API requests."""
    session = requests.Session()
    
    # Check if API is available before running tests
    try:
        response = session.get(f"{API_BASE_URL}/health", timeout=5)
        response.raise_for_status()
        print(f"API health check passed: {response.json()}")
    except (requests.RequestException, ValueError) as e:
        pytest.skip(f"API is not available: {str(e)}")
    
    yield session
    session.close()


def test_browser_task_happy_path(api_client):
    """
    Happy path integration test for browser automation API.
    
    This test:
    1. Submits a simple task to the browser automation API
    2. Verifies the API responds correctly
    3. Checks that the response contains expected fields
    """
    # Test data
    test_task = "Go to https://example.com and get the title of the page"
    
    # Create a unique ID for this test run
    test_id = str(uuid.uuid4())[:8]
    print(f"Running test with ID: {test_id}")
    
    # 1. Submit task to API
    payload = {
        "task": test_task
    }
    
    start_time = time.time()
    print(f"Sending request to {API_BASE_URL}/agents")
    response = api_client.post(
        f"{API_BASE_URL}/agents",
        json=payload,
        timeout=TEST_TIMEOUT
    )
    
    # 2. Verify API response
    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}: {response.text}"
    
    # 3. Verify response structure
    response_data = response.json()
    assert "data" in response_data, "Response missing 'data' field"
    
    # Extract the result data
    result = response_data["data"]
    print(f"Received response: {result}")
    
    # 4. Verify result fields
    assert "task_id" in result, "Response missing task_id"
    assert "url" in result, "Response missing url field"
    assert "response" in result, "Response missing response field"
    assert "type" in result, "Response missing type field"
    assert "execution_time" in result, "Response missing execution_time field"
    
    # 5. Verify specific field values
    # assert result["url"] == "https://example.com", f"Expected URL to be example.com, got {result['url']}"
    assert result["type"] == "browser-use", f"Expected type to be 'browser-use', got {result['type']}"
    
    # 6. Print test metrics
    print(f"Task executed successfully in {result.get('execution_time', 'unknown')} seconds")
    print(f"Total test time: {time.time() - start_time:.2f} seconds")
    
    return result


def test_health_endpoint(api_client):
    """Test the health endpoint returns OK status."""
    response = api_client.get(f"{API_BASE_URL}/health")
    assert response.status_code == 200
    
    data = response.json()
    assert "status" in data
    assert data["status"] == "ok"


if __name__ == "__main__":
    # This allows running the test directly
    pytest.main(["-xvs", __file__])