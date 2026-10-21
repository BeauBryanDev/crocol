import argparse
import asyncio
import base64
import time
from pathlib import Path

import bootstrap
from config.roles import MEMORY_TURNS

DESCRIPTION = (
    "Live smoke test: stream one question through the Crocol ask use case "
    "(graph, Postgres references and trace log), then read the saved trace "
    "back. Costs a few cents. "
    "Usage: magdalena/bin/python spikes/agent_smoke.py \"question\" "
    "[--image photo.jpg] [--follow-up \"next question\" ...]"
)


def print_node(event: dict) -> None:

    print(f"  {event['node']:<17} {event['status']:<8} "
          f"{event['duration_ms']:>6} ms  {event['summary']}")


def print_final(final: dict, seconds: float) -> None:

    print(f"\nSTATUS: {final['status']}  trace_id={final['trace_id']}  "
          f"({seconds:.1f} s)\n")
    print(final["answer"])
    if final["references"]:
        print("\nREFERENCES:")
        for reference in final["references"]:
            print(f"  - {reference}")
    if final["caveats"]:
        print("\nCAVEATS:")
        for caveat in final["caveats"]:
            print(f"  - {caveat}")


def save_overlay(final: dict) -> None:

    encoded = final.get("overlay_webp_b64")
    if not encoded:
        return
    target = Path("/tmp/claude-1000/-home-beaunix-Documents-VMM/"
                  "a3401ec2-130e-4167-a5d7-04d832a5f6f4/scratchpad/vision/"
                  "smoke_overlay.webp")
    target.write_bytes(base64.b64decode(encoded))
    print(f"\nOVERLAY saved: {target}")


def print_saved(saved: dict | None) -> None:

    if saved is None:
        print("\nSAVED TRACE: not found (Postgres unavailable?)")
        return

    stages: dict[str, int] = {}
    for row in saved["chunks"]:
        stages[row["stage"]] = stages.get(row["stage"], 0) + 1
    print(f"\nSAVED TRACE: status={saved['status']} "
          f"llm_calls={saved['llm_calls']} tokens_in={saved['tokens_in']} "
          f"tokens_out={saved['tokens_out']} latency={saved['latency_ms']} ms "
          f"cross_family={saved['cross_family']} chunks={stages}")


async def turn(ask, pool, question: str, image: bytes | None,
               history: list[dict]) -> dict:

    started = time.perf_counter()
    final: dict = {}
    async for event in ask.stream(question, image, None, history):
        if event["event"] == "node":
            print_node(event)
        final = event
    print_final(final, time.perf_counter() - started)
    save_overlay(final)
    saved = await bootstrap.build_get_trace(pool).run(final["trace_id"])
    print_saved(saved)
    return final


async def run(questions: list[str], image_path: str | None) -> None:

    pool = bootstrap.build_pool()
    if pool is None:
        raise SystemExit("PG_DSN is not set in .env")

    signer = bootstrap.build_memory_signer()
    async with pool:
        ask = bootstrap.build_ask(pool, signer=signer)
        image = Path(image_path).read_bytes() if image_path else None
        signed: list[dict] = []
        for number, question in enumerate(questions, 1):
            print(f"\n=== TURN {number}: {question}")
            history = []
            if signer:
                history = signer.verified(signed, int(time.time()),
                                          MEMORY_TURNS)
            final = await turn(ask, pool, question, image, history)
            image = None
            if final.get("memory"):
                signed = [*signed, final["memory"]][-MEMORY_TURNS:]


def main() -> None:

    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("question")
    parser.add_argument("--image", help="photo to analyze with the CNN")
    parser.add_argument("--follow-up", action="append", default=[],
                        help="next turn using Crocol's memory (repeatable)")
    args = parser.parse_args()
    asyncio.run(run([args.question, *args.follow_up], args.image))


if __name__ == "__main__":
    main()
