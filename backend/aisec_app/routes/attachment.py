import base64
import logging
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from flask import Blueprint, current_app, jsonify, request

from ..db import db_cursor
from ..errors import DatabaseError, ExternalAPIError, NotFoundError, ValidationError
from ..services.config_service import get_judge_config, get_vision_config
from ..services.llm_service import resolve_model_params, call_chat
from .chat import check_content_safety

logger = logging.getLogger(__name__)

bp = Blueprint("attachment", __name__)


def parse_document(file_path, file_ext):
    text = ""
    images = []

    if file_ext == "pdf":
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(file_path)
            for page in doc:
                page_text = page.get_text()
                if page_text:
                    text += page_text + "\n"

                for img in page.get_images(full=True):
                    try:
                        xref = img[0]
                        base_image = doc.extract_image(xref)
                        image_data = base_image["image"]
                        images.append(base64.b64encode(image_data).decode("utf-8"))
                    except Exception:
                        pass
            doc.close()
        except ImportError:
            try:
                import PyPDF2

                with open(file_path, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
            except ImportError:
                return None, [], "需要安装 PyMuPDF: pip install PyMuPDF"

    elif file_ext in ["doc", "docx"]:
        try:
            from docx import Document

            doc = Document(file_path)
            for para in doc.paragraphs:
                if para.text.strip():
                    text += para.text + "\n"

            for rel in doc.part.rels.values():
                if "image" in rel.reltype:
                    try:
                        image_data = rel.target_part.blob
                        images.append(base64.b64encode(image_data).decode("utf-8"))
                    except Exception:
                        pass
        except ImportError:
            return None, [], "需要安装 python-docx: pip install python-docx"

    return text.strip() if text else None, images, None


def call_vision_model(image_base64, prompt, api_url, api_key, model_name):
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
                },
            ],
        }
    ]

    response = requests.post(
        f"{api_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model_name, "messages": messages, "max_tokens": 2048},
        timeout=60,
    )

    if response.status_code == 200:
        return response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    return None


@bp.post("/api/chat/attachment")
def chat_with_attachment():
    try:
        model_name_param = request.form.get("model_name")
        model_id_param = request.form.get("model_id")
        user_message = request.form.get("message", "")
        user_id = request.form.get("user_id", "anonymous")
        file = request.files.get("file")

        if (not model_name_param and not model_id_param) or not file:
            return jsonify({"success": False, "error": "缺少必要参数"}), 400

        settings = current_app.config["AISEC_SETTINGS"]
        with db_cursor(settings) as (conn, cursor):
            model_key = model_name_param or model_id_param
            params = resolve_model_params(model_key, cursor)

            if not params:
                return jsonify({"success": False, "error": "模型不存在"}), 404

            model_id = params["model_id"]
            api_url = params["api_url"]
            api_key = params["api_key"]
            model_name = params["model_name"]
            security_prompt = params["security_prompt"]
            is_local = params["source"] in ("ollama", "hf")

            if not is_local and not api_key:
                return jsonify({"success": False, "error": "该模型未配置 API Key"}), 400

            start_time = time.time()

            filename = file.filename
            file_ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

            image_exts = ["jpg", "jpeg", "png", "gif", "bmp", "webp"]
            doc_exts = ["pdf", "doc", "docx"]

            ai_response = ""
            check_performed = False

            if file_ext in image_exts:
                vision_api_url, vision_model_name, vision_api_key = get_vision_config(cursor)

                if not vision_api_url or not vision_api_key or not vision_model_name:
                    return jsonify({"success": False, "error": "请先在系统设置中配置视觉模型"}), 400

                image_data = file.read()
                image_base64 = base64.b64encode(image_data).decode("utf-8")

                prompt = user_message if user_message else "请详细描述这张图片的内容"
                ai_response = call_vision_model(
                    image_base64, prompt, vision_api_url, vision_api_key, vision_model_name
                )

                if not ai_response:
                    return jsonify({"success": False, "error": "视觉模型调用失败"}), 500

                if security_prompt:
                    judge_api_url, judge_model_name, judge_api_key = get_judge_config(cursor)
                    judge_api_url = judge_api_url or api_url
                    judge_model_name = judge_model_name or model_name
                    judge_api_key = judge_api_key or api_key

                    is_safe, risk_score, reason, _ = check_content_safety(
                        ai_response,
                        "output",
                        judge_api_url,
                        judge_api_key,
                        judge_model_name,
                        security_prompt,
                    )

                    if not is_safe:
                        response_time_ms = int((time.time() - start_time) * 1000)
                        cursor.execute(
                            """
                            INSERT INTO chat_logs
                            (model_id, user_id, user_input, ai_response, input_blocked, output_blocked, block_reason, confidence, context_summary, response_time_ms)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                model_id,
                                user_id,
                                f"[图片: {filename}]",
                                "",
                                False,
                                True,
                                f"图片内容违规: {reason}",
                                risk_score,
                                None,
                                response_time_ms,
                            ),
                        )
                        conn.commit()

                        return jsonify(
                            {
                                "success": True,
                                "data": {
                                    "blocked": True,
                                    "block_type": "output",
                                    "reason": f"图片内容存在安全风险: {reason}",
                                    "confidence": risk_score,
                                    "response_time_ms": response_time_ms,
                                },
                            }
                        )

                    check_performed = True

            elif file_ext in doc_exts:
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as tmp:
                    file.save(tmp.name)
                    tmp_path = tmp.name

                try:
                    doc_text, doc_images, error = parse_document(tmp_path, file_ext)
                    if error:
                        return jsonify({"success": False, "error": error}), 500

                    if not doc_text and not doc_images:
                        return jsonify({"success": False, "error": "文档解析失败或内容为空"}), 400

                    image_descriptions = []
                    if doc_images:
                        vision_api_url, vision_model_name, vision_api_key = get_vision_config(cursor)

                        if not vision_api_url or not vision_api_key or not vision_model_name:
                            doc_images = []

                        def recognize_image(args):
                            idx, img_base64 = args
                            try:
                                desc = call_vision_model(
                                    img_base64,
                                    "请简要描述这张图片的内容",
                                    vision_api_url,
                                    vision_api_key,
                                    vision_model_name,
                                )
                                return idx, desc
                            except Exception:
                                return idx, None

                        batch_size = 3
                        for batch_start in range(0, len(doc_images), batch_size):
                            batch = [
                                (i, doc_images[i])
                                for i in range(
                                    batch_start,
                                    min(batch_start + batch_size, len(doc_images)),
                                )
                            ]

                            with ThreadPoolExecutor(max_workers=3) as executor:
                                futures = [executor.submit(recognize_image, item) for item in batch]
                                for future in as_completed(futures):
                                    idx, desc = future.result()
                                    if desc:
                                        image_descriptions.append((idx, desc))

                        image_descriptions.sort(key=lambda x: x[0])

                    if not doc_text:
                        doc_text = ""
                    if image_descriptions:
                        doc_text += "\n\n【文档中的图片内容】\n"
                        for idx, desc in image_descriptions:
                            doc_text += f"图片{idx+1}: {desc}\n"

                    if doc_text and security_prompt:
                        judge_api_url, judge_model_name, judge_api_key = get_judge_config(cursor)
                        judge_api_url = judge_api_url or api_url
                        judge_model_name = judge_model_name or model_name
                        judge_api_key = judge_api_key or api_key

                        chunk_size = 2000
                        chunks = [
                            (i, doc_text[i * chunk_size : (i + 1) * chunk_size])
                            for i in range((len(doc_text) + chunk_size - 1) // chunk_size)
                        ]

                        def check_chunk(args):
                            idx, chunk = args
                            try:
                                is_safe, risk_score, reason, _ = check_content_safety(
                                    chunk,
                                    "input",
                                    judge_api_url,
                                    judge_api_key,
                                    judge_model_name,
                                    security_prompt,
                                )
                                return idx, is_safe, risk_score, reason, None
                            except Exception as e:
                                return idx, True, 0, "", str(e)

                        max_workers = min(8, len(chunks))
                        rate_limit_error = None

                        with ThreadPoolExecutor(max_workers=max_workers) as executor:
                            futures = {
                                executor.submit(check_chunk, chunk): chunk[0]
                                for chunk in chunks
                            }

                            for future in as_completed(futures):
                                idx, is_safe, risk_score, reason, error = future.result()

                                if error and (
                                    "rate" in error.lower()
                                    or "limit" in error.lower()
                                    or "429" in error
                                    or "quota" in error.lower()
                                ):
                                    rate_limit_error = error
                                    for f in futures:
                                        f.cancel()
                                    break

                                if not is_safe:
                                    for f in futures:
                                        f.cancel()

                                    response_time_ms = int((time.time() - start_time) * 1000)
                                    cursor.execute(
                                        """
                                        INSERT INTO chat_logs
                                        (model_id, user_id, user_input, ai_response, input_blocked, output_blocked, block_reason, confidence, context_summary, response_time_ms)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                        """,
                                        (
                                            model_id,
                                            user_id,
                                            f"[附件: {filename}]",
                                            "",
                                            True,
                                            False,
                                            f"文档第{idx+1}段违规: {reason}",
                                            risk_score,
                                            None,
                                            response_time_ms,
                                        ),
                                    )
                                    conn.commit()
                                    os.unlink(tmp_path)

                                    return jsonify(
                                        {
                                            "success": True,
                                            "data": {
                                                "blocked": True,
                                                "block_type": "input",
                                                "reason": f"文档第{idx+1}段存在安全风险: {reason}",
                                                "confidence": risk_score,
                                                "response_time_ms": response_time_ms,
                                            },
                                        }
                                    )

                        if rate_limit_error:
                            os.unlink(tmp_path)
                            return (
                                jsonify(
                                    {
                                        "success": False,
                                        "error": "文档过长，审查请求超出API限制，请稍后重试或上传较短的文档",
                                    }
                                ),
                                429,
                            )

                        check_performed = True

                    combined_message = (
                        f"以下是用户上传的文档内容：\n\n{doc_text[:8000]}\n\n用户问题："
                        f"{user_message if user_message else '请总结这个文档的主要内容'}"
                    )

                    messages = []
                    if security_prompt:
                        messages.append({"role": "system", "content": security_prompt})
                    messages.append({"role": "user", "content": combined_message})

                    ai_response = call_chat(
                        api_url, model_name, messages,
                        api_key=api_key, temperature=0.7, max_tokens=2048, timeout=60,
                    )

                    if ai_response is None:
                        return (
                            jsonify(
                                {
                                    "success": False,
                                    "error": "模型调用失败，未返回有效回复",
                                }
                            ),
                            500,
                        )

                finally:
                    os.unlink(tmp_path)

            else:
                return jsonify({"success": False, "error": "不支持的文件格式"}), 400

            response_time_ms = int((time.time() - start_time) * 1000)

            cursor.execute(
                """
                INSERT INTO chat_logs
                (model_id, user_id, user_input, ai_response, input_blocked, output_blocked, block_reason, confidence, context_summary, response_time_ms)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    model_id,
                    user_id,
                    f"[附件: {filename}] {user_message}",
                    ai_response,
                    False,
                    False,
                    None,
                    None,
                    None,
                    response_time_ms,
                ),
            )
            conn.commit()

        return jsonify(
            {
                "success": True,
                "data": {
                    "response": ai_response,
                    "blocked": False,
                    "response_time_ms": response_time_ms,
                    "check_enabled": check_performed,
                },
            }
        )

    except NotFoundError:
        raise
    except ValidationError:
        raise
    except ExternalAPIError:
        raise
    except Exception as e:
        logger.error(f"Attachment chat failed: {str(e)}", exc_info=True)
        raise DatabaseError("附件对话处理失败")
