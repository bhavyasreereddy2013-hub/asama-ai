import math
import re
from collections.abc import Iterable
from datetime import datetime
from threading import Lock

from fastembed import TextEmbedding

EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
_embedding_model: TextEmbedding | None = None
_embedding_model_lock = Lock()


def get_embedding_model() -> TextEmbedding:
    global _embedding_model
    if _embedding_model is None:
        with _embedding_model_lock:
            if _embedding_model is None:
                _embedding_model = TextEmbedding(model_name=EMBEDDING_MODEL_NAME)
    return _embedding_model


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    left_values = tuple(float(value) for value in left)
    right_values = tuple(float(value) for value in right)
    if len(left_values) != len(right_values):
        raise ValueError("Embedding vectors must have the same dimensions")
    numerator = math.fsum(a * b for a, b in zip(left_values, right_values))
    left_norm = math.sqrt(math.fsum(value ** 2 for value in left_values))
    right_norm = math.sqrt(math.fsum(value ** 2 for value in right_values))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def describe_match(query: str, agent, profile, recent_posts: list) -> list[str]:
    query_terms = list(dict.fromkeys(tokenize(query)))
    query_set = set(query_terms)
    agent_terms = set(tokenize(" ".join([
        agent.name or "",
        agent.summary or "",
        agent.business_goals or "",
        agent.interests or "",
    ])))
    profile_terms = set(tokenize(" ".join([
        profile.company_name or "" if profile else "",
        profile.industry or "" if profile else "",
        profile.description or "" if profile else "",
        profile.products or "" if profile else "",
        profile.services or "" if profile else "",
        profile.requirements or "" if profile else "",
        profile.interests or "" if profile else "",
    ])))
    update_terms = set(tokenize(" ".join(
        " ".join([post.title or "", post.description or "", post.requirements or "", post.category or ""])
        for post in recent_posts
    )))

    stop_words = {"a", "an", "and", "are", "for", "in", "is", "of", "our", "the", "to", "we", "with"}
    reasons = []
    industry = profile.industry if profile and profile.industry else agent.industry
    industry_matches = query_set & set(tokenize(industry or ""))
    if industry_matches:
        reasons.append(f"Industry alignment: {industry}.")

    location = agent.location or (profile.location if profile else "")
    location_matches = query_set & set(tokenize(location or ""))
    if location_matches:
        reasons.append(f"Location alignment: {location}.")

    profile_matches = [term for term in query_terms if term in profile_terms and term not in stop_words]
    if profile_matches:
        reasons.append(f"Business profile overlaps on: {', '.join(profile_matches[:5])}.")

    update_matches = [term for term in query_terms if term in update_terms and term not in stop_words]
    if update_matches:
        reasons.append(f"Recent updates mention: {', '.join(update_matches[:5])}.")

    agent_matches = [term for term in query_terms if term in agent_terms and term not in stop_words]
    if agent_matches:
        reasons.append(f"Agent goals or interests include: {', '.join(agent_matches[:5])}.")

    if not reasons:
        reasons.append("Embedding similarity found related business context.")
    return reasons


def rank_agents_for_query(query: str, agents: list) -> list[dict]:
    if not agents:
        return []

    agent_contexts = []
    documents = []
    for agent in agents:
        profile = agent.user.profile if agent.user else None
        recent_posts = sorted(
            agent.posts,
            key=lambda post: post.created_at or datetime.min,
            reverse=True,
        )[:5]
        agent_text = " ".join(
            [
                agent.name or "",
                agent.industry or "",
                agent.summary or "",
                agent.business_goals or "",
                agent.interests or "",
                agent.location or "",
            ]
        )
        profile_text = " ".join(
            [
                profile.company_name or "" if profile else "",
                profile.industry or "" if profile else "",
                profile.description or "" if profile else "",
                profile.products or "" if profile else "",
                profile.services or "" if profile else "",
                profile.requirements or "" if profile else "",
                profile.interests or "" if profile else "",
                profile.location or "" if profile else "",
            ]
        )
        updates_text = " ".join(
            " ".join([post.title or "", post.description or "", post.requirements or "", post.category or ""])
            for post in recent_posts
        )
        context = " ".join([agent_text, profile_text, updates_text])
        agent_contexts.append((agent, profile, recent_posts))
        documents.append(context)

    model = get_embedding_model()
    query_embeddings = list(model.query_embed(query))
    if not query_embeddings:
        raise RuntimeError("Embedding model returned no query vector")
    document_embeddings = list(model.passage_embed(documents))
    if len(document_embeddings) != len(agent_contexts):
        raise RuntimeError("Embedding model returned an unexpected number of vectors")

    query_embedding = query_embeddings[0]
    ranked = []
    for (agent, profile, recent_posts), embedding in zip(agent_contexts, document_embeddings):
        score = cosine_similarity(query_embedding, embedding)
        if score > 0:
            ranked.append({
                "agent_id": agent.id,
                "user_id": agent.user_id,
                "name": agent.name,
                "industry": agent.industry,
                "location": agent.location or (profile.location if profile else ""),
                "score": round(score, 4),
                "summary": agent.summary,
                "reasons": describe_match(query, agent, profile, recent_posts),
            })

    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked
