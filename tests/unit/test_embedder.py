from src.kb.embedder import E5Embedder


class RecordingModel:
    """Fake SentenceTransformer: records what it was given."""

    def __init__(self):
        self.seen: list[str] = []

    def encode(self, texts, normalize_embeddings=True, show_progress_bar=False):
        self.seen.extend(texts)
        return [[1.0, 0.0] for _ in texts]


def test_passages_get_passage_prefix():
    model = RecordingModel()
    embedder = E5Embedder(model=model)
    vectors = embedder.embed_passages(["Artículo 1198 texto"])
    assert model.seen == ["passage: Artículo 1198 texto"]
    assert vectors == [[1.0, 0.0]]


def test_queries_get_query_prefix():
    model = RecordingModel()
    embedder = E5Embedder(model=model)
    embedder.embed_query("plazo mínimo locación")
    assert model.seen == ["query: plazo mínimo locación"]


def test_no_unprefixed_encoding_is_exposed():
    embedder = E5Embedder(model=RecordingModel())
    assert not hasattr(embedder, "encode")


def test_concurrent_first_use_loads_the_model_once(monkeypatch):
    import sys
    import threading
    import time
    import types

    loads = []

    class SlowSentenceTransformer:
        def __init__(self, name):
            loads.append(name)
            time.sleep(0.05)

        def encode(self, texts, normalize_embeddings=True, show_progress_bar=False):
            return [[1.0, 0.0] for _ in texts]

    fake_module = types.ModuleType("sentence_transformers")
    fake_module.SentenceTransformer = SlowSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    embedder = E5Embedder(model_name="fake/model")
    threads = [
        threading.Thread(target=embedder.embed_query, args=("x",)) for _ in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert loads == ["fake/model"]


def test_concurrent_encoding_never_overlaps_inside_the_model():
    import threading
    import time

    state = {"active": 0, "overlap": False}
    guard = threading.Lock()

    class Model:
        def encode(self, texts, normalize_embeddings=True, show_progress_bar=False):
            with guard:
                state["active"] += 1
                if state["active"] > 1:
                    state["overlap"] = True
            time.sleep(0.01)
            with guard:
                state["active"] -= 1
            return [[1.0, 0.0] for _ in texts]

    embedder = E5Embedder(model=Model())
    threads = [
        threading.Thread(target=embedder.embed_query, args=(f"t{i}",)) for i in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert state["overlap"] is False
