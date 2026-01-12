"""Test script to verify Langfuse connection and send a test trace."""
import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 50)
print("Langfuse Connection Test (v3 SDK)")
print("=" * 50)

# Check environment variables
print("\n1. Checking environment variables:")
public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
secret_key = os.getenv("LANGFUSE_SECRET_KEY")
host = os.getenv("LANGFUSE_HOST")
tracing = os.getenv("LANGFUSE_TRACING")
logging_env = os.getenv("LANGFUSE_LOGGING")

print(f"   LANGFUSE_PUBLIC_KEY: {'[OK] Set' if public_key else '[ERROR] Not set'}")
print(f"   LANGFUSE_SECRET_KEY: {'[OK] Set' if secret_key else '[ERROR] Not set'}")
print(f"   LANGFUSE_HOST: {host or '[ERROR] Not set'}")
print(f"   LANGFUSE_TRACING: {tracing}")
print(f"   LANGFUSE_LOGGING: {logging_env}")

if not all([public_key, secret_key, host]):
    print("\n[ERROR] Missing required environment variables!")
    exit(1)

# Test Langfuse client using v3 SDK
print("\n2. Testing Langfuse client initialization (v3 SDK):")
try:
    from langfuse._client.get_client import get_client

    client = get_client()
    print("   [OK] Langfuse client initialized successfully via get_client()")
except Exception as e:
    print(f"   [ERROR] Failed to initialize Langfuse client: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Send a test trace using v3 SDK
print("\n3. Sending test trace using v3 SDK:")
try:
    # In v3 SDK, we use spans and generations directly
    from langfuse._client.span import LangfuseSpan

    # Create a trace (span) directly from the client
    span = client.start_observation(
        name="test-connection-trace",
        as_type="span",
        input={"test": True, "source": "connection_test_script"},
        metadata={"test_run": True},
    )

    # Update trace attributes
    span.update_trace(
        user_id="test-user",
        session_id="test-session",
        tags=["test", "connection-verification"],
    )

    # Add a child generation
    generation = span.start_observation(
        name="test-generation",
        as_type="generation",
        input="Test input message",
        model="test-model",
    )
    generation.update(
        output="Test output response",
        usage={"input": 10, "output": 20},
    )
    generation.end()

    # End the main span
    span.update(output={"result": "success"})
    span.end()

    print(f"   [OK] Test trace created with ID: {span.trace_id}")
    print(f"   Trace URL: {host}/trace/{span.trace_id}")

except Exception as e:
    print(f"   [ERROR] Failed to create test trace: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Flush the client to ensure data is sent
print("\n4. Flushing data to Langfuse:")
try:
    client.flush()
    print("   [OK] Data flushed successfully")
except Exception as e:
    print(f"   [ERROR] Failed to flush data: {e}")
    import traceback
    traceback.print_exc()

# Shutdown
print("\n5. Shutting down client:")
try:
    client.shutdown()
    print("   [OK] Client shutdown successfully")
except Exception as e:
    print(f"   [WARNING] Shutdown: {e}")

print("\n" + "=" * 50)
print("Test completed! Check your Langfuse dashboard for the test trace.")
print(f"Dashboard URL: {host}")
print("=" * 50)
