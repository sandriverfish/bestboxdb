from unittest.mock import patch

from redis import RedisError


def test_cache_config_defaults():
    from bestbox.adapters.cache.redis_cache import CacheConfig

    config = CacheConfig()

    assert config.redis_url == "redis://localhost:6379"
    assert config.ttl_sales_order_sec == 60
    assert config.ttl_stock_sec == 120
    assert config.ttl_low_stock_sec == 300


def test_redis_cache_get_returns_value():
    from bestbox.adapters.cache.redis_cache import CacheConfig, RedisCache

    with patch("bestbox.adapters.cache.redis_cache.Redis") as mock_redis:
        mock_client = mock_redis.from_url.return_value
        mock_client.get.return_value = '{"key": "value"}'

        cache = RedisCache(CacheConfig())

    assert cache.get("some:key") == '{"key": "value"}'


def test_redis_cache_get_returns_none_on_error():
    from bestbox.adapters.cache.redis_cache import CacheConfig, RedisCache

    with patch("bestbox.adapters.cache.redis_cache.Redis") as mock_redis:
        mock_client = mock_redis.from_url.return_value
        mock_client.get.side_effect = RedisError("connection refused")

        cache = RedisCache(CacheConfig())

    assert cache.get("some:key") is None


def test_redis_cache_set_calls_redis():
    from bestbox.adapters.cache.redis_cache import CacheConfig, RedisCache

    with patch("bestbox.adapters.cache.redis_cache.Redis") as mock_redis:
        mock_client = mock_redis.from_url.return_value
        cache = RedisCache(CacheConfig())

        cache.set("some:key", "value", 60)

    mock_client.set.assert_called_once_with("some:key", "value", ex=60)


def test_redis_cache_set_silently_ignores_error():
    from bestbox.adapters.cache.redis_cache import CacheConfig, RedisCache

    with patch("bestbox.adapters.cache.redis_cache.Redis") as mock_redis:
        mock_client = mock_redis.from_url.return_value
        mock_client.set.side_effect = RedisError("write failed")
        cache = RedisCache(CacheConfig())

        cache.set("some:key", "value", 60)


def test_redis_cache_ping_returns_true_on_success():
    from bestbox.adapters.cache.redis_cache import CacheConfig, RedisCache

    with patch("bestbox.adapters.cache.redis_cache.Redis") as mock_redis:
        mock_client = mock_redis.from_url.return_value
        mock_client.ping.return_value = True
        cache = RedisCache(CacheConfig())

    assert cache.ping() is True


def test_redis_cache_ping_returns_false_on_error():
    from bestbox.adapters.cache.redis_cache import CacheConfig, RedisCache

    with patch("bestbox.adapters.cache.redis_cache.Redis") as mock_redis:
        mock_client = mock_redis.from_url.return_value
        mock_client.ping.side_effect = RedisError("unreachable")
        cache = RedisCache(CacheConfig())

    assert cache.ping() is False


def test_redis_cache_invalidate_deletes_matching_keys():
    from bestbox.adapters.cache.redis_cache import CacheConfig, RedisCache

    with patch("bestbox.adapters.cache.redis_cache.Redis") as mock_redis:
        mock_client = mock_redis.from_url.return_value
        mock_client.scan_iter.return_value = ["bestbox:one", "bestbox:two"]
        mock_client.delete.return_value = 2
        cache = RedisCache(CacheConfig())

    assert cache.invalidate("bestbox:*") == 2
    mock_client.scan_iter.assert_called_once_with(match="bestbox:*")
    mock_client.delete.assert_called_once_with("bestbox:one", "bestbox:two")
