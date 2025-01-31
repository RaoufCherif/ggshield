import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import pytest
from requests import Response


def create_json_response(json_data: Dict[str, Any], status_code: int = 200) -> Response:
    """Helper function to create a Response returned by the requests package containing
    JSON content. This is required because `requests.Response` does not provide an easy
    way to build a response manually.

    Can be used on its own or with RequestMock."""
    response = Response()
    response.headers = {"content-type": "application/json"}
    response.status_code = status_code
    response._content = json.dumps(json_data).encode("utf-8")
    return response


# See ExpectedRequest.data_checker
DataChecker = Callable[[Any], None]


@dataclass
class ExpectedRequest:
    """Stores an expected request and the response to return"""

    method: str
    endpoint: str
    response: Response

    # If defined, RequestMock will call this function with the value of the `data` field
    # it receives. It can be used to check the payload is as expected.
    data_checker: Optional[DataChecker] = None


class RequestMock:
    """
    Can be used to mock the `requests.Session.request()` method or the
    `requests.request()` from the requests package.

    Usage:

    ```python
    # Create the mock
    mock = RequestMock()

    # Install the mock
    monkeypatch.setattr("ggshield.core.client.Session.request", mock)

    # Add expected requests
    mock.add_GET("/foo1", JSONResponse({"a": 12}))
    mock.add_POST("/login", JSONResponse({"a": 12}))
    mock.add_GET("/not_found", JSONResponse({"msg": "no-such-page"}, 400))

    # Execute the code expected to send requests
    # If a request does not match the expected requests, an assert will raise
    my_code()

    # Verify the tested code sent all the requests
    mock.assert_all_requests_happened()
    ```
    """

    def __init__(self):
        self._requests: List[ExpectedRequest] = []

    def add_GET(
        self,
        endpoint: str,
        response: Response,
        data_checker: Optional[DataChecker] = None,
    ):
        self.add_request(ExpectedRequest("GET", endpoint, response, data_checker))

    def add_POST(
        self,
        endpoint: str,
        response: Response,
        data_checker: Optional[DataChecker] = None,
    ):
        self.add_request(ExpectedRequest("POST", endpoint, response, data_checker))

    def add_request(self, request: ExpectedRequest) -> None:
        """Low-level method to add a request, it's simpler to use add_GET or add_POST
        instead"""
        self._requests.append(request)

    def assert_all_requests_happened(self) -> None:
        assert self._requests == []

    def __call__(
        self, method: str, url: str, data: Optional[Any] = None, **kwargs: Any
    ) -> Response:
        """This method is called by the tested code. It pops the next expected request
        and checks it matches with the received request."""
        method = method.upper()

        # Get the expected request
        if not self._requests:
            pytest.fail(f"Unexpected call: {method} {url}")
        request = self._requests.pop(0)

        # Check the current request matches the expected one
        assert url.endswith(request.endpoint)
        assert method == request.method
        if request.data_checker:
            request.data_checker(data)

        return request.response
