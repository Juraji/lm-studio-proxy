# Application Goal

> **Note:** This project will run locally on Linux and does not require Docker or GitHub Actions for deployment or CI.
> All tooling is kept minimal to simplify setup.


The project is a lightweight **proxy server** that forwards requests from an OpenAI‑compatible client to one of several
LM Studio instances. The goal is to make multiple LM Studio machines appear as a single endpoint so that tools such as
IntelliJ IDEA, VS Code or any other consumer can work with them without modification.

---

## High‑level Architecture

```
+------------------+          +---------------+          +---------------------+
|  Client (OpenAI) | <-----> |   Proxy API   | <-----> | LM Studio Instance A |
+------------------+          +---------------+          +---------------------+
                                          
                                         +---------------------+
                                         | LM Studio Instance B |
                                         +---------------------+
```

* **Client** – any OpenAI‑compatible library or UI.
* **Proxy API** – a small Python web server that receives requests, decides which LM Studio instance to forward them to
  and streams the response back.
* **LM Studio instances** – one or more machines running LM Studio with their own set of models.

---

## Configuration (YAML)

The proxy reads a `config.yaml` file that contains:

```yaml
# config.yaml example
instances:
  - name: fast‑model‑pc
    base_url: http://192.168.1.10:1234/v1   # LM Studio endpoint
    models: [ "llama-2-7b", "mistral" ]
  - name: large‑model‑pc
    base_url: http://192.168.1.11:5678/v1
    models: [ "llama-2-13b", "gpt4o-mini" ]
# Optional: default instance if no model match is found
fallback_instance: fast‑model‑pc
```

* **name** – human readable identifier.
* **base_url** – the LM Studio OpenAI‑compatible base URL.
* **models** – list of model names that this instance hosts.
* **fallback_instance** – used when a request’s `model` field does not match any configured instance.

---

## Routing Strategy

1. Parse the incoming request JSON and read the `model` key.
2. Look up the model in the configuration:
    * If found, forward to that instance.
    * If not found and a fallback is defined, use the fallback.
    * Otherwise return **400 Bad Request** with an informative message.
3. Forward the request body exactly as received, but change the `url` to point at the chosen instance’s `/v1/…`
   endpoint.
4. Preserve all headers that are relevant for authentication (e.g., `Authorization`).
5. Return the response verbatim – status code, headers and body.

---

## Streaming Support

LM Studio supports streaming via the OpenAI‑compatible API. The proxy must **not block** on a streaming response:

* Use an asynchronous web framework (FastAPI + `httpx.AsyncClient`).
* Forward the request with `stream=True`.
* As chunks arrive, yield them immediately to the client using the same event‑source format (`data: …\n\n`).
* Ensure that connection closures and timeouts are propagated correctly.

---

## Implementation Checklist

- [x] Create project scaffolding: main.py, proxy.py, config.py, tests/ directory
- [x] Write `requirements.txt` (and optionally pyproject.toml)
- [x] Implement configuration data models and loader (`config.py`)
- [x] Build FastAPI app in `proxy.py`, mount `/v1/*`
- [x] Implement instance selection logic
- [x] Forward non‑streaming requests via httpx.AsyncClient
- [x] Add streaming support (async generator)
- [x] Add error handling middleware (OpenAI style)
- [ ] Ensure graceful shutdown
- [x] Optional: add health‑check endpoint `/health`
- [ ] Add console logging for debugging
- [ ] Write unit tests (pytest + httpx testclient) covering routing, fallback, streaming
- [ ] Create virtual environment script `setup.sh`
- [ ] Document usage in README (config format, running steps, testing)
- [ ] Commit changes

