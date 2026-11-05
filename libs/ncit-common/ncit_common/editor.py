"""Generic editor routes for dashboard-managed content (needs SQLAlchemy).

A service describes each kind of content once, as a "collection":

    COLLECTIONS = {
        "banners": {
            "model": Banner,            # SQLAlchemy model with id, published, sort_order, updated_at, updated_by
            "serialize": banner,        # fn(item, now) -> dict, including a "status" key
            "label": "banner",          # used in messages and audit entries
            "ordered": True,            # editors drag to reorder (sort_order); False = sorted by `order_by`
            "order_by": lambda m: [...],  # optional, for unordered collections
            "name_field": "title",      # shown in the audit log
            "fields": {...},            # ncit_common.fields.Field spec
            "filters": ("club_id",),    # optional: ?club_id=... narrows the list
        },
    }

and gets, for every collection, guarded by one role:

    GET    /<collection>?status=&q=   list (with status filter and search)
    POST   /<collection>              create
    PATCH  /<collection>/<id>         update (only the fields sent)
    DELETE /<collection>/<id>         delete
    POST   /<collection>/order        save a new order {"ids": [...]}
    POST   /uploads                   upload a photo (kind=image) or PDF (kind=pdf)

Every change is published as an event ("<collection>.created", ".updated",
".deleted", ".published", ".unpublished") for the audit log.

Hooks let a service add rules without copying the routes:
- check_rules(collection, item)      raise ApiError for invalid combinations
- before_create(collection, item)    fill derived fields (e.g. a slug)
- before_delete(collection, item)    refuse or clean up
"""

from datetime import UTC, datetime

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import func, select

from .auth import current_principal, require_role
from .errors import ApiError
from .fields import apply


def utcnow() -> datetime:
    return datetime.now(UTC)


def emit(event_type: str, *, entity: str, entity_id: str, data: dict | None = None) -> None:
    """Publish an audit event for the signed-in user; never blocks the request."""
    p = current_principal()
    try:
        current_app.config["EVENTS"].publish(
            event_type, actor={"id": p.user_id, "email": p.email}, entity=entity, entity_id=entity_id,
            data=data or {},
            ip=(request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.remote_addr or ""),
        )
    except Exception:  # an audit outage must not block editing
        current_app.logger.exception("could not publish %s", event_type)


def editor_blueprint(collections: dict, *, role: str, db, service: str, name: str = "editor",
                     check_rules=None, before_create=None, before_delete=None, upload_groups=None) -> Blueprint:
    """Build the editor blueprint. `db` is a function returning the request's session."""
    bp = Blueprint(name, __name__)
    upload_groups = set(upload_groups or collections)

    def _spec(collection: str) -> dict:
        spec = collections.get(collection)
        if spec is None:
            raise ApiError(404, "not_found", "Not found.")
        return spec

    def _emit(event_type: str, collection: str, item, data: dict | None = None) -> None:
        spec = collections[collection]
        emit(event_type, entity=collection, entity_id=item.id,
             data={"collection": collection, "label": spec["label"],
                   "name": getattr(item, spec["name_field"], ""), **(data or {})})

    def _sorted(spec: dict, stmt):
        model = spec["model"]
        if spec["ordered"]:
            return stmt.order_by(model.sort_order)
        if "order_by" in spec:
            return stmt.order_by(*spec["order_by"](model))
        return stmt.order_by(model.updated_at.desc())

    def _load(collection: str, item_id: str):
        spec = _spec(collection)
        item = db().get(spec["model"], item_id)
        if item is None:
            raise ApiError(404, "item_not_found", f"That {spec['label']} was already removed.")
        return spec, item

    def _rules(collection: str, item) -> None:
        if check_rules:
            check_rules(collection, item)

    @bp.get("/<collection>")
    @require_role(role)
    def list_items(collection):
        spec = _spec(collection)
        stmt = select(spec["model"])
        for key in spec.get("filters", ()):
            if request.args.get(key):
                stmt = stmt.where(getattr(spec["model"], key) == request.args[key])
        t = utcnow()
        items = [spec["serialize"](x, t) for x in db().scalars(_sorted(spec, stmt))]
        status = request.args.get("status")
        if status:
            items = [i for i in items if i["status"] == status]
        q = (request.args.get("q") or "").strip().lower()
        if q:
            items = [i for i in items if q in str(i.get(spec["name_field"], "")).lower()]
        return jsonify(items=items)

    @bp.post("/<collection>")
    @require_role(role)
    def create_item(collection):
        spec = _spec(collection)
        model = spec["model"]
        item = model(updated_by=current_principal().email)
        apply(item, spec["fields"], request.get_json(silent=True) or {}, partial=False)
        if before_create:
            before_create(collection, item)
        if spec["ordered"]:
            item.sort_order = (db().scalar(select(func.max(model.sort_order))) or 0) + 1
        _rules(collection, item)
        db().add(item)
        db().commit()
        _emit(f"{collection}.created", collection, item, {"published": item.published})
        return jsonify(item=spec["serialize"](item, utcnow())), 201

    @bp.patch("/<collection>/<item_id>")
    @require_role(role)
    def update_item(collection, item_id):
        spec, item = _load(collection, item_id)
        changed = apply(item, spec["fields"], request.get_json(silent=True) or {}, partial=True)
        if changed:
            _rules(collection, item)
            item.updated_by = current_principal().email
            db().commit()
            if changed == ["published"]:
                _emit(f"{collection}.{'published' if item.published else 'unpublished'}", collection, item)
            else:
                _emit(f"{collection}.updated", collection, item, {"fields": changed})
        return jsonify(item=spec["serialize"](item, utcnow()))

    @bp.delete("/<collection>/<item_id>")
    @require_role(role)
    def delete_item(collection, item_id):
        _, item = _load(collection, item_id)
        if before_delete:
            before_delete(collection, item)
        db().delete(item)
        db().commit()
        _emit(f"{collection}.deleted", collection, item)
        return jsonify(ok=True)

    @bp.post("/<collection>/order")
    @require_role(role)
    def reorder(collection):
        spec = _spec(collection)
        if not spec["ordered"]:
            raise ApiError(422, "not_ordered", "This list is sorted by date.")
        ids = (request.get_json(silent=True) or {}).get("ids") or []
        items = {x.id: x for x in db().scalars(select(spec["model"]))}
        if sorted(ids) != sorted(items):
            raise ApiError(422, "bad_order", "The list changed while you were editing. Reload and try again.")
        for position, item_id in enumerate(ids, start=1):
            items[item_id].sort_order = position
        db().commit()
        return jsonify(ok=True)

    @bp.post("/uploads")
    @require_role(role)
    def upload():
        """Upload a photo (kind=image) or a PDF (kind=pdf); returns its URL to save in a field."""
        from .media import save_image, save_pdf

        file = request.files.get("file")
        if file is None:
            raise ApiError(422, "no_file", "Choose a file to upload.")
        group = request.form.get("group", "misc")
        if group not in upload_groups:
            group = "misc"
        root = current_app.config["MEDIA_ROOT"]
        if request.form.get("kind") == "pdf":
            url = save_pdf(file, media_root=root, service=service, group=group)
        else:
            url = save_image(file, media_root=root, service=service, group=group)
        return jsonify(url=url), 201

    return bp
