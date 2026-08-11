"""
Tests for the in-memory product-existence cache in handlers.check_product_exists().

Context: check_product_exists() used to call DefectDojo's
GET /api/v2/products/?name=<name> on EVERY report import. DefectDojo's Product API
serializer embeds the full findings_list in the response, so against a product with a
large findings backlog this call got very slow (500ms-39s observed), and since it ran
unconditionally and very frequently, concurrently-slow calls saturated DefectDojo's
web workers and caused a crash loop. The fix caches confirmed-existing products
in-process so the expensive GET only ever needs to happen (at most) once per product
per operator run.
"""

from unittest.mock import MagicMock, patch

import pytest

import handlers


@pytest.fixture(autouse=True)
def clear_product_cache():
    """Keep each test isolated from the shared module-level cache."""
    handlers._known_existing_products.clear()
    yield
    handlers._known_existing_products.clear()


def _mock_response(count: int):
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"count": count}
    return response


def test_check_product_exists_caches_positive_result():
    """Once a product is confirmed to exist, later calls must not hit DefectDojo again."""
    with patch("handlers.requests.get", return_value=_mock_response(count=1)) as mocked_get:
        logger = MagicMock()

        assert handlers.check_product_exists("trivy-staging-marketplace", logger) is True
        assert handlers.check_product_exists("trivy-staging-marketplace", logger) is True
        assert handlers.check_product_exists("trivy-staging-marketplace", logger) is True

        mocked_get.assert_called_once()


def test_check_product_exists_rechecks_negative_result():
    """
    A not-yet-existing product is re-checked on every call (cheap: empty result set,
    no findings_list to serialize) until it is confirmed created - we must never cache
    a negative result permanently, or a freshly-created product would incorrectly keep
    being treated as missing (breaking the product_type_name auto-create logic).
    """
    with patch("handlers.requests.get", return_value=_mock_response(count=0)) as mocked_get:
        logger = MagicMock()

        assert handlers.check_product_exists("brand-new-product", logger) is False
        assert handlers.check_product_exists("brand-new-product", logger) is False

        assert mocked_get.call_count == 2


def test_check_product_exists_caches_independently_per_product_name():
    with patch("handlers.requests.get", return_value=_mock_response(count=1)) as mocked_get:
        logger = MagicMock()

        handlers.check_product_exists("product-a", logger)
        handlers.check_product_exists("product-b", logger)
        handlers.check_product_exists("product-a", logger)
        handlers.check_product_exists("product-b", logger)

        assert mocked_get.call_count == 2


def test_check_product_exists_still_returns_bool_on_error():
    """Behavior/return type must stay identical from the caller's perspective."""
    with patch("handlers.requests.get", side_effect=Exception("boom")):
        logger = MagicMock()

        result = handlers.check_product_exists("some-product", logger)

        assert result is False
        assert "some-product" not in handlers._known_existing_products
