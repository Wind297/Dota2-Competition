from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import AuthToken
from app.models import Tag
from app.schemas import TagCreate, TagOut, TagPatch

router = APIRouter(prefix="/api/tags", tags=["tags"])


@router.get("", response_model=list[TagOut])
def list_tags(
    _: AuthToken,
    db: Session = Depends(get_db),
    include_disabled: bool = False,
):
    q = select(Tag).order_by(Tag.sort_order, Tag.id)
    if not include_disabled:
        q = q.where(Tag.is_enabled.is_(True))
    return db.scalars(q).all()


@router.post("", response_model=TagOut)
def create_tag(body: TagCreate, _: AuthToken, db: Session = Depends(get_db)):
    label = body.label.strip()
    if not label:
        raise HTTPException(status_code=400, detail="标签不能为空")
    t = Tag(label=label, sort_order=body.sort_order, is_enabled=body.is_enabled)
    db.add(t)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="标签已存在")
    db.refresh(t)
    return t


@router.patch("/{tag_id}", response_model=TagOut)
def patch_tag(tag_id: int, body: TagPatch, _: AuthToken, db: Session = Depends(get_db)):
    t = db.get(Tag, tag_id)
    if not t:
        raise HTTPException(status_code=404, detail="标签不存在")
    if body.label is not None:
        new_label = body.label.strip()
        if not new_label:
            raise HTTPException(status_code=400, detail="标签不能为空")
        t.label = new_label
    if body.sort_order is not None:
        t.sort_order = body.sort_order
    if body.is_enabled is not None:
        t.is_enabled = body.is_enabled
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="标签名已被占用")
    db.refresh(t)
    return t


@router.delete("/{tag_id}")
def delete_tag(tag_id: int, _: AuthToken, db: Session = Depends(get_db)):
    """硬删除标签。会级联删除所有该标签的投票记录。
    通常更推荐改为 is_enabled=False 来"软禁用"。
    """
    t = db.get(Tag, tag_id)
    if not t:
        raise HTTPException(status_code=404, detail="标签不存在")
    db.delete(t)
    db.commit()
    return {"ok": True, "id": tag_id}
