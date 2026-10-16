from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

try:
    from .local_hashing_v14_1 import HASH_DIM, hashing_vector, normalize_text
except ImportError:
    from local_hashing_v14_1 import HASH_DIM, hashing_vector, normalize_text


STOPWORDS = {
    "toi", "minh", "em", "anh", "chi", "bac", "muon", "can", "hoi", "cho", "biet",
    "ve", "la", "thi", "va", "hoac", "cua", "co", "khong", "duoc", "lam", "the", "nao",
    "nhu", "gi", "mot", "cac", "nhung", "nay", "do", "o", "tai", "xin", "giup", "phai",
    "thu tuc", "ho so", "giay to",
}


INTENT_PATTERNS: Dict[str, Tuple[str, ...]] = {
    "documents": (
        "hồ sơ", "giấy tờ", "cần mang", "chuẩn bị gì", "nộp những gì", "cần những gì",
        "cần hồ sơ", "thành phần", "bản sao", "bản chính", "đơn gì", "tờ khai nào",
    ),
    "where": (
        "ở đâu", "đến đâu", "nộp chỗ nào", "nộp nơi nào", "cơ quan nào", "địa điểm",
        "trực tiếp", "bưu điện", "bưu chính", "nơi tiếp nhận",
    ),
    "online_steps": (
        "online", "trực tuyến", "qua mạng", "trên mạng", "dịch vụ công", "vneid",
        "đăng ký điện tử", "nộp điện tử",
    ),
    "time": (
        "bao lâu", "bao nhiêu ngày", "mấy ngày", "thời hạn", "thời gian giải quyết",
        "khi nào có", "chờ lâu", "ngày làm việc",
    ),
    "condition": (
        "điều kiện", "ai được", "đối tượng", "trường hợp nào", "có đủ điều kiện",
        "được đăng ký khi", "yêu cầu bắt buộc",
    ),
    "benefit": (
        "mức hưởng", "mức hỗ trợ", "được bao nhiêu", "nhận bao nhiêu", "hỗ trợ bao nhiêu", "số tiền",
        "tiền trợ cấp", "mức trợ cấp", "vay tối đa", "lãi suất",
    ),
    "fee": (
        "phí", "lệ phí", "chi phí", "tốn bao nhiêu", "phải đóng bao nhiêu",
        "mất bao nhiêu tiền", "thuế", "lệ phí trước bạ",
    ),
    "validity": (
        "hiệu lực", "có giá trị bao lâu", "hết hạn", "thời hạn giấy", "dùng được bao lâu",
    ),
    "authority": (
        "thẩm quyền", "ai xác minh", "cơ quan xác minh", "ai giải quyết", "đơn vị giải quyết",
    ),
    "steps": (
        "quy trình", "trình tự", "các bước", "làm thế nào", "làm sao", "bắt đầu từ đâu",
        "làm như thế nào", "làm ra sao", "thực hiện thế nào", "thực hiện ra sao",
        "cách thực hiện", "bằng cách nào",
    ),
    "legal": (
        "căn cứ", "luật nào", "nghị định nào", "thông tư nào", "quy định nào", "cơ sở pháp lý",
    ),
}


SECTION_MATCH: Dict[str, Tuple[str, ...]] = {
    "documents": ("documents", "documents_evidence", "documents_first_issue", "documents_reissue"),
    "where": ("where", "where_time"),
    "online_steps": ("online_steps", "where", "steps"),
    "time": ("time", "where_time"),
    "condition": ("condition", "scope"),
    "benefit": ("benefit",),
    "fee": ("fee",),
    "validity": ("validity",),
    "authority": ("authority", "where"),
    "steps": ("steps", "steps_first_issue", "steps_reissue", "online_steps"),
    "legal": ("general", "condition", "steps", "documents"),
}


LIST_PATTERNS = (
    "có những thủ tục nào", "có các thủ tục nào", "danh sách thủ tục", "những thủ tục gì",
    "các thủ tục gì", "tất cả thủ tục", "hỗ trợ việc gì", "giải quyết việc gì",
)


OUT_OF_SCOPE_PATTERNS = (
    "cấp số nhà", "xin số nhà", "đăng ký số nhà", "hộ chiếu", "passport",
    "giấy phép lái xe", "bằng lái xe", "đăng ký xe máy", "đăng ký ô tô",
    "lý lịch tư pháp",
)


@dataclass
class Route:
    kb_relevant: bool = False
    field: str = ""
    procedure_id: str = ""
    procedure_name: str = ""
    intents: List[str] = dataclass_field(default_factory=list)
    missing_intents: List[str] = dataclass_field(default_factory=list)
    confidence: float = 0.0
    margin: float = 0.0
    needs_clarification: bool = False
    clarification_reason: str = ""
    candidates: List[Dict[str, Any]] = dataclass_field(default_factory=list)
    candidate_procedures: List[str] = dataclass_field(default_factory=list)
    administrative_level: str = ""
    route_method: str = "local_hybrid_v14_1"
    is_list_query: bool = False


@dataclass
class Retrieval:
    route: Route
    hits: List[Dict[str, Any]]

    @property
    def kb_relevant(self) -> bool:
        return self.route.kb_relevant

    @property
    def low_confidence(self) -> bool:
        return self.route.needs_clarification or bool(self.route.missing_intents)


def phrase_present(norm_query: str, phrase: str) -> bool:
    p = normalize_text(phrase)
    return bool(p) and f" {p} " in f" {norm_query} "


def content_tokens(text: str) -> set[str]:
    return {x for x in normalize_text(text).split() if len(x) >= 2 and x not in STOPWORDS}


def lexical_overlap(query: str, candidate: str) -> float:
    q = content_tokens(query)
    c = content_tokens(candidate)
    if not q or not c:
        return 0.0
    common = len(q & c)
    return min(1.0, 0.55 * common / len(q) + 0.30 * common / len(c) + 0.15 * common / len(q | c))


def detect_intents(query: str) -> List[str]:
    q = normalize_text(query)
    found: List[str] = []
    for intent, phrases in INTENT_PATTERNS.items():
        if any(phrase_present(q, p) for p in phrases):
            found.append(intent)
    # Context corrections: a destination question should not also become a dossier question.
    if "where" in found and re.search(r"\b(nop|gui|mang)\b.{0,25}\b(o dau|den dau|cho nao|noi nao|co quan nao)\b", q):
        if not re.search(r"\b(ho so gom|can ho so|giay to nao|giay to gi|chuan bi gi|nop nhung gi|can nhung gi)\b", q):
            found = [x for x in found if x != "documents"]
    if "online_steps" in found and "where" in found and not re.search(r"\b(o dau|den dau|dia diem|co quan nao)\b", q):
        found = [x for x in found if x != "where"]
    if re.search(r"\b(phan anh|kien nghi|khieu nai)\b", q) and phrase_present(q, "bằng cách nào"):
        found = [x for x in found if x != "steps"]
        if "where" not in found:
            found.append("where")
    return found


class LocalHybridKBStoreV141:
    def __init__(self, kb_dir: Path):
        self.kb_dir = Path(kb_dir)
        self.meta: List[Dict[str, Any]] = json.loads((self.kb_dir / "kb_meta.json").read_text(encoding="utf-8"))
        self.catalog: List[Dict[str, Any]] = json.loads((self.kb_dir / "procedure_catalog.json").read_text(encoding="utf-8"))
        self.vectors = np.load(self.kb_dir / "kb_vectors.npy", allow_pickle=False).astype(np.float32)
        if self.vectors.shape != (len(self.meta), HASH_DIM):
            raise ValueError(f"Invalid KB vector shape: {self.vectors.shape}; metadata={len(self.meta)}")
        self.by_procedure: Dict[str, List[int]] = {}
        for i, row in enumerate(self.meta):
            self.by_procedure.setdefault(str(row["procedure_id"]), []).append(i)
        self.route_vectors = np.vstack([self._route_vector(row) for row in self.catalog]).astype(np.float32)

    @staticmethod
    def _route_text(row: Dict[str, Any]) -> str:
        aliases = " | ".join(str(x) for x in row.get("aliases", []))
        return f"{row.get('procedure_name', '')} | {aliases} | {row.get('field', '')}"

    def _route_vector(self, row: Dict[str, Any]) -> np.ndarray:
        return hashing_vector(self._route_text(row))

    def _field_score(self, query_norm: str, row: Dict[str, Any]) -> float:
        phrases = [row.get("field", "")] + list(row.get("field_aliases", []))
        lengths = [len(normalize_text(x).split()) for x in phrases if phrase_present(query_norm, str(x))]
        return min(0.12, 0.025 + 0.018 * max(lengths)) if lengths else 0.0

    def _alias_score(self, query_norm: str, row: Dict[str, Any]) -> Tuple[float, str]:
        phrases = [row.get("procedure_name", "")] + list(row.get("aliases", []))
        matched = [str(x) for x in phrases if phrase_present(query_norm, str(x))]
        if not matched:
            return 0.0, ""
        best = max(matched, key=lambda x: len(normalize_text(x).split()))
        count = len(normalize_text(best).split())
        return min(0.62, 0.38 + 0.055 * count), best

    def route(self, query: str) -> Route:
        query = (query or "").strip()
        if not query:
            return Route()
        qn = normalize_text(query)
        intents = detect_intents(query)
        if any(phrase_present(qn, p) for p in OUT_OF_SCOPE_PATTERNS):
            return Route(kb_relevant=False, intents=intents)
        is_list = any(phrase_present(qn, p) for p in LIST_PATTERNS)
        qv = hashing_vector(query)
        semantic = self.route_vectors @ qv
        candidates: List[Dict[str, Any]] = []
        for i, row in enumerate(self.catalog):
            alias_score, matched_alias = self._alias_score(qn, row)
            lexical = lexical_overlap(query, self._route_text(row))
            field_boost = self._field_score(qn, row)
            score = 0.56 * float(semantic[i]) + 0.34 * lexical + alias_score + field_boost
            candidates.append({
                "procedure_id": row["procedure_id"],
                "procedure_name": row["procedure_name"],
                "field": row["field"],
                "score": float(score),
                "semantic": float(semantic[i]),
                "lexical": lexical,
                "alias_score": alias_score,
                "matched_alias": matched_alias,
            })
        candidates.sort(key=lambda x: x["score"], reverse=True)
        best = candidates[0]
        second = candidates[1]
        margin = best["score"] - second["score"]
        strong_alias = best["alias_score"] >= 0.48
        relevant = bool(
            strong_alias
            or best["score"] >= 0.28
            or (best["score"] >= 0.245 and margin >= 0.05)
        )
        route = Route(
            kb_relevant=relevant,
            field=best["field"] if relevant else "",
            procedure_id=best["procedure_id"] if relevant else "",
            procedure_name=best["procedure_name"] if relevant else "",
            intents=intents,
            confidence=float(best["score"]),
            margin=float(margin),
            candidates=candidates[:5],
            candidate_procedures=[x["procedure_name"] for x in candidates[:5]],
            is_list_query=is_list,
        )
        if not relevant:
            return route
        if is_list:
            # A list query is field-level; procedure choice is not used.
            route.procedure_id = ""
            route.procedure_name = ""
            return route

        ambiguity_reason = ""
        if re.search(r"\b(chuyen nha|doi cho o|dang ky cho o)\b", qn) and not re.search(r"\b(tam tru|thuong tru|o han|o tam|o tro|nhap khau)\b", qn):
            ambiguity_reason = "Cần xác định người dân muốn đăng ký tạm trú hay thường trú."
        elif re.search(r"\b(thay doi|sua|cap nhat)\b.{0,30}\b(so do|so hong|giay chung nhan)\b", qn) and not re.search(r"\b(rach|nhoe|hong|mat|cu|doi mau)\b", qn):
            ambiguity_reason = "Cần xác định đây là đăng ký biến động hay cấp đổi giấy chứng nhận."
        elif phrase_present(qn, "mở quán ăn") and not re.search(r"\b(an toan thuc pham|ve sinh|attp|dang ky ho kinh doanh|kinh doanh ca the)\b", qn):
            ambiguity_reason = "Cần xác định người dân hỏi đăng ký hộ kinh doanh hay giấy chứng nhận an toàn thực phẩm."
        if ambiguity_reason:
            route.needs_clarification = True
            route.clarification_reason = ambiguity_reason
            return route

        # Exact, sufficiently specific aliases are decisive. Otherwise close procedures
        # must be clarified instead of silently mixing their evidence.
        top_alias = str(best.get("matched_alias", ""))
        alias_words = len(normalize_text(top_alias).split()) if top_alias else 0
        if not (strong_alias and alias_words >= 2) and margin < 0.035:
            route.needs_clarification = True
            route.clarification_reason = "Có nhiều thủ tục gần nghĩa; cần hỏi thêm để chọn đúng thủ tục."
        return route

    def _list_hits(self, route: Route) -> List[Dict[str, Any]]:
        return [
            {
                "content_type": "procedure_catalog",
                "field": row["field"],
                "procedure_id": row["procedure_id"],
                "procedure_name": row["procedure_name"],
                "section_name": "catalog",
                "text": row["procedure_name"],
                "score": 1.0,
            }
            for row in self.catalog if row["field"] == route.field
        ]

    @staticmethod
    def _section_priority(row: Dict[str, Any], intents: Sequence[str]) -> int:
        if not intents:
            return 1
        best = 0
        section = str(row.get("section_name", ""))
        tags = set(str(x) for x in row.get("intent_tags", []))
        for intent in intents:
            allowed = SECTION_MATCH.get(intent, ())
            if intent in tags:
                best = max(best, 7)
            elif section in allowed:
                best = max(best, len(allowed) - allowed.index(section) + 2)
        return best

    def retrieve(self, query: str, top_k: int = 6, min_sim: Optional[float] = None) -> Retrieval:
        route = self.route(query)
        if not route.kb_relevant or route.needs_clarification:
            return Retrieval(route=route, hits=[])
        if route.is_list_query:
            return Retrieval(route=route, hits=self._list_hits(route))
        indices = self.by_procedure.get(route.procedure_id, [])
        if not indices:
            return Retrieval(route=route, hits=[])
        qv = hashing_vector(query)
        scored: List[Tuple[float, int]] = []
        for idx in indices:
            row = self.meta[idx]
            section = str(row.get("section_name", ""))
            priority = self._section_priority(row, route.intents)
            sim = float(self.vectors[idx] @ qv)
            score = sim + 0.16 * priority
            # Prefer exact issue variants when the citizen says first issue/reissue.
            qn = normalize_text(query)
            if "lan dau" in qn and "first_issue" in section:
                score += 0.25
            if any(x in qn for x in ("cap doi", "doi lai", "bi rach", "hu hong")) and "reissue" in section:
                score += 0.25
            scored.append((score, idx))
        scored.sort(reverse=True)
        selected: List[int] = []
        # Guarantee at least one row for every requested intent when available.
        for intent in route.intents:
            eligible = [
                (s, i) for s, i in scored
                if intent in self.meta[i].get("intent_tags", [])
                or self.meta[i].get("section_name") in SECTION_MATCH.get(intent, ())
            ]
            if eligible and eligible[0][1] not in selected:
                selected.append(eligible[0][1])
            elif not eligible:
                route.missing_intents.append(intent)
        for _, idx in scored:
            if len(selected) >= top_k:
                break
            if idx not in selected:
                selected.append(idx)
        hits: List[Dict[str, Any]] = []
        score_map = {i: s for s, i in scored}
        for idx in selected[:top_k]:
            row = dict(self.meta[idx])
            row["score"] = float(score_map[idx])
            hits.append(row)
        return Retrieval(route=route, hits=hits)


def format_kb_block(retrieval: Retrieval) -> str:
    route = retrieval.route
    if not route.kb_relevant:
        return ""
    lines = [
        "=== KNOWLEDGE BASE V14.1 ===",
        f"field={route.field or 'unknown'}; procedure={route.procedure_name or 'unknown'}; "
        f"intents={','.join(route.intents) if route.intents else 'general'}; "
        f"missing_intents={','.join(route.missing_intents) if route.missing_intents else 'none'}; "
        f"NEEDS_CLARIFICATION={'true' if route.needs_clarification else 'false'}",
    ]
    if route.needs_clarification:
        lines.append(route.clarification_reason)
        lines.append("CANDIDATES: " + " | ".join(x["procedure_name"] for x in route.candidates[:3]))
        return "\n".join(lines)
    if not retrieval.hits:
        lines.append("NO VERIFIED EVIDENCE RETRIEVED. Do not invent administrative facts.")
        return "\n".join(lines)
    if route.missing_intents:
        lines.append(
            "IMPORTANT: The source document does not contain reliable information for: "
            + ", ".join(route.missing_intents)
            + ". State that this information is unavailable; do not infer or invent it."
        )
    for i, hit in enumerate(retrieval.hits, 1):
        lines.append(
            f"[{i}] procedure_id={hit.get('procedure_id','')}; procedure={hit.get('procedure_name','')}; "
            f"section={hit.get('section_name','')}\n{str(hit.get('text','')).strip()}"
        )
    return "\n".join(lines)
