"""This module contains functions for pdf processing and semantic search."""

import re
import fitz
from typing import Any
import urllib.request
import numpy as np
import tensorflow_hub as hub
from sklearn.neighbors import NearestNeighbors

recommender = None

def download_pdf(url, output_path) -> None:
    urllib.request.urlretrieve(url, output_path)


def preprocess(text) -> str:
    text = text.replace('\n', ' ')
    text = re.sub('\s+', ' ', text)
    return text


def pdf_to_text(path, start_page=1, end_page=None):
    doc = fitz.open(path)
    total_pages = doc.page_count

    if end_page is None:
        end_page = total_pages

    text_list = []

    for i in range(start_page - 1, end_page):
        text = doc.load_page(i).get_text("text")
        text = preprocess(text)
        text_list.append(text)

    doc.close()
    return text_list


def text_to_chunks(texts, word_length=150, start_page=1):
    text_toks = [t.split(' ') for t in texts]
    page_nums = []
    chunks = []

    for idx, words in enumerate(text_toks):
        for i in range(0, len(words), word_length):
            chunk = words[i : i + word_length]
            if (
                (i + word_length) > len(words)
                and (len(chunk) < word_length)
                and (len(text_toks) != (idx + 1))
            ):
                text_toks[idx + 1] = chunk + text_toks[idx + 1]
                continue
            chunk = ' '.join(chunk).strip()
            chunk = f'[Page no. {idx+start_page}]' + ' ' + '"' + chunk + '"'
            chunks.append(chunk)
    return chunks


class SemanticSearch:

    def __init__(self) -> None:
        self.use = hub.load('https://tfhub.dev/google/universal-sentence-encoder/4')
        self.fitted = False

    def fit(self, data, batch=2000, n_neighbors=10) -> None:
        self.data = data
        self.embeddings = self.get_text_embedding(data, batch=batch)
        n_neighbors = min(n_neighbors, len(self.embeddings))
        self.nn = NearestNeighbors(n_neighbors=n_neighbors)
        self.nn.fit(self.embeddings)
        self.fitted = True

    def __call__(self, text, return_data=True) -> Any:
        inp_emb = self.use([text])
        neighbors = self.nn.kneighbors(inp_emb, return_distance=False)[0]

        if return_data:
            return [self.data[i] for i in neighbors]
        else:
            return neighbors

    def get_text_embedding(self, texts, batch=2000) -> Any:
        embeddings = []
        for i in range(0, len(texts), batch):
            text_batch = texts[i : (i + batch)]
            emb_batch = self.use(text_batch)
            embeddings.append(emb_batch)
        embeddings = np.vstack(embeddings)
        return embeddings


def load_recommender(path, start_page=1)-> Any:
    global recommender
    if recommender is None:
        recommender = SemanticSearch()

    texts = pdf_to_text(path, start_page=start_page)
    chunks = text_to_chunks(texts, start_page=start_page)
    recommender.fit(chunks)
    return 'Corpus Loaded.'


def generate_answer(question)-> Any:
    topn_chunks = recommender(question)
    prompt = ""
    prompt += 'search results:\n\n'
    for c in topn_chunks:
        prompt += c + '\n\n'
    answer = prompt
    return answer