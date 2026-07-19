"""True model version control — snapshots + append-only change journal.

Not chat history. Every *committed* state of the BIM model is a real version
with parent linkage, message, author, timestamp, and content hash. Working
copy can diverge; commit freezes truth. Diff shows element-level changes.

On-disk layout (next to model.llmbim.json)::

    <project_dir>/
      model.llmbim.json          # working tree (HEAD checkout + uncommitted)
      .llmbim/
        HEAD                     # current version id (or "unborn")
        journal.jsonl            # every mutation since (and across) commits
        refs.json                # named tags → version id
        versions/
          <version_id>.json      # full ProjectModel + commit metadata
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from llmbim_core.ids import new_id
from llmbim_core.model import ProjectModel


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _hash_model(data: dict[str, Any]) -> str:
    blob = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


@dataclass
class JournalEntry:
    """One mutation event (even if not yet committed)."""

    id: str
    ts: str
    op: str
    summary: dict[str, Any] = field(default_factory=dict)
    author: str = "agent"
    version_id: str | None = None  # filled when committed
    client_op_id: str | None = None


@dataclass
class CommitMeta:
    version_id: str
    parent_id: str | None
    message: str
    author: str
    ts: str
    content_hash: str
    stats: dict[str, int]
    journal_from: int  # inclusive index into journal at commit time
    journal_to: int  # exclusive


class ModelVCS:
    """Filesystem-backed version control for one project directory."""

    def __init__(self, project_dir: str | Path, *, model_filename: str = "model.llmbim.json") -> None:
        self.project_dir = Path(project_dir)
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.model_path = self.project_dir / model_filename
        self.meta_dir = self.project_dir / ".llmbim"
        self.versions_dir = self.meta_dir / "versions"
        self.journal_path = self.meta_dir / "journal.jsonl"
        self.head_path = self.meta_dir / "HEAD"
        self.refs_path = self.meta_dir / "refs.json"
        self.meta_dir.mkdir(parents=True, exist_ok=True)
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        if not self.head_path.exists():
            self.head_path.write_text("unborn\n", encoding="utf-8")
        if not self.refs_path.exists():
            self.refs_path.write_text("{}\n", encoding="utf-8")
        if not self.journal_path.exists():
            self.journal_path.write_text("", encoding="utf-8")

    # --- journal --------------------------------------------------------------

    def append_journal(
        self,
        op: str,
        summary: dict[str, Any] | None = None,
        *,
        author: str = "agent",
        client_op_id: str | None = None,
    ) -> JournalEntry:
        entry = JournalEntry(
            id=new_id("jrn"),
            ts=_utc_now(),
            op=op,
            summary=summary or {},
            author=author,
            client_op_id=client_op_id,
        )
        with self.journal_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry), default=str) + "\n")
        return entry

    def read_journal(self) -> list[dict[str, Any]]:
        if not self.journal_path.exists() or self.journal_path.stat().st_size == 0:
            return []
        lines = self.journal_path.read_text(encoding="utf-8").splitlines()
        out = []
        for line in lines:
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    # --- head / refs ----------------------------------------------------------

    def head(self) -> str | None:
        h = self.head_path.read_text(encoding="utf-8").strip()
        return None if h in ("", "unborn") else h

    def set_head(self, version_id: str) -> None:
        self.head_path.write_text(version_id + "\n", encoding="utf-8")

    def refs(self) -> dict[str, str]:
        return json.loads(self.refs_path.read_text(encoding="utf-8"))

    def tag(self, name: str, version_id: str | None = None) -> dict[str, str]:
        vid = version_id or self.head()
        if not vid:
            raise ValueError("No version to tag (commit first)")
        refs = self.refs()
        refs[name] = vid
        self.refs_path.write_text(json.dumps(refs, indent=2) + "\n", encoding="utf-8")
        self.append_journal("tag", {"name": name, "version_id": vid}, author="system")
        return {"name": name, "version_id": vid}

    # --- commit / checkout ----------------------------------------------------

    def commit(
        self,
        model: ProjectModel,
        message: str,
        *,
        author: str = "agent",
        allow_empty: bool = False,
    ) -> dict[str, Any]:
        """Freeze current model as a new version. Updates working copy file."""
        data = model.to_dict()
        content_hash = _hash_model(data)
        parent = self.head()

        # reject empty commit if hash matches parent
        if parent and not allow_empty:
            parent_data = self.load_version(parent)
            ph = (
                parent_data.get("content_hash")
                or parent_data.get("commit", {}).get("content_hash")
                or _hash_model(parent_data["model"])
            )
            if ph == content_hash:
                raise ValueError(
                    "No model changes since last commit "
                    f"({parent[:12]}…). Edit the model, then commit."
                )

        journal = self.read_journal()
        version_id = new_id("ver")
        meta = CommitMeta(
            version_id=version_id,
            parent_id=parent,
            message=message.strip() or "commit",
            author=author,
            ts=_utc_now(),
            content_hash=content_hash,
            stats=model.stats(),
            journal_from=0,
            journal_to=len(journal),
        )
        payload = {
            "commit": asdict(meta),
            "model": data,
        }
        path = self.versions_dir / f"{version_id}.json"
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        # stamp journal entries with version_id for this commit range
        self._stamp_journal(parent, version_id)

        self.set_head(version_id)
        model.save(self.model_path)
        # also write commit pointer note
        self.append_journal(
            "commit",
            {
                "version_id": version_id,
                "message": meta.message,
                "content_hash": content_hash,
                "parent_id": parent,
            },
            author=author,
        )
        return {
            "version_id": version_id,
            "parent_id": parent,
            "message": meta.message,
            "author": author,
            "ts": meta.ts,
            "content_hash": content_hash,
            "stats": meta.stats,
            "path": str(path),
        }

    def _stamp_journal(self, parent: str | None, version_id: str) -> None:
        """Mark uncommitted journal ops with this version_id."""
        entries = self.read_journal()
        changed = False
        for e in entries:
            if e.get("version_id") is None and e.get("op") not in ("commit", "checkout", "tag"):
                e["version_id"] = version_id
                changed = True
        if changed:
            with self.journal_path.open("w", encoding="utf-8") as f:
                for e in entries:
                    f.write(json.dumps(e, default=str) + "\n")

    def load_version(self, version_id: str) -> dict[str, Any]:
        # resolve tag
        refs = self.refs()
        if version_id in refs:
            version_id = refs[version_id]
        path = self.versions_dir / f"{version_id}.json"
        if not path.exists():
            # prefix match
            matches = list(self.versions_dir.glob(f"{version_id}*.json"))
            if len(matches) == 1:
                path = matches[0]
            else:
                raise FileNotFoundError(f"Version not found: {version_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def checkout(self, version_id: str, *, author: str = "agent") -> ProjectModel:
        """Restore working tree to a committed version (destroys uncommitted changes)."""
        payload = self.load_version(version_id)
        model = ProjectModel.from_dict(payload["model"])
        vid = payload["commit"]["version_id"]
        model.save(self.model_path)
        self.set_head(vid)
        self.append_journal(
            "checkout",
            {"version_id": vid, "message": payload["commit"].get("message")},
            author=author,
        )
        return model

    def log(self, *, limit: int = 50) -> list[dict[str, Any]]:
        """Newest-first commit log."""
        commits = []
        for path in sorted(self.versions_dir.glob("ver_*.json"), reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                c = data.get("commit", {})
                commits.append(
                    {
                        "version_id": c.get("version_id"),
                        "parent_id": c.get("parent_id"),
                        "message": c.get("message"),
                        "author": c.get("author"),
                        "ts": c.get("ts"),
                        "content_hash": c.get("content_hash", "")[:12],
                        "stats": c.get("stats"),
                    }
                )
            except (json.JSONDecodeError, OSError):
                continue
        # topological-ish by reading HEAD chain
        by_id = {c["version_id"]: c for c in commits if c.get("version_id")}
        chain: list[dict[str, Any]] = []
        cur = self.head()
        seen: set[str] = set()
        while cur and cur in by_id and cur not in seen:
            chain.append(by_id[cur])
            seen.add(cur)
            cur = by_id[cur].get("parent_id")
        # append any orphans
        for c in commits:
            if c.get("version_id") not in seen:
                chain.append(c)
        return chain[:limit]

    def status(self, model: ProjectModel) -> dict[str, Any]:
        """Working tree vs HEAD."""
        head = self.head()
        data = model.to_dict()
        h = _hash_model(data)
        if not head:
            return {
                "clean": False,
                "head": None,
                "working_hash": h[:12],
                "message": "No commits yet — working tree is unborn history",
                "journal_ops": len(self.read_journal()),
            }
        parent = self.load_version(head)
        ph = parent.get("content_hash") or _hash_model(parent["model"])
        clean = ph == h
        return {
            "clean": clean,
            "head": head,
            "head_message": parent.get("commit", {}).get("message"),
            "working_hash": h[:12],
            "head_hash": ph[:12],
            "message": "clean" if clean else "uncommitted model changes",
            "journal_ops": len(self.read_journal()),
            "diff_summary": None if clean else self.diff(head, model=model)["summary"],
        }

    def diff(
        self,
        version_a: str | None = None,
        version_b: str | None = None,
        *,
        model: ProjectModel | None = None,
    ) -> dict[str, Any]:
        """Element-level diff. Defaults: HEAD vs working tree."""
        if version_a is None:
            version_a = self.head()
        if version_a is None:
            return {
                "summary": {"added": 0, "removed": 0, "changed": 0},
                "added": [],
                "removed": [],
                "changed": [],
                "note": "no commits yet",
            }

        a_payload = self.load_version(version_a)
        a_model = a_payload["model"]

        if version_b is None and model is not None:
            b_model = model.to_dict()
            b_label = "working"
        elif version_b is None:
            if self.model_path.exists():
                b_model = json.loads(self.model_path.read_text(encoding="utf-8"))
                b_label = "working"
            else:
                b_model = a_model
                b_label = version_a
        else:
            b_payload = self.load_version(version_b)
            b_model = b_payload["model"]
            b_label = version_b

        return diff_models(a_model, b_model, label_a=version_a, label_b=b_label)


def diff_models(
    a: dict[str, Any],
    b: dict[str, Any],
    *,
    label_a: str = "a",
    label_b: str = "b",
) -> dict[str, Any]:
    """Compare two project dicts by element id."""
    a_els = {e["id"]: e for e in a.get("elements", [])}
    b_els = {e["id"]: e for e in b.get("elements", [])}
    a_ids, b_ids = set(a_els), set(b_els)

    added = []
    for i in sorted(b_ids - a_ids):
        e = b_els[i]
        added.append({"id": i, "category": e.get("category"), "name": e.get("name")})

    removed = []
    for i in sorted(a_ids - b_ids):
        e = a_els[i]
        removed.append({"id": i, "category": e.get("category"), "name": e.get("name")})

    changed = []
    for i in sorted(a_ids & b_ids):
        if _hash_model(a_els[i]) != _hash_model(b_els[i]):
            ae, be = a_els[i], b_els[i]
            fields = []
            for key in ("name", "category", "level_id", "host_id", "type_id", "params"):
                if ae.get(key) != be.get(key):
                    fields.append(key)
            changed.append(
                {
                    "id": i,
                    "category": be.get("category"),
                    "name": be.get("name"),
                    "fields": fields,
                }
            )

    # levels
    a_lv = {lv["name"]: lv for lv in a.get("levels", [])}
    b_lv = {lv["name"]: lv for lv in b.get("levels", [])}
    level_changes = {
        "added": sorted(set(b_lv) - set(a_lv)),
        "removed": sorted(set(a_lv) - set(b_lv)),
        "changed": [
            n
            for n in sorted(set(a_lv) & set(b_lv))
            if a_lv[n].get("elevation_mm") != b_lv[n].get("elevation_mm")
        ],
    }

    return {
        "label_a": label_a,
        "label_b": label_b,
        "summary": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
            "levels_added": len(level_changes["added"]),
            "levels_removed": len(level_changes["removed"]),
            "levels_changed": len(level_changes["changed"]),
        },
        "added": added,
        "removed": removed,
        "changed": changed,
        "levels": level_changes,
    }


def init_vcs(project_dir: str | Path, model: ProjectModel, *, message: str = "initial commit") -> ModelVCS:
    """Initialize VCS and create first commit."""
    vcs = ModelVCS(project_dir)
    model.save(vcs.model_path)
    vcs.commit(model, message, author="system", allow_empty=True)
    return vcs
