import os
import pytest
import requests
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Test configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:5001")
TEST_TIMEOUT = int(os.getenv("TEST_TIMEOUT", "10"))  # Shorter timeout for error cases


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


class TestInvalidInputs:
    """Tests for invalid input handling in the browser automation API."""
    
    def test_empty_task(self, api_client):
        """Test API response when task is empty."""
        payload = {"task": ""}
        
        response = api_client.post(
            f"{API_BASE_URL}/agents",
            json=payload,
            timeout=TEST_TIMEOUT
        )
        
        # Verify error response
        assert response.status_code == 400, f"Expected status code 400, got {response.status_code}"
        
        error_data = response.json()
        assert "error" in error_data, "Response missing 'error' field"
        assert "task" in error_data["error"].lower(), "Error message should mention 'task'"
        
        print(f"Empty task test passed: {error_data['error']}")
    
    def test_missing_task(self, api_client):
        """Test API response when task parameter is missing."""
        payload = {}  # Empty payload
        
        response = api_client.post(
            f"{API_BASE_URL}/agents",
            json=payload,
            timeout=TEST_TIMEOUT
        )
        
        # Verify error response
        assert response.status_code == 400, f"Expected status code 400, got {response.status_code}"
        
        error_data = response.json()
        assert "error" in error_data, "Response missing 'error' field"
        assert "task" in error_data["error"].lower(), "Error message should mention 'task'"
        
        print(f"Missing task test passed: {error_data['error']}")
    
    def test_task_too_long(self, api_client):
        """Test API response when task is too long."""
        # Generate a very long task (assuming max length is 1000)
        long_task = "Go to example.com and check " + "a" * 2000
        
        payload = {"task": long_task}
        
        response = api_client.post(
            f"{API_BASE_URL}/agents",
            json=payload,
            timeout=TEST_TIMEOUT
        )
        
        # Verify error response
        assert response.status_code == 400, f"Expected status code 400, got {response.status_code}"
        
        error_data = response.json()
        assert "error" in error_data, "Response missing 'error' field"
        assert "length" in error_data["error"].lower() or "long" in error_data["error"].lower(), \
            "Error message should mention length"
        
        print(f"Task too long test passed: {error_data['error']}")
    
    def test_malformed_json(self, api_client):
        """Test API response when request has malformed JSON."""
        # Send malformed JSON in the request
        response = api_client.post(
            f"{API_BASE_URL}/agents",
            data="This is not JSON",
            headers={"Content-Type": "application/json"},
            timeout=TEST_TIMEOUT
        )
        
        # Verify error response
        assert response.status_code in [500, 400, 422], \
            f"Expected status code 400 or 422, got {response.status_code}"
        
        try:
            error_data = response.json()
            assert "error" in error_data, "Response missing 'error' field"
        except json.JSONDecodeError:
            # If response isn't JSON, that's acceptable too as long as status code is correct
            pass
        
        print(f"Malformed JSON test passed with status code: {response.status_code}")
    
    def test_wrong_http_method(self, api_client):
        """Test API response when using wrong HTTP method (GET instead of POST)."""
        response = api_client.get(
            f"{API_BASE_URL}/agents",
            timeout=TEST_TIMEOUT
        )
        
        # Should return method not allowed or similar
        assert response.status_code in [405, 404, 400, 501], \
            f"Expected error status code, got {response.status_code}"
        
        print(f"Wrong HTTP method test passed with status code: {response.status_code}")
    
    def test_invalid_content_type(self, api_client):
        """Test API response when using wrong content type."""
        response = api_client.post(
            f"{API_BASE_URL}/agents",
            data="task=Go to example.com",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=TEST_TIMEOUT
        )
        
        # Verify error response
        assert response.status_code != 200, \
            f"Expected non-200 status code, got {response.status_code}"
        
        print(f"Invalid content type test passed with status code: {response.status_code}")


if __name__ == "__main__":
    # This allows running the test directly
    pytest.main(["-xvs", __file__])