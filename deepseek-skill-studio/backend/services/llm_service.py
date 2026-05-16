"""Unified LLM service: Ollama, Claude, OpenAI, OpenAI-compatible."""
import json
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from fastapi import HTTPException


class LLMService:
    def __init__(self, settings: dict):
        self.s = settings

    @property
    def provider(self) -> str:
        return self.s.get("llm_provider", "ollama")

    @property
    def ollama_url(self) -> str:
        return self.s.get("ollama_base_url", "http://127.0.0.1:11434")

    def default_model(self) -> str:
        p = self.provider
        if p == "claude":
            return self.s.get("claude_model", "claude-sonnet-4-6")
        if p in ("openai", "openai_compat"):
            return self.s.get("openai_model", "gpt-4o")
        return self.s.get("ollama_model", "deepseek-r1:8b")

    # ── Non-streaming completion ────────────────────────────────────────

    async def chat_complete(
        self,
        messages: List[Dict],
        model: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
    ) -> str:
        chunks: List[str] = []
        async for chunk in self.chat_stream(messages, model, tools):
            chunks.append(chunk)
        return "".join(chunks)

    # ── Streaming completion ────────────────────────────────────────────

    async def chat_stream(
        self,
        messages: List[Dict],
        model: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
    ) -> AsyncGenerator[str, None]:
        m = model or self.default_model()
        p = self.provider
        if p == "claude":
            async for chunk in self._claude_stream(messages, m, tools):
                yield chunk
        elif p in ("openai", "openai_compat"):
            async for chunk in self._openai_stream(messages, m, tools):
                yield chunk
        else:
            async for chunk in self._ollama_stream(messages, m):
                yield chunk

    # ── Ollama ──────────────────────────────────────────────────────────

    async def _ollama_stream(self, messages: List[Dict], model: str) -> AsyncGenerator[str, None]:
        url = f"{self.ollama_url}/api/chat"
        try:
            async with httpx.AsyncClient(timeout=900) as client:
                async with client.stream(
                    "POST", url,
                    json={"model": model, "messages": messages, "stream": True},
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            chunk = data.get("message", {}).get("content", "")
                            if chunk:
                                yield chunk
                        except Exception:
                            pass
        except HTTPException:
            raise
        except Exception as exc:
            # Fallback: try /api/generate
            try:
                prompt = "\n".join(
                    f"{m.get('role','user').upper()}: {m.get('content','')}" for m in messages
                )
                async with httpx.AsyncClient(timeout=900) as client:
                    async with client.stream(
                        "POST", f"{self.ollama_url}/api/generate",
                        json={"model": model, "prompt": prompt, "stream": True},
                    ) as resp:
                        resp.raise_for_status()
                        async for line in resp.aiter_lines():
                            if not line:
                                continue
                            try:
                                data = json.loads(line)
                                chunk = data.get("response", "")
                                if chunk:
                                    yield chunk
                            except Exception:
                                pass
            except Exception as exc2:
                raise HTTPException(
                    500,
                    f"Ollama request failed. Is Ollama running and the model pulled? Error: {exc2}",
                )

    # ── Claude ──────────────────────────────────────────────────────────

    async def _claude_stream(
        self, messages: List[Dict], model: str, tools: Optional[List[Dict]]
    ) -> AsyncGenerator[str, None]:
        try:
            import anthropic
        except ImportError:
            raise HTTPException(500, "Install the 'anthropic' package: pip install anthropic")

        api_key = self.s.get("claude_api_key", "")
        if not api_key:
            raise HTTPException(400, "Claude API key is not configured. Add it in Settings.")

        client = anthropic.AsyncAnthropic(api_key=api_key)
        system_msgs = [m for m in messages if m.get("role") == "system"]
        user_msgs = [m for m in messages if m.get("role") != "system"]
        system_text = "\n\n".join(m["content"] for m in system_msgs)

        kwargs: Dict[str, Any] = {
            "model": model,
            "max_tokens": 8192,
            "messages": user_msgs,
        }
        if system_text:
            kwargs["system"] = system_text
        if tools:
            kwargs["tools"] = tools

        try:
            async with client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield text
        except Exception as exc:
            raise HTTPException(500, f"Claude API error: {exc}")

    # ── OpenAI / OpenAI-compat ──────────────────────────────────────────

    async def _openai_stream(
        self, messages: List[Dict], model: str, tools: Optional[List[Dict]]
    ) -> AsyncGenerator[str, None]:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise HTTPException(500, "Install the 'openai' package: pip install openai")

        api_key = self.s.get("openai_api_key") or "sk-dummy"
        base_url = self.s.get("openai_base_url") or None

        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools

        try:
            stream = await client.chat.completions.create(**kwargs)
            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content
        except Exception as exc:
            raise HTTPException(500, f"OpenAI API error: {exc}")

    # ── Embeddings ──────────────────────────────────────────────────────

    async def embed(self, text: str) -> List[float]:
        p = self.provider
        if p in ("openai", "openai_compat"):
            return await self._openai_embed(text)
        return await self._ollama_embed(text)

    async def _ollama_embed(self, text: str) -> List[float]:
        model = self.s.get("ollama_embedding_model", "nomic-embed-text")
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{self.ollama_url}/api/embeddings",
                    json={"model": model, "prompt": text},
                )
                resp.raise_for_status()
                return resp.json().get("embedding", [])
        except Exception:
            return []

    async def _openai_embed(self, text: str) -> List[float]:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            return []
        client = AsyncOpenAI(
            api_key=self.s.get("openai_api_key") or "sk-dummy",
            base_url=self.s.get("openai_base_url") or None,
        )
        try:
            resp = await client.embeddings.create(model="text-embedding-3-small", input=text)
            return resp.data[0].embedding
        except Exception:
            return []

    # ── Installed models (Ollama only) ──────────────────────────────────

    def installed_ollama_models(self) -> List[str]:
        import requests as req
        try:
            tags = req.get(f"{self.ollama_url}/api/tags", timeout=5).json()
            return sorted(
                item.get("name", "") for item in tags.get("models", []) if item.get("name")
            )
        except Exception:
            return []
