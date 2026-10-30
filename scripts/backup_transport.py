"""Private exact-pod TCP tunnel for recovery data; never expose a public service."""

import contextlib
import select
import socket
import subprocess
import time


@contextlib.contextmanager
def port_forward(resources, pod, remote):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        local = sock.getsockname()[1]
    process = subprocess.Popen(
        resources.kubectl
        + [
            "-n",
            resources.namespace,
            "port-forward",
            "pod/" + pod,
            f"{local}:{remote}",
            "--address=127.0.0.1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 30
        ready = False
        while time.monotonic() < deadline:
            readable, _, _ = select.select(
                [process.stdout, process.stderr],
                [],
                [],
                max(0, deadline - time.monotonic()),
            )
            if not readable:
                break
            for stream in readable:
                if stream.readline().startswith("Forwarding from 127.0.0.1:"):
                    ready = True
                    break
            if ready or process.poll() is not None:
                break
        if not ready:
            raise RuntimeError("Private exact-pod recovery tunnel did not start")
        yield f"http://127.0.0.1:{local}"
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
