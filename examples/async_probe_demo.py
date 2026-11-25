import asyncio
from time import perf_counter

from app.services.probe import simulate_device_probe


async def main() -> None:
    device_ids = ["device-1", "device-2", "device-3"]

    start = perf_counter()
    sequential_results = [await simulate_device_probe(device_id) for device_id in device_ids]
    sequential_elapsed = perf_counter() - start

    start = perf_counter()
    concurrent_results = await asyncio.gather(
        *(simulate_device_probe(device_id) for device_id in device_ids)
    )
    concurrent_elapsed = perf_counter() - start

    print(f"Sequential results: {sequential_results}")
    print(f"Sequential elapsed: {sequential_elapsed:.3f} seconds")
    print(f"Concurrent results: {concurrent_results}")
    print(f"Concurrent elapsed: {concurrent_elapsed:.3f} seconds")


if __name__ == "__main__":
    asyncio.run(main())