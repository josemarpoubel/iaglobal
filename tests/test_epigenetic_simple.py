import asyncio
import tempfile
import shutil
import hashlib
from pathlib import Path

# Import the epigenetic registry
from iaglobal.obsidian.epigenetic_registry import EpigeneticRegistry

# Create a temporary directory for testing
temp_dir = tempfile.mkdtemp()
print(f"Using temporary directory: {temp_dir}")

# Create the base path for the registry
base_path = Path(temp_dir) / "epigenetic"
base_path.mkdir(parents=True, exist_ok=True)

# Create the registry
registry = EpigeneticRegistry(base_path=base_path)

# Run a simple test
async def test():
    # Try to record a failure (this will create a .cbor file)
    task_hash = hashlib.sha3_512(b"test_task").hexdigest()[:16]
    context = {"test": "context"}
    
    epigenetic_id = await registry.record_failure(
        agent_id="test_agent",
        task_hash=task_hash,
        error_type="test_error",
        context=context
    )
    
    print(f"Recorded failure with epigenetic_id: {epigenetic_id}")
    
    # Check if the file was created
    file_path = base_path / f"{epigenetic_id}.cbor"
    if file_path.exists():
        print("SUCCESS: File was created")
    else:
        print("ERROR: File was not created")
    
    # Try to read it back
    with open(file_path, 'rb') as f:
        import cbor2
        data = cbor2.load(f)
        print(f"File content: {data}")
    
    # Clean up
    shutil.rmtree(temp_dir)

# Run the test
asyncio.run(test())
