# Handles audio chunk stream + session management

import socketio
from utils.redis_utils import create_session, add_audio_chunk, get_audio_chunks, remove_session, get_session_meta, set_session_meta
from utils import audio_utils
from services.stt_service import stt_service 
from services.tts_service import tts_service
from sqlalchemy import select
from db import AsyncSessionLocal
from models import Response
import base64

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
_sessions = {}

@sio.event
async def connect(sid, environ):
    await sio.emit("connected", {"sid": sid}, to=sid)

@sio.event
async def disconnect(sid):
    session_id = _sessions.pop(sid, None)
    if session_id:
        await remove_session(session_id)

@sio.event
async def start_interview(sid, data):
    session_id = data.get("session_id")
    response_id = data.get("response_id")
    session_token = data.get("session_token")

    if not session_id or not response_id or not session_token:
        return {"ok": False, "error": "session_id, response_id, session_token are required"}

    meta = await get_session_meta(session_id)
    if not meta:
        return {"ok": False, "error": "Session not initialized via REST /start"}
    if meta.get("response_id") != str(response_id):
        return {"ok": False, "error": "response_id mismatch"}
    if meta.get("session_token") != session_token:
        return {"ok": False, "error": "Invalid session token"}

    _sessions[sid] = {
        "session_id": session_id,
        "response_id": response_id,
        "interview_id": meta.get("interview_id")
    }
    await sio.enter_room(sid, session_id)
    await set_session_meta(session_id, {"sid": sid})

    return {
        "ok": True,
        "session_id": session_id,
        "response_id": response_id,
        "interview_id": meta.get("interview_id")
    }

@sio.event
async def send_audio_chunk(sid, data):
    sess = _sessions.get(sid)
    if not sess:
        return {"ok": False, "error": "No active session"}
    session_id = sess["session_id"]

    chunk_bytes = data if isinstance(data, (bytes, bytearray)) else data.get("chunk_data", data)
    if chunk_bytes :
        print(f"[DEBUG] Received audio chunk from {sid}: {len(chunk_bytes)} bytes") 
    else : 
        print(" Empty chunks ")
    await add_audio_chunk(session_id, chunk_bytes)
    
    try:
        print(f"[DEBUG] Processing audio chunk: {len(chunk_bytes)} bytes")
        converted_audio = audio_utils.converted_audio_compatible(chunk_bytes)
        print(f"[DEBUG] Converted audio: {len(converted_audio)} bytes")
        
        transcript = await stt_service.provider.transcribe(converted_audio)
        print(f"[DEBUG] STT result: '{transcript}'")
        
        if transcript.strip(): 
            print(f"[DEBUG] Real-time transcript chunk: {transcript}")
            await sio.emit("transcript_result", {"text": transcript}, to=sid)
        else:
            print(f"[DEBUG] Empty transcript, not sending")
    except Exception as e:
        print(f"[ERROR] Failed to process audio chunk: {e}")
        import traceback
        traceback.print_exc()
    
    return {"ok": True}

@sio.event
async def send_question_audio(sid, data):
    sess = _sessions.get(sid)
    if not sess:
        return {"ok": False, "error": "No active session"}
    
    try:
        question_text = data.get("text")
        if not question_text:
            return {"ok": False, "error": "No text provided"}
        
        audio_bytes = await tts_service.synthesize_text(question_text)
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        await sio.emit("question_audio", {
            "audio": audio_b64,
            "text": question_text
        }, to=sid)
        
        return {"ok": True, "message": "Audio sent successfully"}
        
    except Exception as e:
        print(f"[ERROR] Failed to synthesize audio: {e}")
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": str(e)}

@sio.event
async def end_interview(sid, data=None):
    sess = _sessions.get(sid)
    if not sess:
        return {"ok": False, "error": "No active session"}

    session_id = sess["session_id"]
    response_id = sess["response_id"]

    try:
        final_text = await stt_service.transcribe_session(session_id)
        print(f"[DEBUG] Final transcript: {final_text}")
        await sio.emit("transcript_result", {"text": final_text}, to=sid)
        return {"ok": True, "transcript": final_text, "response_id": response_id}
    finally:
        await remove_session(session_id)
        _sessions.pop(sid, None)
        await sio.leave_room(sid, session_id)

@sio.event
async def get_transcript(sid, data=None):
    sess = _sessions.get(sid)
    if not sess:
        return {"ok": False, "error": "No active session"}

    session_id = sess["session_id"]
    
    try:
        transcript = await stt_service.transcribe_session(session_id)
        return {"ok": True, "transcript": transcript}
    except Exception as e:
        print(f"[ERROR] Failed to get transcript: {e}")
        return {"ok": False, "error": str(e)}