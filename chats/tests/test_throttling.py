import pytest
import time
import os
import redis
from asgiref.sync import async_to_sync

REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))

THROTTLE_RATE = 5      
THROTTLE_PERIOD = 10   

@pytest.fixture(scope="module")
def redis_client():
    """Redis connection and cleanup for Throttling tests."""
    try:
        r = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        r.ping()        
        r.delete("throttle:test_user_limit") 
        r.delete("throttle:test_user_reset") 
        return r
    except redis.exceptions.ConnectionError:
        pytest.skip("Skipping Redis tests: Could not connect to Redis server.")
        return None

async def check_throttle_logic(redis_client, user_key):
    """
    Replicates the check_throttle logic from consumers.py for testing.
    (Note: The Redis client is explicitly passed).
    """
    if not redis_client:
        return False 
        
    key = f"throttle:{user_key}"
    now = time.time()    
    
    pipe = redis_client.pipeline()      
    pipe.zremrangebyscore(key, '-inf', now - THROTTLE_PERIOD)      
    pipe.zadd(key, {str(now): now})      
    pipe.expire(key, THROTTLE_PERIOD)      
    pipe.zcard(key)      
    
    results = pipe.execute()
    count = results[-1]
    
    return count > THROTTLE_RATE


def test_throttling_allows_calls_within_limit(redis_client):
    """Tests that 5 calls are allowed within the period."""
    user = "test_user_limit"
    
    # Try 5 calls 
    for i in range(THROTTLE_RATE):       
        is_throttled = async_to_sync(check_throttle_logic)(redis_client, user)
        assert is_throttled is False, f"Call {i+1} should not be throttled."

def test_throttling_blocks_calls_exceeding_limit(redis_client):
    """Tests that the sixth call is blocked."""
    user = "test_user_limit"    
    
    for i in range(THROTTLE_RATE):
        async_to_sync(check_throttle_logic)(redis_client, user)       
    
    is_throttled = async_to_sync(check_throttle_logic)(redis_client, user)
    assert is_throttled is True, "The sixth call MUST be throttled."


def test_throttling_resets_after_period(redis_client):
    """Tests that the limit is reset after the 10-second period."""
    user = "test_user_reset"    
    
    for _ in range(THROTTLE_RATE + 1):
        async_to_sync(check_throttle_logic)(redis_client, user)
            
    assert async_to_sync(check_throttle_logic)(redis_client, user) is True
    
    print(f"\nWaiting {THROTTLE_PERIOD} seconds for the reset...")
    
    time.sleep(THROTTLE_PERIOD + 0.5) 
        
    is_throttled = async_to_sync(check_throttle_logic)(redis_client, user)
    assert is_throttled is False, "After waiting the period, the new call should be allowed."