from app.document import chunk_document


def test_chunking_splits_long_text():
    text = " ".join(["This is a short sentence."] * 40)
    chunks = chunk_document(text)
    assert len(chunks) >= 2
    assert chunks[0]["index"] == 0
    assert chunks[1]["index"] == 1
    assert all(len(chunk["text"]) <= 600 for chunk in chunks)
