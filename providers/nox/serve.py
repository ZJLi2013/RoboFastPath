from __future__ import annotations

import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from decision import DecisionModel


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve a Decision bundle over /v1/systemone")
    parser.add_argument("model_path")
    parser.add_argument("--served-model-name", default="Decision-1.0-Nox-4B")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=30001)
    args = parser.parse_args()

    model = DecisionModel.from_pretrained(
        args.model_path,
        device=args.device,
        local_files_only=True,
    )
    print(f"loaded {args.model_path}; runtime={json.dumps(model.runtime, default=str)}", flush=True)

    class Handler(BaseHTTPRequestHandler):
        def send_json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            if self.path.rstrip("/") != "/v1/systemone":
                self.send_json(404, {"error": f"unknown path: {self.path}"})
                return
            try:
                request = json.loads(
                    self.rfile.read(int(self.headers.get("Content-Length", 0)))
                )
                started = time.perf_counter()
                response = dict(model.decide(request["state"], request["questions"]))
            except (KeyError, TypeError, ValueError) as error:
                self.send_json(400, {"error": str(error)})
                return
            response["model"] = args.served_model_name
            response.setdefault("usage", {}).setdefault("output_tokens", 0)
            print(f"decide {1000 * (time.perf_counter() - started):.1f} ms", flush=True)
            self.send_json(200, response)

        def log_message(self, *_: object) -> None:
            pass

    print(f"serving on http://{args.host}:{args.port}/v1/systemone", flush=True)
    HTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
