from flask import Blueprint, current_app, jsonify, request
import json as json_lib
import os
import pymysql
import logging
from pathlib import Path
import requests as http_requests
from pydantic import ValidationError as PydanticValidationError

from ..db import db_cursor
from ..errors import DatabaseError, NotFoundError, ValidationError
from ..utils import normalize_datetimes
from ..validators import CreateModelRequest, UpdateModelRequest

logger = logging.getLogger(__name__)

bp = Blueprint("models", __name__)

OLLAMA_BASE_URL = "http://localhost:11434"


@bp.get("/api/models")
def get_models():
    try:
        settings = current_app.config["AISEC_SETTINGS"]
        with db_cursor(settings) as (conn, cursor):
            cursor.execute("SELECT * FROM models ORDER BY created_at DESC")
            models = cursor.fetchall()
        return jsonify({"success": True, "data": normalize_datetimes(models)})
    except Exception as e:
        logger.error(f"Failed to get models: {str(e)}", exc_info=True)
        raise DatabaseError("获取模型列表失败")


@bp.get("/api/models/<int:model_id>")
def get_model(model_id: int):
    try:
        settings = current_app.config["AISEC_SETTINGS"]
        with db_cursor(settings) as (conn, cursor):
            cursor.execute("SELECT * FROM models WHERE id = %s", (model_id,))
            model = cursor.fetchone()
        if not model:
            raise NotFoundError("模型不存在")
        return jsonify({"success": True, "data": normalize_datetimes(model)})
    except NotFoundError:
        raise
    except Exception as e:
        logger.error(f"Failed to get model {model_id}: {str(e)}", exc_info=True)
        raise DatabaseError("获取模型详情失败")


@bp.post("/api/models")
def create_model():
    try:
        data = request.json or {}
        try:
            validated = CreateModelRequest(**data)
        except PydanticValidationError as e:
            raise ValidationError(str(e.errors()[0]['msg']))

        settings = current_app.config["AISEC_SETTINGS"]
        with db_cursor(settings) as (conn, cursor):
            cursor.execute(
                """
                INSERT INTO models (name, model_id, model_type, url, api_key, security_prompt, custom_config)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    validated.name,
                    validated.model_id,
                    validated.model_type,
                    validated.url,
                    validated.api_key,
                    validated.security_prompt,
                    validated.custom_config,
                ),
            )
            conn.commit()
            new_id = cursor.lastrowid

        return jsonify({"success": True, "data": {"id": new_id}, "message": "模型创建成功"})
    except pymysql.err.IntegrityError:
        raise ValidationError("模型名称或 ID 已存在")
    except Exception as e:
        logger.error(f"Failed to create model: {str(e)}", exc_info=True)
        raise DatabaseError("创建模型失败")


@bp.put("/api/models/<int:model_id>")
def update_model(model_id: int):
    try:
        data = request.json or {}
        try:
            validated = UpdateModelRequest(**data)
        except PydanticValidationError as e:
            raise ValidationError(str(e.errors()[0]['msg']))

        settings = current_app.config["AISEC_SETTINGS"]
        with db_cursor(settings) as (conn, cursor):
            cursor.execute(
                """
                UPDATE models SET
                    name = COALESCE(%s, name),
                    model_id = COALESCE(%s, model_id),
                    model_type = COALESCE(%s, model_type),
                    url = COALESCE(%s, url),
                    api_key = COALESCE(%s, api_key),
                    security_prompt = COALESCE(%s, security_prompt),
                    custom_config = COALESCE(%s, custom_config)
                WHERE id = %s
                """,
                (
                    validated.name,
                    validated.model_id,
                    validated.model_type,
                    validated.url,
                    validated.api_key,
                    validated.security_prompt,
                    validated.custom_config,
                    model_id,
                ),
            )
            conn.commit()
            affected = cursor.rowcount

        if affected == 0:
            return jsonify({"success": False, "error": "模型不存在"}), 404
        return jsonify({"success": True, "message": "模型更新成功"})
    except pymysql.err.IntegrityError:
        raise ValidationError("模型名称或 ID 已存在")
    except Exception as e:
        logger.error(f"Failed to update model {model_id}: {str(e)}", exc_info=True)
        raise DatabaseError("更新模型失败")


@bp.delete("/api/models/<int:model_id>")
def delete_model(model_id: int):
    try:
        settings = current_app.config["AISEC_SETTINGS"]
        with db_cursor(settings) as (conn, cursor):
            cursor.execute("DELETE FROM models WHERE id = %s", (model_id,))
            conn.commit()
            affected = cursor.rowcount

        if affected == 0:
            raise NotFoundError("模型不存在")
        return jsonify({"success": True, "message": "模型删除成功"})
    except NotFoundError:
        raise
    except Exception as e:
        logger.error(f"Failed to delete model {model_id}: {str(e)}", exc_info=True)
        raise DatabaseError("删除模型失败")


@bp.get("/api/models/ollama")
def get_ollama_models():
    """获取 Ollama 本地已安装的模型列表"""
    try:
        resp = http_requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if resp.status_code != 200:
            return jsonify({"success": True, "data": [], "message": "Ollama 服务未响应"})

        raw_models = resp.json().get("models", [])
        models = []
        for m in raw_models:
            name = m.get("name", "")
            size_bytes = m.get("size", 0)
            if size_bytes > 1024 * 1024 * 1024:
                size_str = f"{size_bytes / (1024**3):.1f}GB"
            elif size_bytes > 1024 * 1024:
                size_str = f"{size_bytes / (1024**2):.0f}MB"
            else:
                size_str = f"{size_bytes / 1024:.0f}KB"

            models.append({
                "name": name,
                "size": size_str,
                "parameter_size": m.get("details", {}).get("parameter_size", ""),
                "family": m.get("details", {}).get("family", ""),
                "quantization": m.get("details", {}).get("quantization_level", ""),
                "modified_at": m.get("modified_at", ""),
            })

        return jsonify({"success": True, "data": models})
    except http_requests.exceptions.ConnectionError:
        return jsonify({"success": True, "data": [], "message": "Ollama 服务未启动"})
    except Exception as e:
        logger.error(f"Failed to get Ollama models: {str(e)}", exc_info=True)
        return jsonify({"success": True, "data": [], "message": f"获取失败: {str(e)}"})


@bp.get("/api/models/local")
def get_local_models():
    """获取本地已下载的 HuggingFace 模型"""
    models = []

    # HuggingFace 缓存目录
    hf_cache = Path.home() / ".cache" / "huggingface" / "hub"
    if not hf_cache.exists():
        return jsonify({"success": True, "data": []})

    for entry in hf_cache.iterdir():
        if not entry.is_dir() or not entry.name.startswith("models--"):
            continue

        # 解析模型名: models--Qwen--Qwen2.5-7B -> Qwen/Qwen2.5-7B
        parts = entry.name.split("--")[1:]
        repo_id = "/".join(parts)

        # 找到最新的 snapshot
        snapshots_dir = entry / "snapshots"
        if not snapshots_dir.exists():
            continue

        snapshot_dirs = sorted(snapshots_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        if not snapshot_dirs:
            continue

        snapshot = snapshot_dirs[0]

        # 读取 config.json 获取模型信息
        config_file = snapshot / "config.json"
        model_info = {
            "name": repo_id,
            "path": str(snapshot),
            "source": "huggingface",
            "size": "",
            "architecture": "",
            "model_type": "",
            "parameters": "",
        }

        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    cfg = json_lib.load(f)
                model_info["architecture"] = (cfg.get("architectures", [""])[0]
                                              if cfg.get("architectures") else "")
                model_info["model_type"] = cfg.get("model_type", "")

                # 估算参数量
                hidden = cfg.get("hidden_size", 0)
                layers = cfg.get("num_hidden_layers", 0)
                intermediate = cfg.get("intermediate_size", 0)
                if hidden and layers:
                    param_estimate = layers * (4 * hidden * hidden + 2 * hidden * intermediate)
                    if param_estimate > 1e9:
                        model_info["parameters"] = f"{param_estimate / 1e9:.1f}B"
                    elif param_estimate > 1e6:
                        model_info["parameters"] = f"{param_estimate / 1e6:.0f}M"
            except Exception:
                pass

        # 计算磁盘占用
        total_size = 0
        blobs_dir = entry / "blobs"
        if blobs_dir.exists():
            for blob in blobs_dir.iterdir():
                if blob.is_file():
                    total_size += blob.stat().st_size

        if total_size > 1024 ** 3:
            model_info["size"] = f"{total_size / (1024**3):.1f}GB"
        elif total_size > 1024 ** 2:
            model_info["size"] = f"{total_size / (1024**2):.0f}MB"
        elif total_size > 0:
            model_info["size"] = f"{total_size / 1024:.0f}KB"

        models.append(model_info)

    return jsonify({"success": True, "data": models})
