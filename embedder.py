import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.preprocessing import normalize


_VECTOR_SIZE = 512

_vectorizer = HashingVectorizer(
    n_features=_VECTOR_SIZE,
    analyzer="char_wb",
    ngram_range=(2, 5),
    lowercase=True,
    alternate_sign=False,
    norm=None,
)


def embed_texts(texts: list[str]) -> np.ndarray:
    vectors = _vectorizer.transform(texts)
    vectors = normalize(vectors, norm="l2", copy=False)
    return vectors.astype("float32").toarray()
