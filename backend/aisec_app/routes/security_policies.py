"""安全策略管理 API — CRUD + 模型绑定 + 场景查询"""
import json
import logging

from flask import Blueprint, current_app, jsonify, request

from ..db import db_cursor
from ..errors import DatabaseError, NotFoundError, ValidationError
from ..utils import normalize_datetimes

logger = logging.getLogger(__name__)

bp = Blueprint("security_policies", __name__)

# 预定义业务场景
SCENES = {
    "general": "通用场景",
    "finance": "金融客服",
    "medical": "医疗问答",
    "education": "教育辅导",
    "legal": "法律咨询",
    "ecommerce": "电商客服",
    "custom": "自定义场景",
}


# ==================== 策略 CRUD ====================

@bp.get("/api/policies")
def list_policies():
    """获取所有安全策略"""
    try:
        settings = current_app.config["AISEC_SETTINGS"]
        with db_cursor(settings) as (conn, cursor):
            cursor.execute("SELECT * FROM security_policies ORDER BY is_default DESC, scene, created_at DESC")
            policies = cursor.fetchall()
        return jsonify({"success": True, "data": normalize_datetimes(policies)})
    except Exception as e:
        logger.error(f"Failed to list policies: {e}", exc_info=True)
        raise DatabaseError("获取策略列表失败")


@bp.get("/api/policies/<int:policy_id>")
def get_policy(policy_id: int):
    """获取单个策略详情"""
    try:
        settings = current_app.config["AISEC_SETTINGS"]
        with db_cursor(settings) as (conn, cursor):
            cursor.execute("SELECT * FROM security_policies WHERE id = %s", (policy_id,))
            policy = cursor.fetchone()
        if not policy:
            raise NotFoundError("策略不存在")
        return jsonify({"success": True, "data": normalize_datetimes(policy)})
    except NotFoundError:
        raise
    except Exception as e:
        logger.error(f"Failed to get policy {policy_id}: {e}", exc_info=True)
        raise DatabaseError("获取策略详情失败")


@bp.post("/api/policies")
def create_policy():
    """创建安全策略"""
    try:
        data = request.json or {}
        name = (data.get("name") or "").strip()
        scene = (data.get("scene") or "general").strip()
        description = (data.get("description") or "").strip()
        prompt = (data.get("prompt") or "").strip()
        rules = data.get("rules")
        is_default = bool(data.get("is_default", False))

        if not name:
            raise ValidationError("策略名称不能为空")
        if not prompt:
            raise ValidationError("安全提示词不能为空")

        rules_json = json.dumps(rules, ensure_ascii=False) if rules else None

        settings = current_app.config["AISEC_SETTINGS"]
        with db_cursor(settings) as (conn, cursor):
            # 如果设为默认，先取消同场景的其他默认
            if is_default:
                cursor.execute(
                    "UPDATE security_policies SET is_default = FALSE WHERE scene = %s",
                    (scene,),
                )

            cursor.execute(
                """
                INSERT INTO security_policies (name, scene, description, prompt, rules, is_default)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (name, scene, description, prompt, rules_json, is_default),
            )
            conn.commit()
            new_id = cursor.lastrowid

        return jsonify({"success": True, "data": {"id": new_id}, "message": "策略创建成功"})
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Failed to create policy: {e}", exc_info=True)
        raise DatabaseError("创建策略失败")


@bp.put("/api/policies/<int:policy_id>")
def update_policy(policy_id: int):
    """更新安全策略"""
    try:
        data = request.json or {}
        settings = current_app.config["AISEC_SETTINGS"]
        with db_cursor(settings) as (conn, cursor):
            cursor.execute("SELECT id FROM security_policies WHERE id = %s", (policy_id,))
            if not cursor.fetchone():
                raise NotFoundError("策略不存在")

            fields = []
            values = []
            for key in ("name", "scene", "description", "prompt"):
                if key in data:
                    fields.append(f"{key} = %s")
                    values.append(data[key])
            if "rules" in data:
                fields.append("rules = %s")
                values.append(json.dumps(data["rules"], ensure_ascii=False) if data["rules"] else None)
            if "is_default" in data:
                is_default = bool(data["is_default"])
                fields.append("is_default = %s")
                values.append(is_default)
                # 如果设为默认，先取消同场景的其他默认
                if is_default:
                    scene = data.get("scene")
                    if not scene:
                        cursor.execute("SELECT scene FROM security_policies WHERE id = %s", (policy_id,))
                        row = cursor.fetchone()
                        scene = row["scene"] if row else "general"
                    cursor.execute(
                        "UPDATE security_policies SET is_default = FALSE WHERE scene = %s AND id != %s",
                        (scene, policy_id),
                    )

            if not fields:
                return jsonify({"success": True, "message": "无需更新"})

            values.append(policy_id)
            cursor.execute(
                f"UPDATE security_policies SET {', '.join(fields)} WHERE id = %s",
                values,
            )
            conn.commit()

        return jsonify({"success": True, "message": "策略更新成功"})
    except (NotFoundError, ValidationError):
        raise
    except Exception as e:
        logger.error(f"Failed to update policy {policy_id}: {e}", exc_info=True)
        raise DatabaseError("更新策略失败")


@bp.delete("/api/policies/<int:policy_id>")
def delete_policy(policy_id: int):
    """删除安全策略"""
    try:
        settings = current_app.config["AISEC_SETTINGS"]
        with db_cursor(settings) as (conn, cursor):
            cursor.execute("DELETE FROM security_policies WHERE id = %s", (policy_id,))
            conn.commit()
            if cursor.rowcount == 0:
                raise NotFoundError("策略不存在")
        return jsonify({"success": True, "message": "策略删除成功"})
    except NotFoundError:
        raise
    except Exception as e:
        logger.error(f"Failed to delete policy {policy_id}: {e}", exc_info=True)
        raise DatabaseError("删除策略失败")


# ==================== 场景列表 ====================

@bp.get("/api/policies/scenes")
def list_scenes():
    """获取所有预定义业务场景"""
    return jsonify({"success": True, "data": SCENES})


# ==================== 模型-策略绑定 ====================

@bp.get("/api/policies/bindings")
def list_bindings():
    """获取所有模型-策略绑定（可按 model_key 过滤）"""
    try:
        model_key = request.args.get("model_key")
        settings = current_app.config["AISEC_SETTINGS"]
        with db_cursor(settings) as (conn, cursor):
            if model_key:
                cursor.execute(
                    """
                    SELECT b.*, p.name AS policy_name, p.scene, p.prompt, p.is_default
                    FROM model_policy_bindings b
                    JOIN security_policies p ON b.policy_id = p.id
                    WHERE b.model_key = %s AND b.is_active = TRUE
                    ORDER BY b.priority DESC
                    """,
                    (model_key,),
                )
            else:
                cursor.execute(
                    """
                    SELECT b.*, p.name AS policy_name, p.scene, p.prompt, p.is_default
                    FROM model_policy_bindings b
                    JOIN security_policies p ON b.policy_id = p.id
                    ORDER BY b.model_key, b.priority DESC
                    """
                )
            bindings = cursor.fetchall()
        return jsonify({"success": True, "data": normalize_datetimes(bindings)})
    except Exception as e:
        logger.error(f"Failed to list bindings: {e}", exc_info=True)
        raise DatabaseError("获取绑定列表失败")


@bp.post("/api/policies/bindings")
def create_binding():
    """为模型绑定安全策略"""
    try:
        data = request.json or {}
        model_key = (data.get("model_key") or "").strip()
        policy_id = data.get("policy_id")
        priority = data.get("priority", 0)

        if not model_key:
            raise ValidationError("模型标识不能为空")
        if not policy_id:
            raise ValidationError("策略ID不能为空")

        settings = current_app.config["AISEC_SETTINGS"]
        with db_cursor(settings) as (conn, cursor):
            # 检查策略是否存在
            cursor.execute("SELECT id FROM security_policies WHERE id = %s", (policy_id,))
            if not cursor.fetchone():
                raise NotFoundError("策略不存在")

            # 检查是否已绑定
            cursor.execute(
                "SELECT id FROM model_policy_bindings WHERE model_key = %s AND policy_id = %s",
                (model_key, policy_id),
            )
            if cursor.fetchone():
                raise ValidationError("该模型已绑定此策略")

            cursor.execute(
                "INSERT INTO model_policy_bindings (model_key, policy_id, priority) VALUES (%s, %s, %s)",
                (model_key, policy_id, priority),
            )
            conn.commit()
            new_id = cursor.lastrowid

        return jsonify({"success": True, "data": {"id": new_id}, "message": "绑定成功"})
    except (ValidationError, NotFoundError):
        raise
    except Exception as e:
        logger.error(f"Failed to create binding: {e}", exc_info=True)
        raise DatabaseError("绑定失败")


@bp.delete("/api/policies/bindings/<int:binding_id>")
def delete_binding(binding_id: int):
    """删除模型-策略绑定"""
    try:
        settings = current_app.config["AISEC_SETTINGS"]
        with db_cursor(settings) as (conn, cursor):
            cursor.execute("DELETE FROM model_policy_bindings WHERE id = %s", (binding_id,))
            conn.commit()
            if cursor.rowcount == 0:
                raise NotFoundError("绑定不存在")
        return jsonify({"success": True, "message": "解绑成功"})
    except NotFoundError:
        raise
    except Exception as e:
        logger.error(f"Failed to delete binding {binding_id}: {e}", exc_info=True)
        raise DatabaseError("解绑失败")


# ==================== 查询模型在指定场景下的策略 ====================

@bp.get("/api/policies/resolve")
def resolve_policy():
    """
    根据模型标识和业务场景，解析出应使用的安全策略。

    查询参数:
        model_key: 模型标识（如 "3", "ollama:qwen2.5:latest"）
        scene: 业务场景（如 "finance"）

    优先级:
        1. 该模型在该场景下的绑定策略（按 priority 降序）
        2. 该场景的默认策略
        3. 通用场景(general)的默认策略
        4. 模型自身的 security_prompt
    """
    try:
        model_key = request.args.get("model_key", "")
        scene = request.args.get("scene", "general")

        settings = current_app.config["AISEC_SETTINGS"]
        with db_cursor(settings) as (conn, cursor):
            prompt = _resolve_security_prompt(cursor, model_key, scene)

        return jsonify({"success": True, "data": {"prompt": prompt, "scene": scene}})
    except Exception as e:
        logger.error(f"Failed to resolve policy: {e}", exc_info=True)
        raise DatabaseError("解析策略失败")


def _resolve_security_prompt(cursor, model_key: str, scene: str = "general") -> str:
    """
    解析模型在指定场景下应使用的安全提示词。

    优先级:
        1. 该模型在该场景下的绑定策略
        2. 该场景的默认策略
        3. 通用场景的默认策略
        4. 模型自身的 security_prompt（数据库模型）
    """
    # 1. 查找模型在该场景下的绑定策略
    cursor.execute(
        """
        SELECT p.prompt FROM model_policy_bindings b
        JOIN security_policies p ON b.policy_id = p.id
        WHERE b.model_key = %s AND p.scene = %s AND b.is_active = TRUE
        ORDER BY b.priority DESC
        LIMIT 1
        """,
        (model_key, scene),
    )
    row = cursor.fetchone()
    if row:
        return row["prompt"]

    # 2. 该场景的默认策略
    cursor.execute(
        "SELECT prompt FROM security_policies WHERE scene = %s AND is_default = TRUE LIMIT 1",
        (scene,),
    )
    row = cursor.fetchone()
    if row:
        return row["prompt"]

    # 3. 通用场景的默认策略
    if scene != "general":
        cursor.execute(
            "SELECT prompt FROM security_policies WHERE scene = 'general' AND is_default = TRUE LIMIT 1"
        )
        row = cursor.fetchone()
        if row:
            return row["prompt"]

    # 4. 模型自身的 security_prompt
    if model_key and model_key.isdigit():
        cursor.execute("SELECT security_prompt FROM models WHERE id = %s", (int(model_key),))
        row = cursor.fetchone()
        if row and row.get("security_prompt"):
            return row["security_prompt"]

    return ""
